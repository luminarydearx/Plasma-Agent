from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from plasmaagent.ai.templates.learner import (
    COMMAND_SIMILARITY_THRESHOLD,
    MAX_PATTERN_LENGTH,
    MIN_CONFIDENCE,
    MIN_FREQUENCY,
    MIN_SUCCESS_RATE,
    TemplateLearner,
)
from plasmaagent.ai.templates.models import (
    LearnedTemplate,
    LearningReport,
    TemplateCandidate,
    TemplateSource,
)


class TestTemplateLearnerInit:
    def test_init_with_database(self):
        db = MagicMock()
        learner = TemplateLearner(db)
        assert learner._db is db

    def test_init_with_none_assigns_none(self):
        learner = TemplateLearner(None)
        assert learner._db is None


class TestNormalizeCommands:
    def setup_method(self):
        self.learner = TemplateLearner.__new__(TemplateLearner)

    def test_normalize_strips_whitespace(self):
        result = self.learner._normalize_commands(["  echo   hello  world  "])
        assert result == ["echo hello world"]

    def test_normalize_lowercases(self):
        result = self.learner._normalize_commands(["ECHO Hello WORLD"])
        assert result == ["echo hello world"]

    def test_normalize_removes_dates(self):
        result = self.learner._normalize_commands(["backup 2024-06-03"])
        assert result == ["backup <DATE>"]

    def test_normalize_removes_times(self):
        result = self.learner._normalize_commands(["run at 14:30:45"])
        assert result == ["run at <TIME>"]

    def test_normalize_removes_uuids(self):
        result = self.learner._normalize_commands(
            ["delete 550e8400-e29b-41d4-a716-446655440000"]
        )
        assert result == ["delete <UUID>"]

    def test_normalize_removes_numbers(self):
        result = self.learner._normalize_commands(["process 42 items"])
        assert result == ["process <NUM> items"]

    def test_normalize_removes_single_quoted_strings(self):
        result = self.learner._normalize_commands(["echo 'hello world'"])
        assert result == ["echo '<STR>'"]

    def test_normalize_removes_double_quoted_strings(self):
        result = self.learner._normalize_commands(['echo "hello world"'])
        assert result == ['echo "<STR>"']

    def test_normalize_skips_non_string(self):
        result = self.learner._normalize_commands([123, None, "echo test"])
        assert result == ["echo test"]

    def test_normalize_skips_empty_string(self):
        result = self.learner._normalize_commands(["", "   ", "echo ok"])
        assert result == ["echo ok"]

    def test_normalize_skips_very_long_commands(self):
        long_cmd = "echo " + ("x" * MAX_PATTERN_LENGTH)
        result = self.learner._normalize_commands([long_cmd])
        assert result == []

    def test_normalize_handles_multiple_commands(self):
        result = self.learner._normalize_commands(["echo 1", "echo 2", "echo 3"])
        assert result == ["echo <NUM>", "echo <NUM>", "echo <NUM>"]


class TestRemoveVolatileParts:
    def setup_method(self):
        self.learner = TemplateLearner.__new__(TemplateLearner)

    def test_replaces_date_pattern(self):
        result = self.learner._remove_volatile_parts("backup 2024-12-25")
        assert result == "backup <DATE>"

    def test_replaces_time_pattern(self):
        result = self.learner._remove_volatile_parts("run at 23:59:59")
        assert result == "run at <TIME>"

    def test_replaces_uuid_pattern(self):
        result = self.learner._remove_volatile_parts(
            "delete 123e4567-e89b-12d3-a456-426614174000"
        )
        assert result == "delete <UUID>"

    def test_replaces_integer_numbers(self):
        result = self.learner._remove_volatile_parts("process 100 files")
        assert result == "process <NUM> files"

    def test_replaces_single_quoted_strings(self):
        result = self.learner._remove_volatile_parts("greet 'alice'")
        assert result == "greet '<STR>'"

    def test_replaces_double_quoted_strings(self):
        result = self.learner._remove_volatile_parts('greet "bob"')
        assert result == 'greet "<STR>"'

    def test_handles_mixed_volatile_parts(self):
        result = self.learner._remove_volatile_parts(
            "backup 'db' at 2024-01-01 12:00:00 id abc12345-def6-7890-abcd-ef1234567890"
        )
        assert "<STR>" in result
        assert "<DATE>" in result
        assert "<TIME>" in result
        assert "<UUID>" in result

    def test_preserves_regular_text(self):
        result = self.learner._remove_volatile_parts("echo hello world")
        assert result == "echo hello world"

    def test_handles_empty_string(self):
        result = self.learner._remove_volatile_parts("")
        assert result == ""


