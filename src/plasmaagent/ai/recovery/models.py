from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class RecoveryActionType(str, Enum):
    RETRY = "retry"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    SKIP = "skip"
    FIX_COMMAND = "fix_command"
    CHECK_PERMISSIONS = "check_permissions"
    CHECK_PATH = "check_path"
    CHECK_NETWORK = "check_network"
    CHECK_DATABASE = "check_database"
    INSTALL_DEPENDENCY = "install_dependency"
    CREATE_DIRECTORY = "create_directory"
    ABORT = "abort"


class ErrorPattern(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    name: str = Field(..., min_length=1, max_length=100)
    patterns: list[str] = Field(..., min_length=1)
    severity: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    category: str = Field(..., min_length=1, max_length=50)
    description: str = Field(default="", max_length=500)


class RecoveryAction(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    action_type: RecoveryActionType
    description: str = Field(..., min_length=1, max_length=500)
    suggested_command: str | None = Field(default=None, max_length=1000)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    @property
    def is_automatic(self) -> bool:
        return self.action_type in (
            RecoveryActionType.RETRY,
            RecoveryActionType.RETRY_WITH_BACKOFF,
            RecoveryActionType.SKIP
        )
    
    @property
    def requires_user_input(self) -> bool:
        return self.action_type in (
            RecoveryActionType.FIX_COMMAND,
            RecoveryActionType.CHECK_PERMISSIONS,
            RecoveryActionType.CHECK_PATH
        )


class ErrorAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    error_output: str = Field(..., max_length=10000)
    exit_code: int = Field(default=1, ge=-128, le=255)
    matched_pattern: ErrorPattern | None = None
    recovery_actions: list[RecoveryAction] = Field(default_factory=list)
    
    @property
    def has_recovery_actions(self) -> bool:
        return len(self.recovery_actions) > 0
    
    @property
    def best_action(self) -> RecoveryAction | None:
        if not self.recovery_actions:
            return None
        return max(self.recovery_actions, key=lambda a: a.confidence)
