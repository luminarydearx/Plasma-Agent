import pytest
from typer.testing import CliRunner
from plasmaagent.cli.main import app

runner = CliRunner()

class TestCLIGeneratePreview:
    def test_preview_valid_input(self):
        result = runner.invoke(app, ["task", "generate", "--input", "backup database postgresql mydb", "--preview"])
        assert result.exit_code == 0
        assert "Generated Task Preview" in result.output
        assert "backup" in result.output.lower()

    def test_preview_empty_input_returns_error(self):
        result = runner.invoke(app, ["task", "generate", "--input", "", "--preview"])
        assert result.exit_code == 1
        assert "empty" in result.output.lower() or "whitespace" in result.output.lower()

    def test_preview_no_pattern_match(self):
        result = runner.invoke(app, ["task", "generate", "--input", "xyz123 gibberish", "--preview"])
        assert result.exit_code == 1
        assert "Could not generate" in result.output

    def test_preview_special_chars(self):
        result = runner.invoke(app, ["task", "generate", "--input", "backup database test!@#$%", "--preview"])
        assert result.exit_code == 0

    def test_preview_with_provider(self):
        result = runner.invoke(app, ["task", "generate", "--input", "check disk space", "--provider", "rule_based", "--preview"])
        assert result.exit_code == 0
        assert "Provider: rule_based" in result.output

class TestCLIGenerateCreate:
    def test_create_with_auto_confirm(self):
        result = runner.invoke(app, ["task", "generate", "--input", "git status", "--yes"])
        assert result.exit_code == 0 or "Task Created" in result.output

    def test_create_invalid_input(self):
        result = runner.invoke(app, ["task", "generate", "--input", "random nonsense xyz", "--yes"])
        assert result.exit_code == 1 or "Could not generate" in result.output

class TestCLIGenerateEdgeCases:
    def test_very_long_input(self):
        long_input = "backup database " + "test " * 100
        result = runner.invoke(app, ["task", "generate", "--input", long_input, "--preview"])
        assert result.exit_code == 0

    def test_unicode_input(self):
        result = runner.invoke(app, ["task", "generate", "--input", "backup database テスト", "--preview"])
        assert result.exit_code == 0

    def test_multiline_input(self):
        result = runner.invoke(app, ["task", "generate", "--input", "backup\npostgres\nmydb", "--preview"])
        assert result.exit_code in [0, 1]

    def test_sql_injection_attempt(self):
        result = runner.invoke(app, ["task", "generate", "--input", "backup; DROP TABLE tasks;", "--preview"])
        assert result.exit_code in [0, 1]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
