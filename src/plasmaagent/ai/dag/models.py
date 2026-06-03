from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class GraphNode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    status: NodeStatus = Field(default=NodeStatus.PENDING)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("node_id")
    @classmethod
    def validate_node_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("node_id cannot be empty")
        if "\x00" in v:
            raise ValueError("node_id cannot contain null bytes")
        if not v.replace("_", "").replace("-", "").replace(".", "").isalnum():
            raise ValueError("node_id must be alphanumeric (underscores, hyphens, and dots allowed)")
        return v.strip()


class GraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    from_node: str = Field(min_length=1, max_length=100)
    to_node: str = Field(min_length=1, max_length=100)

    @field_validator("from_node", "to_node")
    @classmethod
    def validate_node_ref(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("node reference cannot be empty")
        if "\x00" in v:
            raise ValueError("node reference cannot contain null bytes")
        return v.strip()


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ordered_nodes: tuple[str, ...] = Field(default_factory=tuple)
    parallel_groups: tuple[tuple[str, ...], ...] = Field(default_factory=tuple)
    has_cycles: bool = Field(default=False)
    cycle_nodes: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        return not self.has_cycles and len(self.ordered_nodes) > 0

    @property
    def node_count(self) -> int:
        return len(self.ordered_nodes)
