import re
from typing import Any
from .models import ErrorAnalysis, ErrorPattern, RecoveryAction, RecoveryActionType


class ErrorAnalyzer:
    DEFAULT_PATTERNS = [
        ErrorPattern(
            name="permission_denied",
            patterns=[
                r"permission denied",
                r"access denied",
                r"operation not permitted",
                r"insufficient privileges",
                r"EACCES"
            ],
            severity="high",
            category="permissions",
            description="Insufficient permissions to execute command"
        ),
        ErrorPattern(
            name="file_not_found",
            patterns=[
                r"no such file or directory",
                r"file not found",
                r"cannot find the file",
                r"ENOENT",
                r"does not exist"
            ],
            severity="medium",
            category="filesystem",
            description="Referenced file or directory does not exist"
        ),
        ErrorPattern(
            name="command_not_found",
            patterns=[
                r"command not found",
                r"is not recognized",
                r"not found",
                r"cannot find command",
                r"executable file not found"
            ],
            severity="high",
            category="command",
            description="Command or executable is not installed or not in PATH"
        ),
        ErrorPattern(
            name="timeout",
            patterns=[
                r"timeout",
                r"timed out",
                r"deadline exceeded",
                r"operation timed out"
            ],
            severity="medium",
            category="timeout",
            description="Operation exceeded time limit"
        ),
        ErrorPattern(
            name="network_error",
            patterns=[
                r"connection refused",
                r"connection reset",
                r"network unreachable",
                r"no route to host",
                r"connection timed out",
                r"dns resolution failed",
                r"could not resolve host"
            ],
            severity="high",
            category="network",
            description="Network connectivity issue"
        ),
        ErrorPattern(
            name="database_error",
            patterns=[
                r"database.*connection.*failed",
                r"could not connect to.*database",
                r"authentication failed",
                r"password authentication failed",
                r"role.*does not exist"
            ],
            severity="critical",
            category="database",
            description="Database connection or authentication issue"
        ),
        ErrorPattern(
            name="disk_space",
            patterns=[
                r"no space left on device",
                r"disk.*full",
                r"insufficient.*space",
                r"ENOSPC"
            ],
            severity="critical",
            category="disk",
            description="Insufficient disk space"
        ),
        ErrorPattern(
            name="invalid_syntax",
            patterns=[
                r"syntax error",
                r"invalid syntax",
                r"unexpected token",
                r"parse error"
            ],
            severity="high",
            category="syntax",
            description="Command syntax is invalid"
        ),
        ErrorPattern(
            name="memory_error",
            patterns=[
                r"out of memory",
                r"cannot allocate memory",
                r"ENOMEM",
                r"insufficient memory"
            ],
            severity="critical",
            category="memory",
            description="Insufficient memory to complete operation"
        ),
        ErrorPattern(
            name="directory_not_empty",
            patterns=[
                r"directory not empty",
                r"directory.*not empty",
                r"ENOTEMPTY"
            ],
            severity="low",
            category="filesystem",
            description="Cannot remove non-empty directory"
        )
    ]
    
    def __init__(self, custom_patterns: list[ErrorPattern] | None = None) -> None:
        self._patterns = list(self.DEFAULT_PATTERNS)
        if custom_patterns:
            self._patterns.extend(custom_patterns)
    
    def analyze(self, error_output: str, exit_code: int = 1) -> ErrorAnalysis:
        truncated_output = error_output[:10000]
        matched_pattern = self._match_pattern(truncated_output)
        recovery_actions = self._generate_actions(matched_pattern, truncated_output, exit_code)
        
        return ErrorAnalysis(
            error_output=truncated_output,
            exit_code=exit_code,
            matched_pattern=matched_pattern,
            recovery_actions=recovery_actions
        )
    
    def _match_pattern(self, error_output: str) -> ErrorPattern | None:
        output_lower = error_output.lower()
        
        for pattern in self._patterns:
            for regex in pattern.patterns:
                if re.search(regex, output_lower, re.IGNORECASE):
                    return pattern
        
        return None
    
    def _generate_actions(
        self,
        pattern: ErrorPattern | None,
        error_output: str,
        exit_code: int
    ) -> list[RecoveryAction]:
        if pattern is None:
            return [
                RecoveryAction(
                    action_type=RecoveryActionType.RETRY,
                    description="Retry the command (may be transient error)",
                    confidence=0.5,
                    metadata={"reason": "unknown_error"}
                )
            ]
        
        actions: list[RecoveryAction] = []
        
        if pattern.name == "permission_denied":
            actions.extend([
                RecoveryAction(
                    action_type=RecoveryActionType.CHECK_PERMISSIONS,
                    description="Check file/directory permissions and adjust if needed",
                    suggested_command="chmod +x <file> or run with elevated privileges",
                    confidence=0.9,
                    metadata={"category": "permissions"}
                ),
                RecoveryAction(
                    action_type=RecoveryActionType.ABORT,
                    description="Abort execution (requires manual permission fix)",
                    confidence=0.8
                )
            ])
        
        elif pattern.name == "file_not_found":
            path_match = re.search(r"['\"]?(/[^\s'\"]+|[A-Za-z]:\\[^\s'\"]+|[^\s'\"]+\.[a-zA-Z0-9]+)['\"]?", error_output)
            suggested_path = path_match.group(1) if path_match else "<path>"
            
            actions.extend([
                RecoveryAction(
                    action_type=RecoveryActionType.CHECK_PATH,
                    description=f"Verify path exists: {suggested_path}",
                    suggested_command=f"ls -la {suggested_path} or dir {suggested_path}",
                    confidence=0.85,
                    metadata={"suggested_path": suggested_path}
                ),
                RecoveryAction(
                    action_type=RecoveryActionType.CREATE_DIRECTORY,
                    description="Create missing directory",
                    suggested_command=f"mkdir -p {suggested_path}",
                    confidence=0.7,
                    metadata={"suggested_path": suggested_path}
                )
            ])
        
        elif pattern.name == "command_not_found":
            cmd_match = re.search(r"([a-zA-Z0-9_\-]+):\s*(?:command not found|is not recognized)", error_output)
            suggested_cmd = cmd_match.group(1) if cmd_match else "<command>"
            
            actions.extend([
                RecoveryAction(
                    action_type=RecoveryActionType.INSTALL_DEPENDENCY,
                    description=f"Install missing command: {suggested_cmd}",
                    suggested_command=f"apt-get install {suggested_cmd} or pip install {suggested_cmd}",
                    confidence=0.8,
                    metadata={"suggested_command": suggested_cmd}
                ),
                RecoveryAction(
                    action_type=RecoveryActionType.SKIP,
                    description="Skip this step and continue",
                    confidence=0.6
                )
            ])
        
        elif pattern.name == "timeout":
            actions.extend([
                RecoveryAction(
                    action_type=RecoveryActionType.RETRY_WITH_BACKOFF,
                    description="Retry with exponential backoff",
                    confidence=0.85,
                    metadata={"backoff_strategy": "exponential"}
                ),
                RecoveryAction(
                    action_type=RecoveryActionType.SKIP,
                    description="Skip this step (may be non-critical)",
                    confidence=0.5
                )
            ])
        
        elif pattern.name == "network_error":
            actions.extend([
                RecoveryAction(
                    action_type=RecoveryActionType.CHECK_NETWORK,
                    description="Check network connectivity",
                    suggested_command="ping google.com or curl -I https://example.com",
                    confidence=0.9,
                    metadata={"category": "network"}
                ),
                RecoveryAction(
                    action_type=RecoveryActionType.RETRY_WITH_BACKOFF,
                    description="Retry after network recovery",
                    confidence=0.75,
                    metadata={"backoff_strategy": "exponential"}
                )
            ])
        
        elif pattern.name == "database_error":
            actions.extend([
                RecoveryAction(
                    action_type=RecoveryActionType.CHECK_DATABASE,
                    description="Check database connection and credentials",
                    suggested_command="psql -U postgres -h localhost -c 'SELECT 1'",
                    confidence=0.9,
                    metadata={"category": "database"}
                ),
                RecoveryAction(
                    action_type=RecoveryActionType.ABORT,
                    description="Abort (database required for operation)",
                    confidence=0.85
                )
            ])
        
        elif pattern.name == "disk_space":
            actions.extend([
                RecoveryAction(
                    action_type=RecoveryActionType.ABORT,
                    description="Abort and free disk space",
                    suggested_command="df -h or du -sh /path/to/check",
                    confidence=0.95,
                    metadata={"category": "disk"}
                )
            ])
        
        elif pattern.name == "invalid_syntax":
            actions.extend([
                RecoveryAction(
                    action_type=RecoveryActionType.FIX_COMMAND,
                    description="Fix command syntax and retry",
                    confidence=0.7,
                    metadata={"category": "syntax"}
                ),
                RecoveryAction(
                    action_type=RecoveryActionType.SKIP,
                    description="Skip malformed command",
                    confidence=0.5
                )
            ])
        
        elif pattern.name == "memory_error":
            actions.extend([
                RecoveryAction(
                    action_type=RecoveryActionType.ABORT,
                    description="Abort and free memory",
                    confidence=0.95,
                    metadata={"category": "memory"}
                )
            ])
        
        elif pattern.name == "directory_not_empty":
            actions.extend([
                RecoveryAction(
                    action_type=RecoveryActionType.FIX_COMMAND,
                    description="Use recursive delete or remove contents first",
                    suggested_command="rm -rf <directory> or find <directory> -delete",
                    confidence=0.85
                ),
                RecoveryAction(
                    action_type=RecoveryActionType.SKIP,
                    description="Skip directory removal",
                    confidence=0.6
                )
            ])
        
        else:
            actions.append(
                RecoveryAction(
                    action_type=RecoveryActionType.RETRY,
                    description="Retry the command",
                    confidence=0.6
                )
            )
        
        return actions
    
    def add_pattern(self, pattern: ErrorPattern) -> None:
        self._patterns.append(pattern)
    
    def remove_pattern(self, pattern_name: str) -> bool:
        original_count = len(self._patterns)
        self._patterns = [p for p in self._patterns if p.name != pattern_name]
        return len(self._patterns) < original_count
    
    def get_pattern(self, pattern_name: str) -> ErrorPattern | None:
        for pattern in self._patterns:
            if pattern.name == pattern_name:
                return pattern
        return None
    
    def list_patterns(self) -> list[ErrorPattern]:
        return list(self._patterns)
    
    @property
    def pattern_count(self) -> int:
        return len(self._patterns)
