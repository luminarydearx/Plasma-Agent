import pytest

from plasmaagent.ai.recovery import (
    ErrorAnalyzer,
    ErrorAnalysis,
    ErrorPattern,
    RecoveryAction,
    RecoveryActionType,
)


class TestErrorAnalyzerInit:
    def test_init_default_patterns(self):
        analyzer = ErrorAnalyzer()
        assert analyzer.pattern_count == 10

    def test_init_with_custom_patterns(self):
        custom = ErrorPattern(
            name="custom_error",
            patterns=[r"custom.*error"],
            severity="high",
            category="custom",
            description="Custom error pattern",
        )
        analyzer = ErrorAnalyzer(custom_patterns=[custom])
        assert analyzer.pattern_count == 11

    def test_init_with_multiple_custom_patterns(self):
        custom1 = ErrorPattern(
            name="error1",
            patterns=[r"error1"],
            severity="low",
            category="test",
            description="Test 1",
        )
        custom2 = ErrorPattern(
            name="error2",
            patterns=[r"error2"],
            severity="medium",
            category="test",
            description="Test 2",
        )
        analyzer = ErrorAnalyzer(custom_patterns=[custom1, custom2])
        assert analyzer.pattern_count == 12


class TestErrorAnalyzerPatternMatching:
    def test_match_permission_denied(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Permission denied: /etc/passwd")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "permission_denied"

    def test_match_permission_denied_lowercase(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("permission denied")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "permission_denied"

    def test_match_access_denied(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Access denied for user 'postgres'")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "permission_denied"

    def test_match_file_not_found(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("No such file or directory: /tmp/test.txt")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "file_not_found"

    def test_match_file_not_found_windows(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("The system cannot find the file specified")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "file_not_found"

    def test_match_command_not_found(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("bash: git: command not found")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "command_not_found"

    def test_match_command_not_recognized(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("'git' is not recognized as an internal or external command")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "command_not_found"

    def test_match_timeout(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Operation timed out after 30 seconds")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "timeout"

    def test_match_network_error_connection_refused(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Connection refused: localhost:5432")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "network_error"

    def test_match_network_error_dns(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Could not resolve host: example.com")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "network_error"

    def test_match_database_error(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("FATAL: password authentication failed for user 'postgres'")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "database_error"

    def test_match_disk_space(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("No space left on device")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "disk_space"

    def test_match_invalid_syntax(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Syntax error near unexpected token 'fi'")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "invalid_syntax"

    def test_match_memory_error(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Out of memory: Kill process")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "memory_error"

    def test_match_directory_not_empty(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("rm: cannot remove '/tmp/test': Directory not empty")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "directory_not_empty"

    def test_no_match_unknown_error(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Some random error message that doesn't match any pattern")
        assert result.matched_pattern is None


class TestErrorAnalyzerRecoveryActions:
    def test_permission_denied_actions(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Permission denied: /etc/passwd")
        assert len(result.recovery_actions) >= 2
        action_types = [a.action_type for a in result.recovery_actions]
        assert RecoveryActionType.CHECK_PERMISSIONS in action_types
        assert RecoveryActionType.ABORT in action_types

    def test_file_not_found_actions(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("No such file or directory: /tmp/test.txt")
        assert len(result.recovery_actions) >= 2
        action_types = [a.action_type for a in result.recovery_actions]
        assert RecoveryActionType.CHECK_PATH in action_types
        assert RecoveryActionType.CREATE_DIRECTORY in action_types

    def test_file_not_found_extracts_path(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("No such file or directory: '/tmp/missing.txt'")
        path_actions = [a for a in result.recovery_actions if a.action_type == RecoveryActionType.CHECK_PATH]
        assert len(path_actions) > 0
        assert "/tmp/missing.txt" in path_actions[0].suggested_command

    def test_command_not_found_actions(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("bash: git: command not found")
        assert len(result.recovery_actions) >= 2
        action_types = [a.action_type for a in result.recovery_actions]
        assert RecoveryActionType.INSTALL_DEPENDENCY in action_types
        assert RecoveryActionType.SKIP in action_types

    def test_command_not_found_extracts_command(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("bash: git: command not found")
        install_actions = [a for a in result.recovery_actions if a.action_type == RecoveryActionType.INSTALL_DEPENDENCY]
        assert len(install_actions) > 0
        assert "git" in install_actions[0].metadata.get("suggested_command", "")

    def test_timeout_actions(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Operation timed out")
        action_types = [a.action_type for a in result.recovery_actions]
        assert RecoveryActionType.RETRY_WITH_BACKOFF in action_types
        assert RecoveryActionType.SKIP in action_types

    def test_network_error_actions(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Connection refused")
        action_types = [a.action_type for a in result.recovery_actions]
        assert RecoveryActionType.CHECK_NETWORK in action_types
        assert RecoveryActionType.RETRY_WITH_BACKOFF in action_types

    def test_database_error_actions(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("password authentication failed")
        action_types = [a.action_type for a in result.recovery_actions]
        assert RecoveryActionType.CHECK_DATABASE in action_types
        assert RecoveryActionType.ABORT in action_types

    def test_disk_space_actions(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("No space left on device")
        action_types = [a.action_type for a in result.recovery_actions]
        assert RecoveryActionType.ABORT in action_types

    def test_invalid_syntax_actions(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Syntax error")
        action_types = [a.action_type for a in result.recovery_actions]
        assert RecoveryActionType.FIX_COMMAND in action_types
        assert RecoveryActionType.SKIP in action_types

    def test_memory_error_actions(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Out of memory")
        action_types = [a.action_type for a in result.recovery_actions]
        assert RecoveryActionType.ABORT in action_types

    def test_directory_not_empty_actions(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Directory not empty")
        action_types = [a.action_type for a in result.recovery_actions]
        assert RecoveryActionType.FIX_COMMAND in action_types
        assert RecoveryActionType.SKIP in action_types

    def test_unknown_error_default_action(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Some random error")
        assert len(result.recovery_actions) == 1
        assert result.recovery_actions[0].action_type == RecoveryActionType.RETRY
        assert result.recovery_actions[0].confidence == 0.5


class TestErrorAnalyzerBestAction:
    def test_best_action_highest_confidence(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Permission denied")
        best = result.best_action
        assert best is not None
        confidences = [a.confidence for a in result.recovery_actions]
        assert best.confidence == max(confidences)

    def test_best_action_none_when_no_actions(self):
        analysis = ErrorAnalysis(
            error_output="test",
            exit_code=1,
            matched_pattern=None,
            recovery_actions=[],
        )
        assert analysis.best_action is None


class TestErrorAnalyzerCustomPatterns:
    def test_add_pattern(self):
        analyzer = ErrorAnalyzer()
        initial_count = analyzer.pattern_count
        custom = ErrorPattern(
            name="custom",
            patterns=[r"custom.*error"],
            severity="high",
            category="custom",
            description="Custom error",
        )
        analyzer.add_pattern(custom)
        assert analyzer.pattern_count == initial_count + 1

    def test_remove_pattern(self):
        analyzer = ErrorAnalyzer()
        assert analyzer.remove_pattern("permission_denied") is True
        assert analyzer.pattern_count == 9

    def test_remove_nonexistent_pattern(self):
        analyzer = ErrorAnalyzer()
        assert analyzer.remove_pattern("nonexistent") is False
        assert analyzer.pattern_count == 10

    def test_get_pattern_existing(self):
        analyzer = ErrorAnalyzer()
        pattern = analyzer.get_pattern("permission_denied")
        assert pattern is not None
        assert pattern.name == "permission_denied"

    def test_get_pattern_nonexistent(self):
        analyzer = ErrorAnalyzer()
        assert analyzer.get_pattern("nonexistent") is None

    def test_list_patterns(self):
        analyzer = ErrorAnalyzer()
        patterns = analyzer.list_patterns()
        assert len(patterns) == 10
        names = [p.name for p in patterns]
        assert "permission_denied" in names
        assert "file_not_found" in names

    def test_custom_pattern_matching(self):
        custom = ErrorPattern(
            name="api_error",
            patterns=[r"API rate limit exceeded"],
            severity="high",
            category="api",
            description="API rate limit exceeded",
        )
        analyzer = ErrorAnalyzer(custom_patterns=[custom])
        result = analyzer.analyze("API rate limit exceeded for user 123")
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "api_error"


class TestErrorAnalyzerEdgeCases:
    def test_empty_error_output(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("")
        assert result.matched_pattern is None
        assert len(result.recovery_actions) == 1
        assert result.recovery_actions[0].action_type == RecoveryActionType.RETRY

    def test_very_long_error_output(self):
        analyzer = ErrorAnalyzer()
        long_output = "Error: " + "x" * 20000
        result = analyzer.analyze(long_output)
        assert len(result.error_output) <= 10000

    def test_null_byte_in_output(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Error\x00message")
        assert result.error_output == "Error\x00message"

    def test_unicode_error_output(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("エラー: ファイルが見つかりません")
        assert result.matched_pattern is None

    def test_multiline_error_output(self):
        analyzer = ErrorAnalyzer()
        multiline = """
Traceback (most recent call last):
  File "test.py", line 10, in <module>
PermissionError: [Errno 13] Permission denied: '/etc/passwd'
"""
        result = analyzer.analyze(multiline)
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "permission_denied"

    def test_special_chars_in_output(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Error: !@#$%^&*()_+-=[]{}|;':\",./<>?")
        assert result.matched_pattern is None

    def test_exit_code_preserved(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Some error", exit_code=127)
        assert result.exit_code == 127

    def test_exit_code_negative(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze("Killed", exit_code=-9)
        assert result.exit_code == -9


class TestErrorAnalyzerSecurity:
    def test_sql_injection_in_error(self):
        analyzer = ErrorAnalyzer()
        malicious = "Error: '; DROP TABLE tasks; --"
        result = analyzer.analyze(malicious)
        assert result.error_output == malicious

    def test_shell_injection_in_error(self):
        analyzer = ErrorAnalyzer()
        malicious = "Error: value; rm -rf /"
        result = analyzer.analyze(malicious)
        assert result.error_output == malicious

    def test_command_substitution_in_error(self):
        analyzer = ErrorAnalyzer()
        malicious = "Error: $(whoami)"
        result = analyzer.analyze(malicious)
        assert result.error_output == malicious

    def test_path_traversal_in_error(self):
        analyzer = ErrorAnalyzer()
        malicious = "No such file or directory: ../../../../etc/passwd"
        result = analyzer.analyze(malicious)
        assert result.matched_pattern is not None
        assert result.matched_pattern.name == "file_not_found"


class TestErrorAnalysisProperties:
    def test_has_recovery_actions_true(self):
        analysis = ErrorAnalysis(
            error_output="test",
            exit_code=1,
            recovery_actions=[
                RecoveryAction(
                    action_type=RecoveryActionType.RETRY,
                    description="Retry",
                    confidence=0.8,
                )
            ],
        )
        assert analysis.has_recovery_actions is True

    def test_has_recovery_actions_false(self):
        analysis = ErrorAnalysis(
            error_output="test",
            exit_code=1,
            recovery_actions=[],
        )
        assert analysis.has_recovery_actions is False


class TestRecoveryActionProperties:
    def test_is_automatic_retry(self):
        action = RecoveryAction(
            action_type=RecoveryActionType.RETRY,
            description="Retry",
            confidence=0.8,
        )
        assert action.is_automatic is True
        assert action.requires_user_input is False

    def test_is_automatic_skip(self):
        action = RecoveryAction(
            action_type=RecoveryActionType.SKIP,
            description="Skip",
            confidence=0.8,
        )
        assert action.is_automatic is True

    def test_requires_user_input_fix_command(self):
        action = RecoveryAction(
            action_type=RecoveryActionType.FIX_COMMAND,
            description="Fix command",
            confidence=0.8,
        )
        assert action.requires_user_input is True
        assert action.is_automatic is False

    def test_requires_user_input_check_permissions(self):
        action = RecoveryAction(
            action_type=RecoveryActionType.CHECK_PERMISSIONS,
            description="Check permissions",
            confidence=0.8,
        )
        assert action.requires_user_input is True


class TestErrorAnalyzerPerformance:
    def test_analyze_performance_short_output(self):
        analyzer = ErrorAnalyzer()
        output = "Permission denied"
        result = analyzer.analyze(output)
        assert result is not None

    def test_analyze_performance_long_output(self):
        analyzer = ErrorAnalyzer()
        output = "Error: " + "x" * 10000
        result = analyzer.analyze(output)
        assert result is not None

    def test_analyze_performance_many_patterns(self):
        analyzer = ErrorAnalyzer()
        for i in range(50):
            custom = ErrorPattern(
                name=f"pattern_{i}",
                patterns=[f"error_{i}"],
                severity="low",
                category="test",
                description=f"Test pattern {i}",
            )
            analyzer.add_pattern(custom)
        result = analyzer.analyze("Some error message")
        assert result is not None
