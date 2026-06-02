import re
import time
from typing import Optional, Callable
from plasmaagent.ai.providers.base import LLMProvider
from plasmaagent.ai.models import (
    TaskGenerationRequest,
    TaskGenerationResponse,
    GeneratedTask,
    TaskComplexity,
    TaskAnalysis,
    ProviderInfo,
)


class RuleBasedProvider(LLMProvider):
    name = "rule_based"
    description = "Rule-based task generation using pattern matching and templates"

    def __init__(self) -> None:
        self._patterns = self._build_patterns()

    def _build_patterns(self) -> dict:
        return {
            "backup_database": {
                "regex": r"(backup|dump)\s+(database|db)\s+(postgresql|postgres|mysql|sqlite)?\s*(\w+)?",
                "template": self._generate_backup_database,
                "confidence": 0.95,
            },
            "cleanup_files": {
                "regex": r"(clean|delete|remove)\s+(temp|temporary|old)\s+files?\s+(in|from)?\s*(.+)?",
                "template": self._generate_cleanup_files,
                "confidence": 0.90,
            },
            "disk_monitoring": {
                "regex": r"(check|monitor)\s+disk\s+(space|usage)",
                "template": self._generate_disk_monitoring,
                "confidence": 0.85,
            },
            "git_operations": {
                "regex": r"(git|commit|push|pull)\s+(.+)",
                "template": self._generate_git_operations,
                "confidence": 0.80,
            },
            "system_info": {
                "regex": r"(show|get|display)\s+(system|cpu|memory|ram)\s+(info|information|usage)",
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
        
        input_text = request.natural_language.lower().strip()
        best_match = None
        best_confidence = 0.0
        extracted_params = {}

        for pattern_name, pattern_config in self._patterns.items():
            regex = pattern_config["regex"]
            match = re.search(regex, input_text, re.IGNORECASE)
            
            if match:
                confidence = pattern_config["confidence"]
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = pattern_name
                    extracted_params = self._extract_parameters(match, pattern_name)

        parsing_time = (time.time() - start_time) * 1000
        generation_start = time.time()

        tasks = []
        if best_match:
            template_func = self._patterns[best_match]["template"]
            generated = template_func(extracted_params, request.context)
            generated.confidence = best_confidence
            generated.template_used = best_match
            generated.parameters = extracted_params
            tasks.append(generated)

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

    def _extract_parameters(self, match: re.Match, pattern_name: str) -> dict:
        params = {}
        groups = match.groups()

        if pattern_name == "backup_database":
            if len(groups) >= 4:
                params["db_type"] = groups[2] if groups[2] else "postgresql"
                params["db_name"] = groups[3] if groups[3] else "plasmaagent"
        
        elif pattern_name == "cleanup_files":
            if len(groups) >= 4:
                params["path"] = groups[3] if groups[3] else "C:\\Temp"
        
        elif pattern_name == "git_operations":
            if len(groups) >= 2:
                params["operation"] = groups[1] if groups[1] else "status"

        return params

    def _generate_backup_database(
        self, params: dict, context: dict
    ) -> GeneratedTask:
        db_type = params.get("db_type", "postgresql")
        db_name = params.get("db_name", "plasmaagent")
        backup_path = context.get("backup_path", "D:\\backups")

        if db_type in ["postgresql", "postgres"]:
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

        return GeneratedTask(
            name=f"Backup {db_type.title()} Database: {db_name}",
            description=f"Backup {db_name} database to {backup_path}",
            commands=commands,
            complexity=TaskComplexity.SIMPLE,
        )

    def _generate_cleanup_files(self, params: dict, context: dict) -> GeneratedTask:
        path = params.get("path", "C:\\Temp")
        days_old = context.get("days_old", 7)

        commands = [
            f'powershell -Command "Get-ChildItem {path} -Recurse | Where-Object {{$_.LastWriteTime -lt (Get-Date).AddDays(-{days_old})}} | Remove-Item -Force"',
            f'echo "Cleanup completed for {path}"',
        ]

        return GeneratedTask(
            name=f"Cleanup Old Files in {path}",
            description=f"Remove files older than {days_old} days from {path}",
            commands=commands,
            complexity=TaskComplexity.SIMPLE,
        )

    def _generate_disk_monitoring(
        self, params: dict, context: dict
    ) -> GeneratedTask:
        threshold_gb = context.get("threshold_gb", 10)
        drive = context.get("drive", "C")

        commands = [
            f'powershell -Command "$free = (Get-PSDrive {drive}).Free / 1GB; Write-Host \'Free space: $free GB\'; if ($free -lt {threshold_gb}) {{ Write-Error \'Low disk space!\' }}"',
        ]

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
        
        if "commit" in operation.lower():
            message = context.get("message", "Auto commit")
            commands = [
                "git add .",
                f'git commit -m "{message}"',
            ]
        elif "push" in operation.lower():
            commands = ["git push"]
        elif "pull" in operation.lower():
            commands = ["git pull"]
        else:
            commands = ["git status"]

        return GeneratedTask(
            name=f"Git: {operation.title()}",
            description=f"Execute git {operation}",
            commands=commands,
            complexity=TaskComplexity.SIMPLE,
        )

    def _generate_system_info(self, params: dict, context: dict) -> GeneratedTask:
        commands = [
            'powershell -Command "Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber"',
            'powershell -Command "Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors"',
            'powershell -Command "Get-CimInstance Win32_PhysicalMemory | Measure-Object Capacity -Sum | Select-Object @{Name=\'TotalRAM_GB\';Expression={[math]::Round($_.Sum/1GB,2)}}"',
        ]

        return GeneratedTask(
            name="System Information",
            description="Display system information (OS, CPU, RAM)",
            commands=commands,
            complexity=TaskComplexity.SIMPLE,
        )


from plasmaagent.ai.providers.registry import register_provider

register_provider("rule_based", RuleBasedProvider)
