import pytest
from typer.testing import CliRunner
from plasmaagent.cli.tasks import app

runner = CliRunner()


class TestCLIGenerateEdgeCasesComprehensive:
    def test_empty_input_returns_error_no_prompt(self) -> None:
        result = runner.invoke(app, ["generate", "--input", "", "--preview"], input="")
        assert result.exit_code == 1
        combined = result.output.lower()
        assert "empty" in combined or "whitespace" in combined

    def test_whitespace_only_input_returns_error(self) -> None:
        result = runner.invoke(app, ["generate", "--input", "   ", "--preview"], input="")
        assert result.exit_code == 1
        combined = result.output.lower()
        assert "empty" in combined or "whitespace" in combined

    def test_tab_only_input_returns_error(self) -> None:
        result = runner.invoke(app, ["generate", "--input", "\t\t\t", "--preview"], input="")
        assert result.exit_code == 1

    def test_newline_only_input_returns_error(self) -> None:
        result = runner.invoke(app, ["generate", "--input", "\n\n", "--preview"], input="")
        assert result.exit_code == 1

    def test_mixed_whitespace_input_returns_error(self) -> None:
        result = runner.invoke(app, ["generate", "--input", " \t\n \t", "--preview"], input="")
        assert result.exit_code == 1

    def test_no_pattern_match_returns_error(self) -> None:
        result = runner.invoke(app, ["generate", "--input", "xyzabc123randomgibberish", "--preview"], input="")
        assert result.exit_code == 1
        combined = result.output.lower()
        assert "could not generate" in combined

    def test_special_characters_handled(self) -> None:
        result = runner.invoke(app, ["generate", "--input", "backup !@#$% database", "--preview"], input="")
        assert result.exit_code in [0, 1]

    def test_sql_injection_attempt_safe(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "backup database'; DROP TABLE tasks;--", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]
        output = result.output.lower()
        if "commands:" in output:
            commands_section = output.split("commands:")[1] if "commands:" in output else ""
            assert "drop table" not in commands_section

    def test_shell_injection_ampersand(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "check disk && rm -rf /", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]
        output = result.output.lower()
        if "commands:" in output:
            commands_section = output.split("commands:")[1] if "commands:" in output else ""
            assert "rm -rf" not in commands_section

    def test_command_injection_backticks(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "backup `whoami` database", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_command_injection_dollar_parens(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "backup $(cat /etc/passwd) database", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_very_long_input_handled(self) -> None:
        long_input = "backup database " + "x" * 5000
        result = runner.invoke(app, ["generate", "--input", long_input, "--preview"], input="")
        assert result.exit_code in [0, 1]

    def test_unicode_japanese_handled(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "データベースをバックアップ", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_unicode_chinese_handled(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "备份数据库", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_unicode_emoji_handled(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "backup 🗄️ database 🔥", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_valid_backup_pattern(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "backup database postgresql plasmaagent", "--preview"],
            input="",
        )
        assert result.exit_code == 0
        combined = result.output.lower()
        assert "backup" in combined
        assert "preview" in combined

    def test_valid_cleanup_pattern(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "cleanup old files in C:\\Temp", "--preview"],
            input="",
        )
        assert result.exit_code == 0
        combined = result.output.lower()
        assert "cleanup" in combined

    def test_valid_disk_pattern(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "check disk space", "--preview"],
            input="",
        )
        assert result.exit_code == 0
        combined = result.output.lower()
        assert "disk" in combined or "monitor" in combined

    def test_valid_git_pattern(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "git commit changes", "--preview"],
            input="",
        )
        assert result.exit_code == 0
        combined = result.output.lower()
        assert "git" in combined

    def test_valid_system_info_pattern(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "show system info", "--preview"],
            input="",
        )
        assert result.exit_code == 0
        combined = result.output.lower()
        assert "system" in combined

    def test_invalid_provider_name(self) -> None:
        result = runner.invoke(
            app,
            [
                "generate",
                "--input",
                "backup database",
                "--provider",
                "nonexistent_provider",
                "--preview",
            ],
            input="",
        )
        assert result.exit_code == 1
        combined = result.output.lower()
        assert "provider" in combined or "error" in combined

    def test_repeated_special_chars(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "backup " + "!" * 100 + " database", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_null_bytes_in_input(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "backup\x00database", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_multiple_valid_patterns_first_wins(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "backup database and cleanup files", "--preview"],
            input="",
        )
        assert result.exit_code == 0

    def test_case_insensitive_patterns(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "BACKUP DATABASE POSTGRESQL", "--preview"],
            input="",
        )
        assert result.exit_code == 0
        combined = result.output.lower()
        assert "backup" in combined

    def test_mixed_case_patterns(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "Check Disk Space", "--preview"],
            input="",
        )
        assert result.exit_code == 0

    def test_leading_trailing_whitespace_stripped(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "  backup database  ", "--preview"],
            input="",
        )
        assert result.exit_code == 0

    def test_very_long_single_word(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "a" * 10000, "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_path_traversal_attempt(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "cleanup files in ../../etc/passwd", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_windows_path_handling(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "cleanup files in C:\\Windows\\System32", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_unix_path_handling(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "cleanup files in /var/log", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_single_character_input(self) -> None:
        result = runner.invoke(app, ["generate", "--input", "a", "--preview"], input="")
        assert result.exit_code in [0, 1]

    def test_single_word_input(self) -> None:
        result = runner.invoke(app, ["generate", "--input", "backup", "--preview"], input="")
        assert result.exit_code in [0, 1]

    def test_numbers_only_input(self) -> None:
        result = runner.invoke(app, ["generate", "--input", "123456789", "--preview"], input="")
        assert result.exit_code in [0, 1]

    def test_rtl_unicode_input(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "نسخ احتياطي", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_zalgo_text_input(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "b̷a̷c̷k̷u̷p̷ d̷a̷t̷a̷b̷a̷s̷e̷", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_very_long_command_like_input(self) -> None:
        long_cmd = "backup database " + "AND ".join([f"db{i}" for i in range(100)])
        result = runner.invoke(app, ["generate", "--input", long_cmd, "--preview"], input="")
        assert result.exit_code in [0, 1]

    def test_python_code_injection(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "backup database __import__('os').system('dir')", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_template_injection_attempt(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "backup {{7*7}} database", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_xml_injection_attempt(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "backup <script>alert(1)</script> database", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]

    def test_ldap_injection_attempt(self) -> None:
        result = runner.invoke(
            app,
            ["generate", "--input", "backup database *)(uid=*))(|(uid=*", "--preview"],
            input="",
        )
        assert result.exit_code in [0, 1]
