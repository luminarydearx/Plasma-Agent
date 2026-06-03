from enum import Enum
from typing import Literal


class RecurringPattern(str, Enum):
    EVERY_MINUTE = "every_minute"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    WEEKDAYS = "weekdays"
    WEEKENDS = "weekends"


class RecurringPatterns:
    @staticmethod
    def every_minute() -> str:
        return "* * * * *"

    @staticmethod
    def hourly(minute: int = 0) -> str:
        if not 0 <= minute <= 59:
            raise ValueError("minute must be between 0 and 59")
        return f"{minute} * * * *"

    @staticmethod
    def daily(hour: int = 0, minute: int = 0) -> str:
        if not 0 <= hour <= 23:
            raise ValueError("hour must be between 0 and 23")
        if not 0 <= minute <= 59:
            raise ValueError("minute must be between 0 and 59")
        return f"{minute} {hour} * * *"

    @staticmethod
    def weekly(
        day_of_week: Literal[0, 1, 2, 3, 4, 5, 6] = 0,
        hour: int = 0,
        minute: int = 0,
    ) -> str:
        if not 0 <= day_of_week <= 6:
            raise ValueError("day_of_week must be between 0 (Monday) and 6 (Sunday)")
        if not 0 <= hour <= 23:
            raise ValueError("hour must be between 0 and 23")
        if not 0 <= minute <= 59:
            raise ValueError("minute must be between 0 and 59")
        return f"{minute} {hour} * * {day_of_week}"

    @staticmethod
    def monthly(
        day: int = 1,
        hour: int = 0,
        minute: int = 0,
    ) -> str:
        if not 1 <= day <= 31:
            raise ValueError("day must be between 1 and 31")
        if not 0 <= hour <= 23:
            raise ValueError("hour must be between 0 and 23")
        if not 0 <= minute <= 59:
            raise ValueError("minute must be between 0 and 59")
        return f"{minute} {hour} {day} * *"

    @staticmethod
    def yearly(
        month: int = 1,
        day: int = 1,
        hour: int = 0,
        minute: int = 0,
    ) -> str:
        if not 1 <= month <= 12:
            raise ValueError("month must be between 1 and 12")
        if not 1 <= day <= 31:
            raise ValueError("day must be between 1 and 31")
        if not 0 <= hour <= 23:
            raise ValueError("hour must be between 0 and 23")
        if not 0 <= minute <= 59:
            raise ValueError("minute must be between 0 and 59")
        return f"{minute} {hour} {day} {month} *"

    @staticmethod
    def weekdays(hour: int = 9, minute: int = 0) -> str:
        if not 0 <= hour <= 23:
            raise ValueError("hour must be between 0 and 23")
        if not 0 <= minute <= 59:
            raise ValueError("minute must be between 0 and 59")
        return f"{minute} {hour} * * 1-5"

    @staticmethod
    def weekends(hour: int = 10, minute: int = 0) -> str:
        if not 0 <= hour <= 23:
            raise ValueError("hour must be between 0 and 23")
        if not 0 <= minute <= 59:
            raise ValueError("minute must be between 0 and 59")
        return f"{minute} {hour} * * 0,6"

    @staticmethod
    def business_hours(
        start_hour: int = 9,
        end_hour: int = 17,
        interval_minutes: int = 60,
    ) -> str:
        if not 0 <= start_hour <= 23:
            raise ValueError("start_hour must be between 0 and 23")
        if not 0 <= end_hour <= 23:
            raise ValueError("end_hour must be between 0 and 23")
        if start_hour >= end_hour:
            raise ValueError("start_hour must be less than end_hour")
        if not 1 <= interval_minutes <= 60:
            raise ValueError("interval_minutes must be between 1 and 60")

        hours = list(range(start_hour, end_hour))
        hours_str = ",".join(str(h) for h in hours)
        return f"*/{interval_minutes} {hours_str} * * 1-5"

    @staticmethod
    def custom(
        minute: str = "*",
        hour: str = "*",
        day: str = "*",
        month: str = "*",
        day_of_week: str = "*",
    ) -> str:
        return f"{minute} {hour} {day} {month} {day_of_week}"
