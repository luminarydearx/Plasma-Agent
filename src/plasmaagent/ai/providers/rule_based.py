import re
import time
from typing import Optional
from plasmaagent.ai.providers.base import LLMProvider
from plasmaagent.ai.models import (
    TaskGenerationRequest,
    TaskGenerationResponse,
    GeneratedTask,
    TaskComplexity,
    TaskAnalysis,
    ProviderInfo,
)

MAX_NL_INPUT_LENGTH = 10000
MAX_COMMAND_LENGTH = 4000
SAFE_DB_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
SAFE_PATH_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\\/:\.\s]+$")


def _sanitize_db_name(name: str) -> str:
    if not name:
        return "plasmaagent"
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "", name)[:63]
    return cleaned or "plasmaagent"


def _sanitize_path(path: str) -> str:
    if not path:
        return "C:\\Temp"
    if not SAFE_PATH_PATTERN.match(path):
        return "C:\\Temp"
    return path[:500]


def _sanitize_drive(drive: str) -> str:
    if drive and len(drive) == 1 and drive.isalpha():
        return drive.upper()
    return "C"


def _sanitize_git_args(args: str) -> str:
    if not args:
        return ""
    dangerous = [";", "&&", "||", "|", "`", "$(", ">", "<", "\x00"]
    for d in dangerous:
        if d in args:
            return ""
    return args[:200]


