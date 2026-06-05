from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from uuid import UUID
from enum import Enum


class MemoryType(str, Enum):
    CONVERSATION = "conversation"
    PATTERN = "pattern"
    FACT = "fact"
    PREFERENCE = "preference"
    TASK_RESULT = "task_result"


class Memory(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: UUID
    user_id: UUID | None = None
    content: str = Field(min_length=1, max_length=10000)
    embedding: list[float] | None = Field(default=None, max_length=1536)
    metadata: dict = Field(default_factory=dict)
    memory_type: MemoryType
    created_at: datetime
    updated_at: datetime
    similarity: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, v: list[float] | None) -> list[float] | None:
        if v is None:
            return v

        if len(v) == 0:
            raise ValueError("Embedding cannot be empty list")

        if len(v) > 1536:
            raise ValueError(f"Embedding too large: {len(v)} > 1536 dimensions")

        for i, val in enumerate(v):
            if not isinstance(val, (int, float)):
                raise ValueError(f"Embedding[{i}] must be numeric, got {type(val)}")

        return v

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict) -> dict:
        if not isinstance(v, dict):
            raise ValueError(f"Metadata must be dict, got {type(v)}")

        return v


class ConversationMessage(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: UUID
    user_id: UUID
    session_id: UUID
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1, max_length=50000)
    created_at: datetime


class ConversationSession(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: UUID
    user_id: UUID
    title: str | None = Field(default=None, max_length=200)
    message_count: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime


class TaskPattern(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: UUID
    user_id: UUID | None = None
    task_name: str = Field(min_length=1, max_length=200)
    commands: list[str] = Field(min_length=1, max_length=100)
    success_count: int = Field(default=0, ge=0)
    avg_duration_ms: float = Field(default=0.0, ge=0.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime
    updated_at: datetime

    @field_validator("commands")
    @classmethod
    def validate_commands(cls, v: list[str]) -> list[str]:
        if len(v) == 0:
            raise ValueError("Commands list cannot be empty")

        for i, cmd in enumerate(v):
            if not cmd.strip():
                raise ValueError(f"Command[{i}] cannot be empty or whitespace")

        return v


class MemorySearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    memory: Memory
    similarity: float = Field(ge=0.0, le=1.0)


class MemoryStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_memories: int = Field(default=0, ge=0)
    memories_by_type: dict[str, int] = Field(default_factory=dict)
    total_conversations: int = Field(default=0, ge=0)
    total_patterns: int = Field(default=0, ge=0)
    avg_embedding_dimensions: int = Field(default=384, ge=1, le=1536)
