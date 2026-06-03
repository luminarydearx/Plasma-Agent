from decimal import Decimal
from typing import Optional
from plasmaagent.ai.providers import get_provider, list_providers
from plasmaagent.ai.models import (
    TaskGenerationRequest,
    TaskGenerationResponse,
    GeneratedTask,
)
from plasmaagent.core.database import Database
from plasmaagent.models.task import TaskCreate, TaskPayload
from plasmaagent.services.task_service import TaskService
from plasmaagent.services.template_metrics_service import TemplateMetricsService


class TaskGeneratorService:
    def __init__(self, db: Database):
        self._db = db
        self._task_service = TaskService(db)
        self._metrics_service = TemplateMetricsService(db)

    async def generate_from_natural_language(
        self,
        natural_language: str,
        provider_name: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> TaskGenerationResponse:
        provider = get_provider(provider_name)
        
        request = TaskGenerationRequest(
            natural_language=natural_language,
            context=context or {},
        )
        
        response = provider.generate_tasks(request)
        
        await self._record_generation_metrics(
            response=response,
            provider_name=provider_name or provider.name,
        )
        
        return response

    async def _record_generation_metrics(
        self,
        response: TaskGenerationResponse,
        provider_name: str,
    ) -> None:
        if not response.tasks:
            return
        
        for task in response.tasks:
            if not task.template_used:
                continue
            
            try:
                await self._metrics_service.record_usage(
                    template_name=task.template_used,
                    pattern=response.provider_used,
                    confidence=Decimal(str(task.confidence)),
                    generation_time_ms=int(response.total_time_ms),
                    success=True,
                )
            except Exception:
                pass

    async def create_task_from_generation(
        self,
        generated: GeneratedTask,
    ) -> str:
        payload = TaskPayload(
            commands=generated.commands,
            env={},
            cwd=None,
        )

        task_create = TaskCreate(
            name=generated.name,
            description=generated.description,
            payload=payload,
        )

        task = await self._task_service.create_task(task_create)
        return str(task.id)

    def get_available_providers(self) -> list[str]:
        return list_providers()

    def preview_task(self, generated: GeneratedTask) -> str:
        lines = [
            f"Name: {generated.name}",
            f"Description: {generated.description}",
            f"Complexity: {generated.complexity.value}",
            f"Confidence: {generated.confidence:.0%}",
            "",
            "Commands:",
        ]
        
        for i, cmd in enumerate(generated.commands, 1):
            lines.append(f"  {i}. {cmd}")
        
        if generated.schedule:
            lines.append(f"\nSchedule: {generated.schedule}")
        
        if generated.template_used:
            lines.append(f"\nTemplate: {generated.template_used}")
        
        return "\n".join(lines)
