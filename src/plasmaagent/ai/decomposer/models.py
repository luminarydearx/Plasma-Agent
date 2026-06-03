from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    MIXED = "mixed"


class SubTask(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str = Field(..., min_length=1, max_length=32)
    natural_language: str = Field(..., min_length=1, max_length=2000)
    depends_on: List[str] = Field(default_factory=list)
    parallel_group: int = Field(default=0, ge=0)
    priority: int = Field(default=0, ge=0, le=10)

    def depends_on_task(self, other: SubTask) -> bool:
        return other.task_id in self.depends_on


class DecomposedTask(BaseModel):
    model_config = ConfigDict(frozen=True)

    original_input: str = Field(..., min_length=1, max_length=10000)
    sub_tasks: List[SubTask] = Field(default_factory=list)
    execution_mode: ExecutionMode = Field(default=ExecutionMode.SEQUENTIAL)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    decomposition_time_ms: float = Field(default=0.0, ge=0.0)
    total_parallel_groups: int = Field(default=0, ge=0)

    @property
    def is_single_task(self) -> bool:
        return len(self.sub_tasks) <= 1

    @property
    def has_dependencies(self) -> bool:
        return any(len(t.depends_on) > 0 for t in self.sub_tasks)

    def get_tasks_in_group(self, group: int) -> List[SubTask]:
        return [t for t in self.sub_tasks if t.parallel_group == group]

    def get_execution_order(self) -> List[List[str]]:
        groups: dict[int, List[str]] = {}
        for t in self.sub_tasks:
            groups.setdefault(t.parallel_group, []).append(t.task_id)
        return [groups[k] for k in sorted(groups.keys())]

    def validate_dependencies(self) -> bool:
        seen: set[str] = set()
        for t in self.sub_tasks:
            for dep in t.depends_on:
                if dep not in seen:
                    return False
            seen.add(t.task_id)
        return True

    def detect_cycle(self) -> Optional[str]:
        visited: set[str] = set()
        in_stack: set[str] = set()
        task_map = {t.task_id: t for t in self.sub_tasks}

        def visit(task_id: str) -> Optional[str]:
            if task_id in in_stack:
                return task_id
            if task_id in visited:
                return None
            visited.add(task_id)
            in_stack.add(task_id)
            for dep in task_map[task_id].depends_on:
                if dep in task_map:
                    cycle = visit(dep)
                    if cycle:
                        return cycle
            in_stack.remove(task_id)
            return None

        for t in self.sub_tasks:
            cycle = visit(t.task_id)
            if cycle:
                return cycle
        return None
