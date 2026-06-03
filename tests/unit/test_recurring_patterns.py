import pytest

from plasmaagent.scheduling.patterns import RecurringPattern, RecurringPatterns


class TestRecurringPatterns:
    def test_every_minute(self):
        result = RecurringPatterns.every_minute()
        assert result == "* * * * *"

    def test_hourly_default(self):
        result = RecurringPatterns.hourly()
        assert result == "0 * * * *"

    def test_hourly_custom_minute(self):
        result = RecurringPatterns.hourly(minute=30)
        assert result == "30 * * * *"

    def test_hourly_invalid_minute(self):
        with pytest.raises(ValueError, match="minute must be between 0 and 59"):
            RecurringPatterns.hourly(minute=60)

        with pytest.raises(ValueError, match="minute must be between 0 and 59"):
            RecurringPatterns.hourly(minute=-1)

    def test_daily_default(self):
        result = RecurringPatterns.daily()
        assert result == "0 0 * * *"

    def test_daily_custom_time(self):
        result = RecurringPatterns.daily(hour=14, minute=30)
        assert result == "30 14 * * *"

    def test_daily_invalid_hour(self):
        with pytest.raises(ValueError, match="hour must be between 0 and 23"):
            RecurringPatterns.daily(hour=24)

    def test_daily_invalid_minute(self):
        with pytest.raises(ValueError, match="minute must be between 0 and 59"):
            RecurringPatterns.daily(minute=60)

    def test_weekly_default(self):
        result = RecurringPatterns.weekly()
        assert result == "0 0 * * 0"

    def test_weekly_custom(self):
        result = RecurringPatterns.weekly(day_of_week=5, hour=18, minute=45)
        assert result == "45 18 * * 5"

    def test_weekly_invalid_day(self):
        with pytest.raises(ValueError, match="day_of_week must be between 0"):
            RecurringPatterns.weekly(day_of_week=7)

    def test_weekly_invalid_hour(self):
        with pytest.raises(ValueError, match="hour must be between 0 and 23"):
            RecurringPatterns.weekly(hour=24)

    def test_monthly_default(self):
        result = RecurringPatterns.monthly()
        assert result == "0 0 1 * *"

    def test_monthly_custom(self):
        result = RecurringPatterns.monthly(day=15, hour=10, minute=30)
        assert result == "30 10 15 * *"

    def test_monthly_invalid_day(self):
        with pytest.raises(ValueError, match="day must be between 1 and 31"):
            RecurringPatterns.monthly(day=0)

        with pytest.raises(ValueError, match="day must be between 1 and 31"):
            RecurringPatterns.monthly(day=32)

    def test_yearly_default(self):
        result = RecurringPatterns.yearly()
        assert result == "0 0 1 1 *"

    def test_yearly_custom(self):
        result = RecurringPatterns.yearly(month=12, day=25, hour=12, minute=0)
        assert result == "0 12 25 12 *"

    def test_yearly_invalid_month(self):
        with pytest.raises(ValueError, match="month must be between 1 and 12"):
            RecurringPatterns.yearly(month=0)

        with pytest.raises(ValueError, match="month must be between 1 and 12"):
            RecurringPatterns.yearly(month=13)

    def test_yearly_invalid_day(self):
        with pytest.raises(ValueError, match="day must be between 1 and 31"):
            RecurringPatterns.yearly(day=0)

    def test_weekdays_default(self):
        result = RecurringPatterns.weekdays()
        assert result == "0 9 * * 1-5"

    def test_weekdays_custom(self):
        result = RecurringPatterns.weekdays(hour=8, minute=30)
        assert result == "30 8 * * 1-5"

    def test_weekdays_invalid_hour(self):
        with pytest.raises(ValueError, match="hour must be between 0 and 23"):
            RecurringPatterns.weekdays(hour=24)

    def test_weekends_default(self):
        result = RecurringPatterns.weekends()
        assert result == "0 10 * * 0,6"

    def test_weekends_custom(self):
        result = RecurringPatterns.weekends(hour=11, minute=15)
        assert result == "15 11 * * 0,6"

    def test_weekends_invalid_hour(self):
        with pytest.raises(ValueError, match="hour must be between 0 and 23"):
            RecurringPatterns.weekends(hour=-1)

    def test_business_hours_default(self):
        result = RecurringPatterns.business_hours()
        assert result == "*/60 9,10,11,12,13,14,15,16 * * 1-5"

    def test_business_hours_custom(self):
        result = RecurringPatterns.business_hours(
            start_hour=8, end_hour=18, interval_minutes=30
        )
        assert result == "*/30 8,9,10,11,12,13,14,15,16,17 * * 1-5"

    def test_business_hours_invalid_start(self):
        with pytest.raises(ValueError, match="start_hour must be between 0 and 23"):
            RecurringPatterns.business_hours(start_hour=24)

    def test_business_hours_invalid_end(self):
        with pytest.raises(ValueError, match="end_hour must be between 0 and 23"):
            RecurringPatterns.business_hours(end_hour=24)

    def test_business_hours_start_after_end(self):
        with pytest.raises(ValueError, match="start_hour must be less than end_hour"):
            RecurringPatterns.business_hours(start_hour=17, end_hour=9)

    def test_business_hours_invalid_interval(self):
        with pytest.raises(ValueError, match="interval_minutes must be between 1 and 60"):
            RecurringPatterns.business_hours(interval_minutes=0)

        with pytest.raises(ValueError, match="interval_minutes must be between 1 and 60"):
            RecurringPatterns.business_hours(interval_minutes=61)

    def test_custom_all_wildcards(self):
        result = RecurringPatterns.custom()
        assert result == "* * * * *"

    def test_custom_specific_values(self):
        result = RecurringPatterns.custom(
            minute="0",
            hour="12",
            day="15",
            month="6",
            day_of_week="1",
        )
        assert result == "0 12 15 6 1"

    def test_custom_ranges(self):
        result = RecurringPatterns.custom(
            minute="*/15",
            hour="9-17",
            day="*",
            month="*",
            day_of_week="1-5",
        )
        assert result == "*/15 9-17 * * 1-5"


class TestRecurringPatternEnum:
    def test_enum_values(self):
        assert RecurringPattern.EVERY_MINUTE == "every_minute"
        assert RecurringPattern.HOURLY == "hourly"
        assert RecurringPattern.DAILY == "daily"
        assert RecurringPattern.WEEKLY == "weekly"
        assert RecurringPattern.MONTHLY == "monthly"
        assert RecurringPattern.YEARLY == "yearly"
        assert RecurringPattern.WEEKDAYS == "weekdays"
        assert RecurringPattern.WEEKENDS == "weekends"

    def test_enum_is_string(self):
        assert isinstance(RecurringPattern.DAILY.value, str)
