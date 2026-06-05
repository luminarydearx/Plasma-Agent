from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Vulnerability:
    file: str
    line: int
    severity: str
    category: str
    description: str
    recommendation: str


@dataclass
class AuditReport:
    project_path: str
    total_files: int
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    score: float = 100.0
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_path": self.project_path,
            "total_files": self.total_files,
            "score": round(self.score, 2),
            "vulnerabilities_count": len(self.vulnerabilities),
            "by_severity": {
                "critical": sum(1 for v in self.vulnerabilities if v.severity == "CRITICAL"),
                "high": sum(1 for v in self.vulnerabilities if v.severity == "HIGH"),
                "medium": sum(1 for v in self.vulnerabilities if v.severity == "MEDIUM"),
                "low": sum(1 for v in self.vulnerabilities if v.severity == "LOW"),
            },
            "by_category": self._count_by_category(),
            "vulnerabilities": [
                {
                    "file": v.file,
                    "line": v.line,
                    "severity": v.severity,
                    "category": v.category,
                    "description": v.description,
                    "recommendation": v.recommendation,
                }
                for v in self.vulnerabilities
            ],
        }

    def _count_by_category(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for v in self.vulnerabilities:
            counts[v.category] = counts.get(v.category, 0) + 1
        return counts


class SecurityAuditor:
    SQL_INJECTION_PATTERNS = [
        (r'(?:execute|cursor\.execute)\s*\(\s*["\'].*?%s', "SQL injection: Use parameterized queries instead of string formatting"),
        (r'(?:execute|cursor\.execute)\s*\(\s*f["\']', "SQL injection: Use parameterized queries instead of f-strings"),
        (r'(?:execute|cursor\.execute)\s*\(\s*["\'].*?\+\s*\w+', "SQL injection: Use parameterized queries instead of string concatenation"),
        (r'f["\'].*?SELECT.*?\{', "SQL injection: Never use f-strings for SQL queries"),
        (r'["\'].*?SELECT.*?["\']\s*\+\s*\w+', "SQL injection: Never concatenate strings for SQL queries"),
    ]

    XSS_PATTERNS = [
        (r'\.innerHTML\s*=', "XSS: Use textContent instead of innerHTML"),
        (r'document\.write\s*\(', "XSS: Avoid document.write, use DOM APIs safely"),
        (r'v-html\s*=', "XSS: v-html can lead to XSS, sanitize input first"),
        (r'dangerouslySetInnerHTML', "XSS: Ensure content is sanitized before using dangerouslySetInnerHTML"),
    ]

    PATH_TRAVERSAL_PATTERNS = [
        (r'\.\.[\\/]', "Path traversal: Validate and sanitize file paths"),
        (r'open\s*\(\s*(?:request|req|params|args)', "Path traversal: Never use user input directly in file operations"),
        (r'Path\s*\(\s*(?:request|req|params|args)', "Path traversal: Validate user input before creating Path objects"),
    ]

    HARDCODED_SECRETS_PATTERNS = [
        (r'(?:password|passwd|pwd)\s*=\s*["\'][^"\']{3,}["\']', "Hardcoded secret: Use environment variables for passwords"),
        (r'(?:api_key|apikey|api_secret)\s*=\s*["\'][^"\']{3,}["\']', "Hardcoded secret: Use environment variables for API keys"),
        (r'(?:secret|token)\s*=\s*["\'][^"\']{3,}["\']', "Hardcoded secret: Use environment variables for secrets"),
        (r'(?:AKIA|ASIA)[A-Z0-9]{16}', "Hardcoded AWS credentials detected"),
    ]

    COMMAND_INJECTION_PATTERNS = [
        (r'subprocess\.(?:call|run|Popen)\s*\(\s*(?:request|req|params|args)', "Command injection: Never pass user input directly to shell commands"),
        (r'os\.system\s*\(', "Command injection: Use subprocess with proper argument lists"),
        (r'os\.popen\s*\(', "Command injection: Use subprocess instead of os.popen"),
        (r'eval\s*\(', "Code injection: Avoid eval, use safer alternatives"),
        (r'exec\s*\(', "Code injection: Avoid exec, it's extremely dangerous"),
    ]

    INSECURE_CRYPTO_PATTERNS = [
        (r'(?:MD5|md5)\s*\(', "Insecure crypto: MD5 is broken, use SHA-256 or better"),
        (r'(?:SHA1|sha1)\s*\(', "Insecure crypto: SHA1 is weak, use SHA-256 or better"),
        (r'(?:DES|RC4)\s*\(', "Insecure crypto: DES/RC4 are deprecated, use AES"),
    ]

    DEBUG_PATTERNS = [
        (r'DEBUG\s*=\s*True', "Debug mode: Disable DEBUG in production"),
        (r'app\.debug\s*=\s*True', "Debug mode: Disable debug in production"),
        (r'print\s*\(', "Debug logging: Use proper logging framework"),
    ]

    def __init__(self) -> None:
        self._patterns = {
            "SQL Injection": self.SQL_INJECTION_PATTERNS,
            "XSS": self.XSS_PATTERNS,
            "Path Traversal": self.PATH_TRAVERSAL_PATTERNS,
            "Hardcoded Secrets": self.HARDCODED_SECRETS_PATTERNS,
            "Command Injection": self.COMMAND_INJECTION_PATTERNS,
            "Insecure Crypto": self.INSECURE_CRYPTO_PATTERNS,
            "Debug Mode": self.DEBUG_PATTERNS,
        }

    async def audit_project(self, project_path: str, file_extensions: list[str] | None = None) -> AuditReport:
        path = Path(project_path).expanduser().resolve()
        if not path.exists():
            return AuditReport(
                project_path=str(path),
                total_files=0,
                vulnerabilities=[
                    Vulnerability(
                        file=str(path),
                        line=0,
                        severity="CRITICAL",
                        category="Configuration",
                        description=f"Project path not found: {path}",
                        recommendation="Provide a valid project path",
                    )
                ],
                score=0.0,
            )

        extensions = file_extensions or [".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".php", ".rb"]

        files = []
        for ext in extensions:
            files.extend(path.rglob(f"*{ext}"))

        files = [f for f in files if ".venv" not in str(f) and "node_modules" not in str(f) and "__pycache__" not in str(f)]

        report = AuditReport(project_path=str(path), total_files=len(files))

        for file_path in files:
            try:
                vulnerabilities = await self._scan_file(file_path)
                report.vulnerabilities.extend(vulnerabilities)
            except UnicodeDecodeError:
                continue
            except Exception:
                continue

        report.score = self._calculate_score(report)
        return report

    async def _scan_file(self, file_path: Path) -> list[Vulnerability]:
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")
        vulnerabilities = []

        for category, patterns in self._patterns.items():
            for pattern, recommendation in patterns:
                for line_num, line in enumerate(lines, start=1):
                    if re.search(pattern, line, re.IGNORECASE):
                        severity = self._get_severity(category, pattern)
                        vulnerabilities.append(
                            Vulnerability(
                                file=str(file_path),
                                line=line_num,
                                severity=severity,
                                category=category,
                                description=f"Line {line_num}: {line.strip()[:100]}",
                                recommendation=recommendation,
                            )
                        )

        return vulnerabilities

    def _get_severity(self, category: str, pattern: str) -> str:
        critical_categories = {"SQL Injection", "Command Injection", "Hardcoded Secrets"}
        high_categories = {"Path Traversal", "XSS"}

        if category in critical_categories:
            return "CRITICAL"
        elif category in high_categories:
            return "HIGH"
        elif "eval" in pattern or "exec" in pattern:
            return "CRITICAL"
        else:
            return "MEDIUM"

    def _calculate_score(self, report: AuditReport) -> float:
        if not report.vulnerabilities:
            return 100.0

        penalty = 0.0
        for v in report.vulnerabilities:
            if v.severity == "CRITICAL":
                penalty += 15.0
            elif v.severity == "HIGH":
                penalty += 10.0
            elif v.severity == "MEDIUM":
                penalty += 5.0
            else:
                penalty += 2.0

        score = max(0.0, 100.0 - penalty)
        return score
