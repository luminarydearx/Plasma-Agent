from abc import ABC, abstractmethod
from plasmaagent.ai.models import (
    TaskGenerationRequest,
    TaskGenerationResponse,
    TaskAnalysis,
    ProviderInfo,
)


class LLMProvider(ABC):
    name: str = "base"
    description: str = "Base provider"

    @abstractmethod
    def get_info(self) -> ProviderInfo:
        pass

    @abstractmethod
    def generate_tasks(self, request: TaskGenerationRequest) -> TaskGenerationResponse:
        pass

    @abstractmethod
    def analyze_task(self, task_id: str) -> TaskAnalysis:
        pass

    @abstractmethod
    def suggest_improvements(self, task_id: str) -> list[str]:
        pass

    def supports_generation(self) -> bool:
        return True

    def supports_analysis(self) -> bool:
        return False

    def supports_suggestions(self) -> bool:
        return False
