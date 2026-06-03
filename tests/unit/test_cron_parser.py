"""Comprehensive tests for CronParser and CronExpression."""

import pytest
from datetime import datetime

from plasmaagent.scheduling.cron_parser import CronExpression, CronParser


class TestCronParserBasic:
    """Test basic cron expression parsing."""

    def test_parse_simple_expression(self) -> None:
        cron = CronParser.parse("* * * * *")
        assert cron.minute == "*"
        assert cron.hour == "*"
        assert cron.day == "*"
        assert cron.month == "*"
        assert cron.weekday == "*"

    def test_parse_specific_values(self) -> None:
        cron = CronParser.parse("30 14 1 6 3")
        assert cron.minute == "30"
        assert cron.hour == "14"
        assert cron.day == "1"
        assert cron.month == "6"
        assert cron.weekday == "3"

    def test_parse_with_ranges(self) -> None:
        cron = CronParser.parse("0-30 9-17 * * 1-5")
        assert cron.minute == "0-30"
        assert cron.hour == "9-17"
        assert cron.weekday == "1-5"

    def test_parse_with_steps(self) -> None:
        cron = CronParser.parse("*/15 */2 * * *")
        assert cron.minute == "*/15"
        assert cron.hour == "*/2"

    def test_parse_with_lists(self) -> None:
        cron = CronParser.parse("0,15,30,45 9,12,15 * * *")
        assert cron.minute == "0,15,30,45"
        assert cron.hour == "9,12,15"

    def test_parse_complex_expression(self) -> None:
        cron = CronParser.parse("0,30 9-17/2 1,15 1-6 1-5")
        assert cron.minute == "0,30"
        assert cron.hour == "9-17/2"
        assert cron.day == "1,15"
        assert cron.month == "1-6"
        assert cron.weekday == "1-5"


class TestCronParserSpecialExpressions:
    """Test special cron expressions (@daily, @hourly, etc)."""

    def test_parse_daily(self) -> None:
        cron = CronParser.parse("@daily")
        assert cron.minute == "0"
        assert cron.hour == "0"
        assert cron.day == "*"
        assert cron.month == "*"
        assert cron.weekday == "*"

    def test_parse_hourly(self) -> None:
        cron = CronParser.parse("@hourly")
        assert cron.minute == "0"
        assert cron.hour == "*"

    def test_parse_weekly(self) -> None:
        cron = CronParser.parse("@weekly")
        assert cron.minute == "0"
        assert cron.hour == "0"
        assert cron.weekday == "0"

    def test_parse_monthly(self) -> None:
        cron = CronParser.parse("@monthly")
        assert cron.minute == "0"
        assert cron.hour == "0"
        assert cron.day == "1"

    def test_parse_yearly(self) -> None:
        cron = CronParser.parse("@yearly")
        assert cron.minute == "0"
        assert cron.hour == "0"
        assert cron.day == "1"
        assert cron.month == "1"

    def test_parse_annually(self) -> None:
        cron = CronParser.parse("@annually")
        assert cron.minute == "0"
        assert cron.hour == "0"
        assert cron.day == "1"
        assert cron.month == "1"

    def test_parse_midnight(self) -> None:
        cron = CronParser.parse("@midnight")
        assert cron.minute == "0"
        assert cron.hour == "0"

    def test_invalid_special_expression(self) -> None:
        with pytest.raises(ValueError, match="Unknown special expression"):
            CronParser.parse("@invalid")


class TestCronParserValidation:
    """Test cron expression validation."""

    def test_invalid_field_count(self) -> None:
        with pytest.raises(ValueError, match="must have 5 fields"):
            CronParser.parse("* * *")

    def test_minute_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            CronParser.parse("60 * * * *")

    def test_hour_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            CronParser.parse("* 24 * * *")

    def test_day_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            CronParser.parse("* * 32 * *")

    def test_month_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            CronParser.parse("* * * 13 *")

    def test_weekday_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            CronParser.parse("* * * * 7")

    def test_invalid_range(self) -> None:
        with pytest.raises(ValueError, match="Range start.*> end"):
            CronParser.parse("30-10 * * * *")

    def test_invalid_step(self) -> None:
        with pytest.raises(ValueError, match="Step must be >= 1"):
            CronParser.parse("*/0 * * * *")

    def test_negative_value(self) -> None:
        with pytest.raises(ValueError):
            CronParser.parse("-1 * * * *")


