from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ExecutionContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    task_id: str = Field(..., min_length=1, max_length=36)
    output: str = Field(default="", max_length=100000)
    exit_code: int = Field(default=0, ge=-128, le=255)
    duration_ms: int = Field(default=0, ge=0, le=3600000)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        return self.exit_code == 0
    
    @property
    def failed(self) -> bool:
        return self.exit_code != 0


class SessionContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    session_id: str = Field(..., min_length=1, max_length=36)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    executions: list[ExecutionContext] = Field(default_factory=list)
    variables: dict[str, str] = Field(default_factory=dict)
    
    def get_execution(self, task_id: str) -> ExecutionContext | None:
        for execution in self.executions:
            if execution.task_id == task_id:
                return execution
        return None
    
    @property
    def execution_count(self) -> int:
        return len(self.executions)
    
    @property
    def success_count(self) -> int:
        return sum(1 for e in self.executions if e.success)
    
    @property
    def failure_count(self) -> int:
        return sum(1 for e in self.executions if e.failed)
    
    @property
    def success_rate(self) -> float:
        if self.execution_count == 0:
            return 0.0
        return self.success_count / self.execution_count
