import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SanitizationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_safe: bool
    original: str
    sanitized: str
    threats_detected: list[str]
    warnings: list[str]


class InputSanitizer:
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC)\b.*\b(FROM|INTO|TABLE|DATABASE|WHERE|SET)\b)",
        r"(--|#|/\*|\*/|;)",
        r"(\bOR\b\s+\d+\s*=\s*\d+)",
        r"(\bOR\b\s+'[^']*'\s*=\s*'[^']*')",
        r"(\b(UNION\s+(ALL\s+)?SELECT)\b)",
        r"(\b(INSERT\s+INTO|DELETE\s+FROM|UPDATE\s+\w+\s+SET|DROP\s+TABLE)\b)",
        r"(\b(EXEC|EXECUTE)\s+\()",
        r"(xp_cmdshell|sp_executesql)",
        r"(\b(WAITFOR\s+DELAY|BENCHMARK)\b)",
        r"(LOAD_FILE|INTO\s+(OUT|DUMP)FILE)",
    ]

    SHELL_INJECTION_PATTERNS = [
        r"(\$\(|`[^`]*`)",
        r"(;\s*(rm|del|format|fdisk|mkfs|dd)\b)",
        r"(\|\s*(rm|del|format|fdisk|mkfs|dd)\b)",
        r"(\b(rm\s+-rf|del\s+/[sfq]|format\s+[a-z]:|fdisk|mkfs)\b)",
        r"(\b(shutdown|reboot|halt|poweroff|init\s+[06])\b)",
        r"(>.*(/etc/passwd|/etc/shadow|C:/Windows/System32))",
        r"(\bcurl\b.*\|\s*(sh|bash|powershell))",
        r"(\bwget\b.*\|\s*(sh|bash|powershell))",
        r"(\b(nc|ncat|netcat)\s+-[el])",
        r"(\b(chmod\s+777|chown\s+root)\b)",
    ]

    PATH_TRAVERSAL_PATTERNS = [
        r"(\.\./|\.\.\\)",
        r"(%2e%2e[/%5c])",
        r"(%252e%252e[/%5c])",
        r"(\.\.%2f|\.\.%5c)",
    ]

    XSS_PATTERNS = [
        r"(<script[^>]*>)",
        r"(javascript\s*:)",
        r"(on\w+\s*=)",
        r"(<iframe|<object|<embed|<form)",
        r"(eval\s*\(|alert\s*\(|prompt\s*\(|confirm\s*\()",
        r"(document\.cookie|document\.write)",
        r"(\.innerHTML\s*=)",
    ]

    COMMAND_INJECTION_PATTERNS = [
        r"(;\s*\w+)",
        r"(\|\s*\w+)",
        r"(&&\s*\w+)",
        r"(\|\|\s*\w+)",
        r"(\$\{.*\})",
        r"(%[0-9a-fA-F]{2})",
    ]

    def __init__(self):
        self._sql_patterns = [re.compile(p, re.IGNORECASE) for p in self.SQL_INJECTION_PATTERNS]
        self._shell_patterns = [re.compile(p, re.IGNORECASE) for p in self.SHELL_INJECTION_PATTERNS]
        self._path_patterns = [re.compile(p, re.IGNORECASE) for p in self.PATH_TRAVERSAL_PATTERNS]
        self._xss_patterns = [re.compile(p, re.IGNORECASE) for p in self.XSS_PATTERNS]
        self._cmd_patterns = [re.compile(p, re.IGNORECASE) for p in self.COMMAND_INJECTION_PATTERNS]

    def sanitize_sql(self, input_str: str) -> SanitizationResult:
        threats = []
        for pattern in self._sql_patterns:
            if pattern.search(input_str):
                threats.append(f"SQL injection pattern detected: {pattern.pattern}")

        sanitized = input_str
        for pattern in self._sql_patterns:
            sanitized = pattern.sub("", sanitized)

        return SanitizationResult(
            is_safe=len(threats) == 0,
            original=input_str,
            sanitized=sanitized,
            threats_detected=threats,
            warnings=[],
        )

    def sanitize_shell(self, input_str: str) -> SanitizationResult:
        threats = []
        warnings = []

        for pattern in self._shell_patterns:
            if pattern.search(input_str):
                threats.append(f"Shell injection pattern detected: {pattern.pattern}")

        for pattern in self._cmd_patterns:
            if pattern.search(input_str):
                warnings.append(f"Potential command injection: {pattern.pattern}")

        sanitized = input_str
        for pattern in self._shell_patterns:
            sanitized = pattern.sub("", sanitized)

        return SanitizationResult(
            is_safe=len(threats) == 0,
            original=input_str,
            sanitized=sanitized,
            threats_detected=threats,
            warnings=warnings,
        )

    def sanitize_path(self, input_str: str) -> SanitizationResult:
        threats = []
        for pattern in self._path_patterns:
            if pattern.search(input_str):
                threats.append(f"Path traversal pattern detected: {pattern.pattern}")

        sanitized = input_str
        for pattern in self._path_patterns:
            sanitized = pattern.sub("", sanitized)

        try:
            resolved = Path(sanitized).expanduser().resolve()
            sanitized = str(resolved)
        except (OSError, RuntimeError):
            pass

        return SanitizationResult(
            is_safe=len(threats) == 0,
            original=input_str,
            sanitized=sanitized,
            threats_detected=threats,
            warnings=[],
        )

    def sanitize_xss(self, input_str: str) -> SanitizationResult:
        threats = []
        for pattern in self._xss_patterns:
            if pattern.search(input_str):
                threats.append(f"XSS pattern detected: {pattern.pattern}")

        sanitized = input_str
        for pattern in self._xss_patterns:
            sanitized = pattern.sub("", sanitized)

        sanitized = sanitized.replace("<", "&lt;").replace(">", "&gt;")

        return SanitizationResult(
            is_safe=len(threats) == 0,
            original=input_str,
            sanitized=sanitized,
            threats_detected=threats,
            warnings=[],
        )

    def sanitize_all(self, input_str: str) -> SanitizationResult:
        all_threats = []
        all_warnings = []
        sanitized = input_str

        sql_result = self.sanitize_sql(sanitized)
        all_threats.extend(sql_result.threats_detected)
        sanitized = sql_result.sanitized

        shell_result = self.sanitize_shell(sanitized)
        all_threats.extend(shell_result.threats_detected)
        all_warnings.extend(shell_result.warnings)
        sanitized = shell_result.sanitized

        path_result = self.sanitize_path(sanitized)
        all_threats.extend(path_result.threats_detected)
        sanitized = path_result.sanitized

        xss_result = self.sanitize_xss(sanitized)
        all_threats.extend(xss_result.threats_detected)
        sanitized = xss_result.sanitized

        return SanitizationResult(
            is_safe=len(all_threats) == 0,
            original=input_str,
            sanitized=sanitized,
            threats_detected=all_threats,
            warnings=all_warnings,
        )

    def is_safe_path(self, path: str, allowed_dirs: Optional[list[str]] = None) -> bool:
        try:
            resolved = Path(path).expanduser().resolve()

            dangerous_dirs = {
                Path("C:/Windows"),
                Path("C:/Program Files"),
                Path("C:/Program Files (x86)"),
                Path("/etc"),
                Path("/usr"),
                Path("/bin"),
                Path("/sbin"),
                Path("/root"),
            }

            for dangerous in dangerous_dirs:
                try:
                    resolved.relative_to(dangerous)
                    return False
                except ValueError:
                    continue

            if allowed_dirs:
                allowed = False
                for allowed_dir in allowed_dirs:
                    try:
                        resolved.relative_to(Path(allowed_dir).expanduser().resolve())
                        allowed = True
                        break
                    except ValueError:
                        continue
                return allowed

            return True
        except (OSError, RuntimeError):
            return False

    def is_safe_shell_command(self, command: str) -> bool:
        result = self.sanitize_shell(command)
        return result.is_safe

    def is_safe_sql(self, query: str) -> bool:
        result = self.sanitize_sql(query)
        return result.is_safe


_sanitizer: Optional[InputSanitizer] = None


def get_sanitizer() -> InputSanitizer:
    global _sanitizer
    if _sanitizer is None:
        _sanitizer = InputSanitizer()
    return _sanitizer