class TestGroupByCommands:
    def setup_method(self):
        self.learner = TemplateLearner.__new__(TemplateLearner)

    def test_groups_identical_commands(self):
        tasks = [
            {"id": "1", "payload": {"commands": ["echo hello"]}},
            {"id": "2", "payload": {"commands": ["echo hello"]}},
            {"id": "3", "payload": {"commands": ["echo hello"]}},
        ]
        groups = self.learner._group_by_commands(tasks)
        assert len(groups) == 1
        assert len(list(groups.values())[0]) == 3

    def test_separates_different_commands(self):
        tasks = [
            {"id": "1", "payload": {"commands": ["echo hello"]}},
            {"id": "2", "payload": {"commands": ["echo world"]}},
        ]
        groups = self.learner._group_by_commands(tasks)
        assert len(groups) == 2

    def test_ignores_tasks_without_payload(self):
        tasks = [
            {"id": "1", "payload": None},
            {"id": "2", "payload": {"commands": ["echo ok"]}},
        ]
        groups = self.learner._group_by_commands(tasks)
        assert len(groups) == 1

    def test_ignores_tasks_without_commands(self):
        tasks = [
            {"id": "1", "payload": {}},
            {"id": "2", "payload": {"commands": []}},
            {"id": "3", "payload": {"commands": ["echo ok"]}},
        ]
        groups = self.learner._group_by_commands(tasks)
        assert len(groups) == 1

    def test_normalizes_before_grouping(self):
        tasks = [
            {"id": "1", "payload": {"commands": ["echo  1"]}},
            {"id": "2", "payload": {"commands": ["echo  2"]}},
            {"id": "3", "payload": {"commands": ["ECHO 3"]}},
        ]
        groups = self.learner._group_by_commands(tasks)
        assert len(groups) == 1
        assert len(list(groups.values())[0]) == 3

    def test_handles_empty_list(self):
        groups = self.learner._group_by_commands([])
        assert groups == {}

    def test_multi_step_commands_use_separator(self):
        tasks = [
            {"id": "1", "payload": {"commands": ["step1", "step2"]}},
            {"id": "2", "payload": {"commands": ["step1", "step2"]}},
        ]
        groups = self.learner._group_by_commands(tasks)
        assert len(groups) == 1
        key = list(groups.keys())[0]
        assert "||" in key


class TestBuildCandidates:
    def setup_method(self):
        self.learner = TemplateLearner.__new__(TemplateLearner)

    def test_filters_by_min_frequency(self):
        groups = {
            "cmd1": [{"id": "1"}, {"id": "2"}],
            "cmd2": [{"id": "3"}, {"id": "4"}, {"id": "5"}],
        }
        candidates = self.learner._build_candidates(groups, min_frequency=3, min_success_rate=0.7)
        assert len(candidates) == 1
        assert candidates[0].frequency == 3

    def test_creates_candidate_with_correct_fields(self):
        groups = {
            "echo test": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
        }
        candidates = self.learner._build_candidates(groups, min_frequency=3, min_success_rate=0.7)
        assert len(candidates) == 1
        c = candidates[0]
        assert isinstance(c, TemplateCandidate)
        assert c.frequency == 3
        assert c.success_rate == 1.0
        assert c.source == TemplateSource.LEARNED
        assert len(c.commands) == 1
        assert c.commands[0] == "echo test"

    def test_confidence_scales_with_frequency(self):
        groups = {
            "cmd_low": [{"id": str(i)} for i in range(3)],
            "cmd_high": [{"id": str(i)} for i in range(10)],
        }
        candidates = self.learner._build_candidates(groups, min_frequency=3, min_success_rate=0.7)
        assert len(candidates) == 2
        sorted_by_freq = sorted(candidates, key=lambda c: c.frequency)
        assert sorted_by_freq[0].confidence <= sorted_by_freq[1].confidence

    def test_confidence_capped_at_one(self):
        groups = {
            "cmd": [{"id": str(i)} for i in range(100)],
        }
        candidates = self.learner._build_candidates(groups, min_frequency=3, min_success_rate=0.7)
        assert candidates[0].confidence == 1.0

    def test_sample_task_ids_limited_to_ten(self):
        groups = {
            "cmd": [{"id": str(i)} for i in range(50)],
        }
        candidates = self.learner._build_candidates(groups, min_frequency=3, min_success_rate=0.7)
        assert len(candidates[0].sample_task_ids) == 10

    def test_sorted_by_frequency_descending(self):
        groups = {
            "cmd_low": [{"id": str(i)} for i in range(3)],
            "cmd_mid": [{"id": str(i)} for i in range(5)],
            "cmd_high": [{"id": str(i)} for i in range(8)],
        }
        candidates = self.learner._build_candidates(groups, min_frequency=3, min_success_rate=0.7)
        freqs = [c.frequency for c in candidates]
        assert freqs == sorted(freqs, reverse=True)

    def test_empty_groups_returns_empty(self):
        candidates = self.learner._build_candidates({}, min_frequency=3, min_success_rate=0.7)
        assert candidates == []