class TestCronExpressionMatches:
    """Test cron expression matching."""

    def test_matches_every_minute(self) -> None:
        cron = CronParser.parse("* * * * *")
        dt = datetime(2026, 6, 3, 14, 30)
        assert cron.matches(dt) is True

    def test_matches_specific_minute(self) -> None:
        cron = CronParser.parse("30 * * * *")
        assert cron.matches(datetime(2026, 6, 3, 14, 30)) is True
        assert cron.matches(datetime(2026, 6, 3, 14, 31)) is False

    def test_matches_specific_hour(self) -> None:
        cron = CronParser.parse("0 14 * * *")
        assert cron.matches(datetime(2026, 6, 3, 14, 0)) is True
        assert cron.matches(datetime(2026, 6, 3, 15, 0)) is False

    def test_matches_range(self) -> None:
        cron = CronParser.parse("0 9-17 * * *")
        assert cron.matches(datetime(2026, 6, 3, 9, 0)) is True
        assert cron.matches(datetime(2026, 6, 3, 14, 0)) is True
        assert cron.matches(datetime(2026, 6, 3, 17, 0)) is True
        assert cron.matches(datetime(2026, 6, 3, 18, 0)) is False

    def test_matches_step(self) -> None:
        cron = CronParser.parse("*/15 * * * *")
        assert cron.matches(datetime(2026, 6, 3, 14, 0)) is True
        assert cron.matches(datetime(2026, 6, 3, 14, 15)) is True
        assert cron.matches(datetime(2026, 6, 3, 14, 30)) is True
        assert cron.matches(datetime(2026, 6, 3, 14, 45)) is True
        assert cron.matches(datetime(2026, 6, 3, 14, 10)) is False

    def test_matches_list(self) -> None:
        cron = CronParser.parse("0,15,30,45 * * * *")
        assert cron.matches(datetime(2026, 6, 3, 14, 0)) is True
        assert cron.matches(datetime(2026, 6, 3, 14, 15)) is True
        assert cron.matches(datetime(2026, 6, 3, 14, 30)) is True
        assert cron.matches(datetime(2026, 6, 3, 14, 45)) is True
        assert cron.matches(datetime(2026, 6, 3, 14, 10)) is False

    def test_matches_weekday(self) -> None:
        # Cron weekday: 0=Sunday, 1=Monday, ..., 6=Saturday
        # 2026-06-01 is Monday (cron weekday=1)
        cron = CronParser.parse("0 9 * * 1-5")  # Monday to Friday (cron: 1-5)
        assert cron.matches(datetime(2026, 6, 1, 9, 0)) is True  # Monday
        assert cron.matches(datetime(2026, 6, 2, 9, 0)) is True  # Tuesday
        assert cron.matches(datetime(2026, 6, 6, 9, 0)) is False  # Saturday (cron=6)
        assert cron.matches(datetime(2026, 6, 7, 9, 0)) is False  # Sunday (cron=0)

    def test_matches_complex_expression(self) -> None:
        cron = CronParser.parse("0,30 9-17/2 1,15 * *")
        assert cron.matches(datetime(2026, 6, 1, 9, 0)) is True
        assert cron.matches(datetime(2026, 6, 1, 9, 30)) is True
        assert cron.matches(datetime(2026, 6, 1, 11, 0)) is True
        assert cron.matches(datetime(2026, 6, 15, 13, 30)) is True
        assert cron.matches(datetime(2026, 6, 2, 9, 0)) is False  # Wrong day
        assert cron.matches(datetime(2026, 6, 1, 10, 0)) is False  # Wrong hour


