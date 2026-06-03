import pytest
from unittest.mock import AsyncMock, MagicMock

from plasmaagent.ai.suggestions.engine import SuggestionEngine


class TestSuggestionEngineHelpers:
    def setup_method(self):
        self.db = MagicMock()
        self.engine = SuggestionEngine(self.db)

    def test_extract_commands_none(self):
        assert self.engine._extract_commands(None) == []

    def test_extract_commands_empty_dict(self):
        assert self.engine._extract_commands({}) == []

    def test_extract_commands_dict_with_commands(self):
        payload = {"commands": ["echo hello", "ls -la"]}
        result = self.engine._extract_commands(payload)
        assert result == ["echo hello", "ls -la"]

    def test_extract_commands_json_string(self):
        payload = '{"commands": ["echo hello", "pwd"]}'
        result = self.engine._extract_commands(payload)
        assert result == ["echo hello", "pwd"]

    def test_extract_commands_invalid_json(self):
        assert self.engine._extract_commands("not json") == []

    def test_extract_commands_empty_list(self):
        assert self.engine._extract_commands({"commands": []}) == []

    def test_extract_commands_filters_none(self):
        payload = {"commands": ["echo", None, "ls", ""]}
        result = self.engine._extract_commands(payload)
        assert result == ["echo", "ls"]

    def test_extract_commands_converts_to_str(self):
        payload = {"commands": [123, True, "echo"]}
        result = self.engine._extract_commands(payload)
        assert result == ["123", "True", "echo"]

    def test_normalize_simple_command(self):
        assert self.engine._normalize_command("echo hello") == "echo"

    def test_normalize_command_with_quotes(self):
        assert self.engine._normalize_command('echo "hello world"') == "echo"

    def test_normalize_command_whitespace(self):
        assert self.engine._normalize_command("  ls   -la  ") == "ls"

    def test_normalize_empty_command(self):
        assert self.engine._normalize_command("") == ""

    def test_normalize_path_command(self):
        assert self.engine._normalize_command("/usr/bin/python script.py") == "/usr/bin/python"


class TestSuggestionEngineSuspiciousPatterns:
    def setup_method(self):
        self.db = MagicMock()
        self.engine = SuggestionEngine(self.db)

    def test_detects_rm_rf_root(self):
        import re
        assert any(
            re.search(p, "rm -rf /", re.IGNORECASE)
            for p in self.engine.SUSPICIOUS_PATTERNS
        )

    def test_detects_format_drive(self):
        import re
        assert any(
            re.search(p, "format C:", re.IGNORECASE)
            for p in self.engine.SUSPICIOUS_PATTERNS
        )

    def test_detects_drop_database(self):
        import re
        assert any(
            re.search(p, "DROP DATABASE plasma", re.IGNORECASE)
            for p in self.engine.SUSPICIOUS_PATTERNS
        )

    def test_detects_fork_bomb(self):
        import re
        assert any(
            re.search(p, ":() { :|:& };", re.IGNORECASE)
            for p in self.engine.SUSPICIOUS_PATTERNS
        )

    def test_detects_fork_bomb_variant(self):
        import re
        assert any(
            re.search(p, ":(){ :|: &};", re.IGNORECASE)
            for p in self.engine.SUSPICIOUS_PATTERNS
        )

    def test_detects_del_system(self):
        import re
        assert any(
            re.search(p, "del /s /q C:\\Windows", re.IGNORECASE)
            for p in self.engine.SUSPICIOUS_PATTERNS
        )

    def test_detects_drop_all_tables(self):
        import re
        assert any(
            re.search(p, "DROP TABLE *", re.IGNORECASE)
            for p in self.engine.SUSPICIOUS_PATTERNS
        )

    def test_detects_shutdown(self):
        import re
        assert any(
            re.search(p, "shutdown -h now", re.IGNORECASE)
            for p in self.engine.SUSPICIOUS_PATTERNS
        )

    def test_normal_command_not_flagged(self):
        import re
        cmd = "echo hello world"
        flagged = any(
            re.search(p, cmd, re.IGNORECASE)
            for p in self.engine.SUSPICIOUS_PATTERNS
        )
        assert flagged is False

    def test_safe_rm_not_flagged(self):
        import re
        cmd = "rm -rf ./build"
        flagged = any(
            re.search(p, cmd, re.IGNORECASE)
            for p in self.engine.SUSPICIOUS_PATTERNS
        )
        assert flagged is False


class TestSuggestionEngineThresholds:
    def setup_method(self):
        self.db = MagicMock()
        self.engine = SuggestionEngine(self.db)

    def test_anomaly_threshold_is_positive(self):
        assert self.engine.ANOMALY_COMMANDS_THRESHOLD > 0

    def test_long_command_threshold_is_positive(self):
        assert self.engine.LONG_COMMAND_THRESHOLD > 0

    def test_slow_execution_threshold_reasonable(self):
        assert self.engine.SLOW_EXECUTION_MS >= 1000

    def test_high_failure_rate_bounded(self):
        assert 0.0 < self.engine.HIGH_FAILURE_RATE < 1.0

    def test_suspicious_patterns_not_empty(self):
        assert len(self.engine.SUSPICIOUS_PATTERNS) > 0
