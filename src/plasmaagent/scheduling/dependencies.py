from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DependencyType(str, Enum):
    ON_SUCCESS = "on_success"
    ON_FAILURE = "on_failure"
    ON_COMPLETE = "on_complete"


class TaskDependencyBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_task_id: UUID
    target_task_id: UUID
    dependency_type: DependencyType = DependencyType.ON_SUCCESS


class TaskDependencyCreate(TaskDependencyBase):
    pass


class TaskDependency(TaskDependencyBase):
    id: UUID
    created_at: datetime
