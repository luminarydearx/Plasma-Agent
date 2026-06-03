from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


CRON_FIELD_RANGES = {
    "minute": (0, 59),
    "hour": (0, 23),
    "day": (1, 31),
    "month": (1, 12),
    "weekday": (0, 6),
}

SPECIAL_EXPRESSIONS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


class CronExpression(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    minute: str = "*"
    hour: str = "*"
    day: str = "*"
    month: str = "*"
    weekday: str = "*"
    raw_expression: str = ""

    @field_validator("minute")
    @classmethod
    def _validate_minute(cls, v: str) -> str:
        CronParser._validate_field(v, "minute")
        return v

    @field_validator("hour")
    @classmethod
    def _validate_hour(cls, v: str) -> str:
        CronParser._validate_field(v, "hour")
        return v

    @field_validator("day")
    @classmethod
    def _validate_day(cls, v: str) -> str:
        CronParser._validate_field(v, "day")
        return v

    @field_validator("month")
    @classmethod
    def _validate_month(cls, v: str) -> str:
        CronParser._validate_field(v, "month")
        return v

    @field_validator("weekday")
    @classmethod
    def _validate_weekday(cls, v: str) -> str:
        CronParser._validate_field(v, "weekday")
        return v

    def matches(self, dt: datetime) -> bool:
        # Python weekday: Monday=0, Sunday=6
        # Cron weekday: Sunday=0, Saturday=6
        # Convert: cron_weekday = (python_weekday + 1) % 7
        cron_weekday = (dt.weekday() + 1) % 7
        
        return (
            CronParser._field_matches(self.minute, dt.minute, "minute")
            and CronParser._field_matches(self.hour, dt.hour, "hour")
            and CronParser._field_matches(self.day, dt.day, "day")
            and CronParser._field_matches(self.month, dt.month, "month")
            and CronParser._field_matches(self.weekday, cron_weekday, "weekday")
        )

    def next_run(self, after: Optional[datetime] = None) -> datetime:
        if after is None:
            after = datetime.now()
        
        # Start from the next minute
        current = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
        
        # Search for up to 1 year
        max_iterations = 525600  # minutes in a year
        for _ in range(max_iterations):
            if self.matches(current):
                return current
            
            current += timedelta(minutes=1)
        
        raise ValueError(f"Could not find next run time after {after}")


class CronParser:
    @staticmethod
    def parse(expression: str) -> CronExpression:
        expression = expression.strip()
        
        if expression.startswith("@"):
            if expression not in SPECIAL_EXPRESSIONS:
                raise ValueError(f"Unknown special expression: {expression}")
            expression = SPECIAL_EXPRESSIONS[expression]
        
        parts = expression.split()
        if len(parts) != 5:
            raise ValueError(
                f"Cron expression must have 5 fields, got {len(parts)}: {expression}"
            )
        
        return CronExpression(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            weekday=parts[4],
            raw_expression=expression,
        )

    @staticmethod
    def _validate_field(field: str, field_name: str) -> None:
        if field == "*":
            return
        
        min_val, max_val = CRON_FIELD_RANGES[field_name]
        
        for part in field.split(","):
            if "/" in part:
                range_part, step = part.split("/", 1)
                CronParser._validate_range(range_part, field_name, min_val, max_val)
                step_val = int(step)
                if step_val < 1:
                    raise ValueError(f"Step must be >= 1, got {step_val}")
            elif "-" in part:
                CronParser._validate_range(part, field_name, min_val, max_val)
            else:
                val = int(part)
                if not (min_val <= val <= max_val):
                    raise ValueError(
                        f"Value {val} out of range [{min_val}-{max_val}] for {field_name}"
                    )

    @staticmethod
    def _validate_range(range_str: str, field_name: str, min_val: int, max_val: int) -> None:
        if range_str == "*":
            return
        
        if "-" in range_str:
            start, end = range_str.split("-", 1)
            start_val = int(start)
            end_val = int(end)
            
            if not (min_val <= start_val <= max_val):
                raise ValueError(
                    f"Range start {start_val} out of range [{min_val}-{max_val}] for {field_name}"
                )
            if not (min_val <= end_val <= max_val):
                raise ValueError(
                    f"Range end {end_val} out of range [{min_val}-{max_val}] for {field_name}"
                )
            if start_val > end_val:
                raise ValueError(
                    f"Range start {start_val} > end {end_val} for {field_name}"
                )
        else:
            val = int(range_str)
            if not (min_val <= val <= max_val):
                raise ValueError(
                    f"Value {val} out of range [{min_val}-{max_val}] for {field_name}"
                )

    @staticmethod
    def _field_matches(field: str, value: int, field_name: str) -> bool:
        if field == "*":
            return True
        
        for part in field.split(","):
            if CronParser._part_matches(part, value, field_name):
                return True
        
        return False

    @staticmethod
    def _part_matches(part: str, value: int, field_name: str) -> bool:
        if "/" in part:
            range_part, step = part.split("/", 1)
            step_val = int(step)
            
            if range_part == "*":
                min_val, _ = CRON_FIELD_RANGES[field_name]
                return (value - min_val) % step_val == 0
            elif "-" in range_part:
                start, end = range_part.split("-", 1)
                start_val = int(start)
                end_val = int(end)
                return start_val <= value <= end_val and (value - start_val) % step_val == 0
            else:
                start_val = int(range_part)
                return value >= start_val and (value - start_val) % step_val == 0
        
        elif "-" in part:
            start, end = part.split("-", 1)
            return int(start) <= value <= int(end)
        
        else:
            return int(part) == value