class RuleBasedProvider(LLMProvider):
    name = "rule_based"
    description = "Rule-based task generation using pattern matching and templates"

    def __init__(self) -> None:
        self._patterns = self._build_patterns()

    def _build_patterns(self) -> dict:
        return {
            "backup_database": {
                "regex": r"(backup|dump)\s+(?:(postgresql|postgres|mysql|sqlite)\s+)?(database|db)(?:\s+(\w+))?|(backup|dump)\s+(database|db)\s+(postgresql|postgres|mysql|sqlite)?\s*(\w+)?",
                "template": self._generate_backup_database,
                "confidence": 0.95,
            },
            "cleanup_files": {
                "regex": r"(clean|cleanup|delete|remove)\s+(temp|temporary|old)?\s*files?\s*(in|from)?\s*(.+)?",
                "template": self._generate_cleanup_files,
                "confidence": 0.90,
            },
            "disk_monitoring": {
                "regex": r"(check|monitor|show)\s+(disk|drive)\s*(space|usage)?",
                "template": self._generate_disk_monitoring,
                "confidence": 0.85,
            },
            "git_operations": {
                "regex": r"(git)\s+(commit|push|pull|status|add|checkout)\s*(.+)?|(commit|push|pull)\s+(.+)",
                "template": self._generate_git_operations,
                "confidence": 0.80,
            },
            "system_info": {
                "regex": r"(show|get|display|check)\s+(system|cpu|memory|ram)\s+(info|information|usage)?",
                "template": self._generate_system_info,
                "confidence": 0.85,
            },
        }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            description=self.description,
            is_active=True,
            supports_generation=True,
            supports_analysis=False,
            supports_suggestions=False,
        )

    def generate_tasks(self, request: TaskGenerationRequest) -> TaskGenerationResponse:
        start_time = time.time()

        if request.natural_language is None:
            return TaskGenerationResponse(
                tasks=[],
                provider_used=self.name,
                parsing_time_ms=0.0,
                generation_time_ms=0.0,
                total_time_ms=(time.time() - start_time) * 1000,
            )

        if len(request.natural_language) > MAX_NL_INPUT_LENGTH:
            return TaskGenerationResponse(
                tasks=[],
                provider_used=self.name,
                parsing_time_ms=0.0,
                generation_time_ms=0.0,
                total_time_ms=(time.time() - start_time) * 1000,
            )

        input_text = request.natural_language.lower().strip()
        if not input_text:
            return TaskGenerationResponse(
                tasks=[],
                provider_used=self.name,
                parsing_time_ms=0.0,
                generation_time_ms=0.0,
                total_time_ms=(time.time() - start_time) * 1000,
            )

        best_match = None
        best_confidence = 0.0
        extracted_params = {}

        for pattern_name, pattern_config in self._patterns.items():
            regex = pattern_config["regex"]
            try:
                match = re.search(regex, input_text, re.IGNORECASE)
            except re.error:
                continue

            if match:
                confidence = pattern_config["confidence"]
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = pattern_name
                    extracted_params = self._extract_parameters(
                        match, pattern_name, request.natural_language
                    )

        parsing_time = (time.time() - start_time) * 1000
        generation_start = time.time()

        tasks = []
        if best_match:
            try:
                template_func = self._patterns[best_match]["template"]
                generated = template_func(extracted_params, request.context or {})
                generated.confidence = best_confidence
                generated.template_used = best_match
                generated.parameters = extracted_params
                tasks.append(generated)
            except Exception:
                pass

        generation_time = (time.time() - generation_start) * 1000
        total_time = (time.time() - start_time) * 1000

        return TaskGenerationResponse(
            tasks=tasks,
            provider_used=self.name,
            parsing_time_ms=parsing_time,
            generation_time_ms=generation_time,
            total_time_ms=total_time,
        )

    def analyze_task(self, task_id: str) -> TaskAnalysis:
        return TaskAnalysis(
            task_id=task_id,
            success_rate=1.0,
            avg_duration_ms=0.0,
            failure_patterns=[],
            suggestions=["Rule-based provider does not support analysis yet"],
        )

    def suggest_improvements(self, task_id: str) -> list[str]:
        return ["Rule-based provider does not support suggestions yet"]

    def _extract_parameters(
        self, match: re.Match, pattern_name: str, original_input: str
    ) -> dict:
        params = {}
        groups = match.groups()

        if pattern_name == "backup_database":
            if groups[1]:
                params["db_type"] = groups[1]
                params["db_name"] = groups[3] if groups[3] else "plasmaagent"
            elif len(groups) >= 8:
                params["db_type"] = groups[6] if groups[6] else "postgresql"
                params["db_name"] = groups[7] if groups[7] else "plasmaagent"
            else:
                params["db_type"] = "postgresql"
                params["db_name"] = "plasmaagent"

        elif pattern_name == "cleanup_files":
            path_match = re.search(r"(?:in|from)\s+(.+)$", original_input, re.IGNORECASE)
            if path_match:
                params["path"] = path_match.group(1).strip()
            else:
                params["path"] = "C:\\Temp"

        elif pattern_name == "git_operations":
            if groups[1]:
                params["operation"] = groups[1]
                params["args"] = groups[2] if groups[2] else ""
            elif groups[3]:
                params["operation"] = groups[3]
                params["args"] = groups[4] if groups[4] else ""
            else:
                params["operation"] = "status"
                params["args"] = ""

        elif pattern_name == "disk_monitoring":
            drive_match = re.search(r"([A-Z]):", original_input, re.IGNORECASE)
            if drive_match:
                params["drive"] = drive_match.group(1).upper()
            else:
                params["drive"] = "C"

        return params

    def _generate_backup_database(
        self, params: dict, context: dict
    ) -> GeneratedTask:
        db_type = params.get("db_type", "postgresql")
        if db_type not in ("postgresql", "postgres", "mysql", "sqlite"):
            db_type = "postgresql"
        db_name = _sanitize_db_name(params.get("db_name", "plasmaagent"))
        backup_path = _sanitize_path(context.get("backup_path", "D:\\backups"))

        if db_type in ("postgresql", "postgres"):
            commands = [
                f'pg_dump -U postgres -F c {db_name} > "{backup_path}\\backup_$(Get-Date -Format yyyyMMdd_HHmmss).sql"',
                f'powershell -Command "if ((Get-Item {backup_path}\\backup_*.sql).Length -eq 0) {{ exit 1 }}"',
            ]
        elif db_type == "mysql":
            commands = [
                f'mysqldump -u root {db_name} > "{backup_path}\\backup_$(Get-Date -Format yyyyMMdd_HHmmss).sql"',
            ]
        else:
            commands = [f'echo "Backup {db_type} not supported yet"']

        commands = [c[:MAX_COMMAND_LENGTH] for c in commands]

        return GeneratedTask(
            name=f"Backup {db_type.title()} Database: {db_name}",
            description=f"Backup {db_name} database to {backup_path}",
            commands=commands,
            complexity=TaskComplexity.SIMPLE,
        )

    def _generate_cleanup_files(self, params: dict, context: dict) -> GeneratedTask:
        path = _sanitize_path(params.get("path", "C:\\Temp"))
        days_old_raw = context.get("days_old", 7)
        try:
            days_old = max(0, min(365, int(days_old_raw)))
        except (TypeError, ValueError):
            days_old = 7

        commands = [
            f'powershell -Command "Get-ChildItem {path} -Recurse | Where-Object {{$_.LastWriteTime -lt (Get-Date).AddDays(-{days_old})}} | Remove-Item -Force"',
            f'echo "Cleanup completed for {path}"',
        ]
        commands = [c[:MAX_COMMAND_LENGTH] for c in commands]

        return GeneratedTask(
            name=f"Cleanup Old Files in {path}",
            description=f"Remove files older than {days_old} days from {path}",
            commands=commands,
            complexity=TaskComplexity.SIMPLE,
        )

    def _generate_disk_monitoring(
        self, params: dict, context: dict
    ) -> GeneratedTask:
        threshold_raw = context.get("threshold_gb", 10)
        try:
            threshold_gb = max(0, min(10000, int(threshold_raw)))
        except (TypeError, ValueError):
            threshold_gb = 10
        drive = _sanitize_drive(params.get("drive", context.get("drive", "C")))

        commands = [
            f'powershell -Command "$free = (Get-PSDrive {drive}).Free / 1GB; Write-Host \'Free space: $free GB\'; if ($free -lt {threshold_gb}) {{ Write-Error \'Low disk space!\' }}"',
        ]
        commands = [c[:MAX_COMMAND_LENGTH] for c in commands]

        return GeneratedTask(
            name=f"Monitor Disk Space ({drive}:)",
            description=f"Check disk space on {drive}: and alert if below {threshold_gb}GB",
            commands=commands,
            complexity=TaskComplexity.SIMPLE,
        )

    def _generate_git_operations(
        self, params: dict, context: dict
    ) -> GeneratedTask:
        operation = params.get("operation", "status")
        if not operation or not isinstance(operation, str):
            operation = "status"

        op_lower = operation.lower()
        if op_lower not in ("commit", "push", "pull", "status", "add", "checkout"):
            op_lower = "status"

        args = _sanitize_git_args(params.get("args", ""))

        if "commit" in op_lower:
            message = context.get("message", args if args else "Auto commit")
            if not isinstance(message, str) or not message:
                message = "Auto commit"
            message = re.sub(r'[`$\\"]', "", message)[:200]
            commands = [
                "git add .",
                f'git commit -m "{message}"',
            ]
        elif "push" in op_lower:
            commands = ["git push" + (f" {args}" if args else "")]
        elif "pull" in op_lower:
            commands = ["git pull" + (f" {args}" if args else "")]
        elif "add" in op_lower:
            commands = [f"git add {args if args else '.'}"]
        elif "checkout" in op_lower:
            commands = [f"git checkout {args if args else 'main'}"]
        else:
            commands = ["git status"]

        commands = [c[:MAX_COMMAND_LENGTH] for c in commands]

        return GeneratedTask(
            name=f"Git: {op_lower.title()}",
            description=f"Execute git {op_lower}",
            commands=commands,
            complexity=TaskComplexity.SIMPLE,
        )

    def _generate_system_info(self, params: dict, context: dict) -> GeneratedTask:
        commands = [
            'powershell -Command "Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber"',
            'powershell -Command "Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors"',
            'powershell -Command "Get-CimInstance Win32_PhysicalMemory | Measure-Object Capacity -Sum | Select-Object @{Name=\'TotalRAM_GB\';Expression={[math]::Round($_.Sum/1GB,2)}}"',
        ]
        commands = [c[:MAX_COMMAND_LENGTH] for c in commands]

        return GeneratedTask(
            name="System Information",
            description="Display system information (OS, CPU, RAM)",
            commands=commands,
            complexity=TaskComplexity.SIMPLE,
        )


from plasmaagent.ai.providers.registry import register_provider

register_provider("rule_based", RuleBasedProvider)
