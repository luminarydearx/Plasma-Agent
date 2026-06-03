import pytest
from plasmaagent.ai.providers.rule_based import (
    RuleBasedProvider,
    _sanitize_db_name,
    _sanitize_path,
    _sanitize_drive,
    _sanitize_git_args,
)
from plasmaagent.ai.models import TaskGenerationRequest


class TestSanitizeDbName:
    def test_valid_name_unchanged(self):
        assert _sanitize_db_name("plasmaagent") == "plasmaagent"

    def test_valid_with_underscore(self):
        assert _sanitize_db_name("my_database") == "my_database"

    def test_valid_with_dash(self):
        assert _sanitize_db_name("my-database") == "my-database"

    def test_empty_returns_default(self):
        assert _sanitize_db_name("") == "plasmaagent"

    def test_special_chars_stripped(self):
        result = _sanitize_db_name("db'; DROP TABLE tasks;--")
        assert "'" not in result
        assert ";" not in result
        assert " " not in result

    def test_sql_injection_chars_removed(self):
        result = _sanitize_db_name("test' OR '1'='1")
        assert "'" not in result
        assert "=" not in result
        assert " " not in result

    def test_very_long_truncated(self):
        long_name = "a" * 200
        result = _sanitize_db_name(long_name)
        assert len(result) <= 63

    def test_only_special_chars_returns_default(self):
        assert _sanitize_db_name("!@#$%^&*()") == "plasmaagent"


class TestSanitizePath:
    def test_valid_windows_path(self):
        assert _sanitize_path("C:\\Temp") == "C:\\Temp"

    def test_valid_with_subfolder(self):
        assert _sanitize_path("C:\\Users\\Dearly\\Temp") == "C:\\Users\\Dearly\\Temp"

    def test_empty_returns_default(self):
        assert _sanitize_path("") == "C:\\Temp"

    def test_path_with_shell_injection_rejected(self):
        result = _sanitize_path("C:\\Temp && rm -rf /")
        assert "rm -rf" not in result
        assert "&&" not in result

    def test_path_with_command_substitution_rejected(self):
        result = _sanitize_path("C:\\Temp$(whoami)")
        assert "whoami" not in result
        assert "$(" not in result

    def test_very_long_path_truncated(self):
        long_path = "C:\\" + "a" * 1000
        result = _sanitize_path(long_path)
        assert len(result) <= 500


class TestSanitizeDrive:
    def test_valid_single_letter(self):
        assert _sanitize_drive("C") == "C"

    def test_lowercase_converted_to_upper(self):
        assert _sanitize_drive("d") == "D"

    def test_empty_returns_default(self):
        assert _sanitize_drive("") == "C"

    def test_multiple_chars_returns_default(self):
        assert _sanitize_drive("CD") == "C"

    def test_non_alpha_returns_default(self):
        assert _sanitize_drive("1") == "C"
        assert _sanitize_drive("!") == "C"


class TestSanitizeGitArgs:
    def test_empty_string(self):
        assert _sanitize_git_args("") == ""

    def test_simple_args(self):
        assert _sanitize_git_args("main") == "main"
        assert _sanitize_git_args("origin main") == "origin main"

    def test_semicolon_rejected(self):
        assert _sanitize_git_args("main; rm -rf /") == ""

    def test_and_operator_rejected(self):
        assert _sanitize_git_args("main && evil") == ""

    def test_or_operator_rejected(self):
        assert _sanitize_git_args("main || evil") == ""

    def test_pipe_rejected(self):
        assert _sanitize_git_args("main | evil") == ""

    def test_backtick_rejected(self):
        assert _sanitize_git_args("main`whoami`") == ""

    def test_dollar_paren_rejected(self):
        assert _sanitize_git_args("main$(whoami)") == ""

    def test_redirect_rejected(self):
        assert _sanitize_git_args("main > file") == ""
        assert _sanitize_git_args("main < file") == ""

    def test_null_byte_rejected(self):
        assert _sanitize_git_args("main\x00evil") == ""

    def test_very_long_truncated(self):
        long_args = "a" * 500
        result = _sanitize_git_args(long_args)
        assert len(result) <= 200


class TestRuleBasedProviderEmptyInput:
    def setup_method(self):
        self.provider = RuleBasedProvider()

    def test_empty_string_returns_no_tasks(self):
        request = TaskGenerationRequest(natural_language="", context={})
        response = self.provider.generate_tasks(request)
        assert response.tasks == []

    def test_whitespace_only_returns_no_tasks(self):
        request = TaskGenerationRequest(natural_language="   \t\n  ", context={})
        response = self.provider.generate_tasks(request)
        assert response.tasks == []

    def test_oversized_input_returns_no_tasks(self):
        huge = "backup database " + ("x" * 15000)
        request = TaskGenerationRequest(natural_language=huge, context={})
        response = self.provider.generate_tasks(request)
        assert response.tasks == []


class TestRuleBasedProviderSanitization:
    def setup_method(self):
        self.provider = RuleBasedProvider()

    def test_backup_with_injection_in_db_name(self):
        request = TaskGenerationRequest(
            natural_language="backup database plasmaagent'; DROP TABLE tasks;--",
            context={},
        )
        response = self.provider.generate_tasks(request)
        if response.tasks:
            task = response.tasks[0]
            for cmd in task.commands:
                assert "DROP TABLE" not in cmd
                assert "'; " not in cmd

    def test_cleanup_with_injection_in_path(self):
        request = TaskGenerationRequest(
            natural_language="cleanup files in C:\\Temp && rm -rf /",
            context={},
        )
        response = self.provider.generate_tasks(request)
        if response.tasks:
            task = response.tasks[0]
            for cmd in task.commands:
                assert "rm -rf" not in cmd
                assert "&&" not in cmd

    def test_git_commit_with_injection_in_message(self):
        request = TaskGenerationRequest(
            natural_language="git commit with message \"test\" && evil",
            context={},
        )
        response = self.provider.generate_tasks(request)
        if response.tasks:
            task = response.tasks[0]
            for cmd in task.commands:
                assert "&&" not in cmd
                assert "evil" not in cmd


class TestRuleBasedProviderPerformance:
    def setup_method(self):
        self.provider = RuleBasedProvider()

    def test_empty_input_fast(self):
        request = TaskGenerationRequest(natural_language="", context={})
        response = self.provider.generate_tasks(request)
        assert response.total_time_ms < 100

    def test_oversized_input_fast(self):
        huge = "x" * 15000
        request = TaskGenerationRequest(natural_language=huge, context={})
        response = self.provider.generate_tasks(request)
        assert response.total_time_ms < 100

    def test_valid_input_fast(self):
        request = TaskGenerationRequest(
            natural_language="backup database postgresql plasmaagent",
            context={},
        )
        response = self.provider.generate_tasks(request)
        assert response.total_time_ms < 100
        assert len(response.tasks) == 1