class TestCronExpressionNextRun:
    """Test next run time calculation."""

    def test_next_run_every_minute(self) -> None:
        cron = CronParser.parse("* * * * *")
        after = datetime(2026, 6, 3, 14, 30, 45)
        next_run = cron.next_run(after)
        assert next_run == datetime(2026, 6, 3, 14, 31)

    def test_next_run_specific_minute(self) -> None:
        cron = CronParser.parse("45 * * * *")
        after = datetime(2026, 6, 3, 14, 30)
        next_run = cron.next_run(after)
        assert next_run == datetime(2026, 6, 3, 14, 45)

    def test_next_run_next_hour(self) -> None:
        cron = CronParser.parse("0 * * * *")
        after = datetime(2026, 6, 3, 14, 30)
        next_run = cron.next_run(after)
        assert next_run == datetime(2026, 6, 3, 15, 0)

    def test_next_run_next_day(self) -> None:
        cron = CronParser.parse("0 0 * * *")
        after = datetime(2026, 6, 3, 14, 30)
        next_run = cron.next_run(after)
        assert next_run == datetime(2026, 6, 4, 0, 0)

    def test_next_run_specific_day(self) -> None:
        cron = CronParser.parse("0 0 15 * *")
        after = datetime(2026, 6, 3, 14, 30)
        next_run = cron.next_run(after)
        assert next_run == datetime(2026, 6, 15, 0, 0)

    def test_next_run_specific_weekday(self) -> None:
        # Cron weekday: 1=Monday
        cron = CronParser.parse("0 9 * * 1")  # Monday
        after = datetime(2026, 6, 3, 14, 30)  # Wednesday
        next_run = cron.next_run(after)
        # Next Monday is 2026-06-08
        assert next_run == datetime(2026, 6, 8, 9, 0)

    def test_next_run_with_step(self) -> None:
        cron = CronParser.parse("*/15 * * * *")
        after = datetime(2026, 6, 3, 14, 32)
        next_run = cron.next_run(after)
        assert next_run == datetime(2026, 6, 3, 14, 45)


class TestCronExpressionEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_expression(self) -> None:
        with pytest.raises(ValueError, match="must have 5 fields"):
            CronParser.parse("")

    def test_whitespace_handling(self) -> None:
        cron = CronParser.parse("  * * * * *  ")
        assert cron.minute == "*"

    def test_frozen_model(self) -> None:
        cron = CronParser.parse("* * * * *")
        with pytest.raises(Exception):  # ValidationError
            cron.minute = "0"

    def test_invalid_characters(self) -> None:
        with pytest.raises(ValueError):
            CronParser.parse("a * * * *")

    def test_very_large_step(self) -> None:
        cron = CronParser.parse("*/100 * * * *")
        # Should parse but won't match anything
        assert cron.minute == "*/100"


class TestCronExpressionPerformance:
    """Test performance of cron operations."""

    def test_parse_performance(self) -> None:
        import time
        start = time.monotonic()
        for _ in range(1000):
            CronParser.parse("0,30 9-17/2 1,15 1-6 1-5")
        duration = time.monotonic() - start
        assert duration < 1.0  # Should parse 1000 expressions in < 1 second

    def test_matches_performance(self) -> None:
        import time
        cron = CronParser.parse("0,30 9-17/2 1,15 1-6 1-5")
        dt = datetime(2026, 6, 15, 11, 30)
        start = time.monotonic()
        for _ in range(10000):
            cron.matches(dt)
        duration = time.monotonic() - start
        assert duration < 1.0  # Should match 10000 times in < 1 second

    def test_next_run_performance(self) -> None:
        import time
        cron = CronParser.parse("0 0 * * *")
        after = datetime(2026, 6, 3, 14, 30)
        start = time.monotonic()
        for _ in range(100):
            cron.next_run(after)
        duration = time.monotonic() - start
        assert duration < 2.0  # Should calculate 100 next runs in < 2 seconds