class TestGeneratePatternName:
    def setup_method(self):
        self.learner = TemplateLearner.__new__(TemplateLearner)

    def test_generates_from_first_command(self):
        name = self.learner._generate_pattern_name(["echo hello world"])
        assert isinstance(name, str)
        assert len(name) > 0

    def test_uses_command_names(self):
        name = self.learner._generate_pattern_name(["echo", "test", "data"])
        assert "echo" in name

    def test_skips_placeholder_tokens(self):
        name = self.learner._generate_pattern_name(["<NUM>", "echo", "hello"])
        assert "<NUM>" not in name

    def test_limits_to_three_parts(self):
        name = self.learner._generate_pattern_name(["echo", "hello", "world", "now"])
        parts = name.split("_")
        assert len(parts) <= 3

    def test_returns_unknown_for_empty(self):
        name = self.learner._generate_pattern_name([])
        assert name == "unknown_pattern"

    def test_returns_pattern_for_all_placeholders(self):
        name = self.learner._generate_pattern_name(["<NUM>", "<DATE>", "<UUID>"])
        assert name == "pattern"

    def test_truncates_long_names(self):
        long_cmd = " ".join(["cmd"] + [f"part{i}" for i in range(50)])
        name = self.learner._generate_pattern_name([long_cmd])
        assert len(name) <= 100

    def test_only_accepts_simple_alphabetic_tokens(self):
        name = self.learner._generate_pattern_name(["echo", "--flag", "123", "hello"])
        assert "echo" in name


class TestTemplateLearnerEdgeCases:
    def setup_method(self):
        self.learner = TemplateLearner.__new__(TemplateLearner)

    def test_constants_are_reasonable(self):
        assert MIN_FREQUENCY >= 1
        assert 0.0 <= MIN_SUCCESS_RATE <= 1.0
        assert 0.0 <= MIN_CONFIDENCE <= 1.0
        assert MAX_PATTERN_LENGTH > 0
        assert 0.0 <= COMMAND_SIMILARITY_THRESHOLD <= 1.0

    def test_normalize_handles_unicode_commands(self):
        result = self.learner._normalize_commands(["echo 日本語テスト"])
        assert len(result) == 1

    def test_normalize_handles_emoji(self):
        result = self.learner._normalize_commands(["echo 🚀 test"])
        assert len(result) == 1

    def test_normalize_handles_sql_injection_attempt(self):
        result = self.learner._normalize_commands(
            ["echo test'; DROP TABLE tasks; --"]
        )
        assert len(result) == 1

    def test_normalize_handles_shell_injection(self):
        result = self.learner._normalize_commands(["echo hello && rm -rf /"])
        assert len(result) == 1

    def test_normalize_handles_null_bytes(self):
        result = self.learner._normalize_commands(["echo\x00test"])
        assert len(result) == 1

    def test_remove_volatile_handles_newlines(self):
        result = self.learner._remove_volatile_parts("echo\nhello\nworld")
        assert isinstance(result, str)

    def test_remove_volatile_handles_tabs(self):
        result = self.learner._remove_volatile_parts("echo\thello\tworld")
        assert isinstance(result, str)

    def test_group_by_commands_with_sql_injection_payload(self):
        tasks = [
            {"id": "1", "payload": {"commands": ["'; DROP TABLE tasks; --"]}},
        ]
        groups = self.learner._group_by_commands(tasks)
        assert len(groups) == 1

    def test_group_by_commands_with_very_large_payload(self):
        large_cmd = "echo " + ("x" * 1000)
        tasks = [{"id": "1", "payload": {"commands": [large_cmd]}}]
        groups = self.learner._group_by_commands(tasks)
        assert len(groups) == 1

    def test_build_candidates_with_malicious_pattern_name(self):
        groups = {
            "'; drop table tasks; --": [{"id": str(i)} for i in range(5)],
        }
        candidates = self.learner._build_candidates(groups, min_frequency=3, min_success_rate=0.7)
        assert isinstance(candidates, list)

    def test_generate_pattern_name_with_special_chars(self):
        name = self.learner._generate_pattern_name(["./script.sh", "--flag=value"])
        assert isinstance(name, str)

    def test_get_learned_templates_returns_list(self):
        result = self.learner.get_learned_templates()
        assert isinstance(result, list)
