from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ConditionOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    LT = "lt"
    LE = "le"
    GT = "gt"
    GE = "ge"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


class Condition(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    variable: str = Field(..., min_length=1, max_length=200)
    operator: ConditionOperator
    value: str | int | float | bool = Field(...)
    negate: bool = Field(default=False)


class ConditionalStep(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    step_id: str = Field(..., min_length=1, max_length=100)
    condition: Condition
    then_action: str = Field(default="execute", min_length=1, max_length=50)
    else_action: Optional[str] = Field(default=None, max_length=50)
    else_step_id: Optional[str] = Field(default=None, max_length=100)
