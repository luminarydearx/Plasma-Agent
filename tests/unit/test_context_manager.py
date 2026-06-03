import pytest
from datetime import datetime

from plasmaagent.ai.context import (
    ContextManager,
    ContextVariableType,
    TaskExecutionResult,
)


class TestContextManagerInit:
    def test_init_default_session_id(self):
        manager = ContextManager()
        assert manager.session_id.startswith("session_")
        assert len(manager) == 0

    def test_init_custom_session_id(self):
        manager = ContextManager(session_id="my_session")
        assert manager.session_id == "my_session"

    def test_init_empty_session_id_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            ContextManager(session_id="")

    def test_init_whitespace_session_id_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            ContextManager(session_id="   ")

    def test_init_long_session_id_raises(self):
        long_id = "x" * 101
        with pytest.raises(ValueError, match="too long"):
            ContextManager(session_id=long_id)

    def test_init_null_byte_session_id_raises(self):
        with pytest.raises(ValueError, match="null bytes"):
            ContextManager(session_id="session\x00id")

    def test_init_none_session_id_type_raises(self):
        with pytest.raises(TypeError, match="must be a string"):
            ContextManager(session_id=123)


class TestContextManagerSetVariable:
    def test_set_string_variable(self):
        manager = ContextManager()
        manager.set_variable("name", "Alice")
        assert manager.get_variable("name") == "Alice"

    def test_set_integer_variable(self):
        manager = ContextManager()
        manager.set_variable("count", 42)
        assert manager.get_variable("count") == 42

    def test_set_float_variable(self):
        manager = ContextManager()
        manager.set_variable("price", 19.99)
        assert manager.get_variable("price") == 19.99

    def test_set_boolean_variable(self):
        manager = ContextManager()
        manager.set_variable("enabled", True)
        assert manager.get_variable("enabled") is True

    def test_set_dict_variable(self):
        manager = ContextManager()
        data = {"key": "value", "nested": {"a": 1}}
        manager.set_variable("config", data)
        assert manager.get_variable("config") == data

    def test_set_list_variable(self):
        manager = ContextManager()
        items = [1, 2, 3, "four"]
        manager.set_variable("items", items)
        assert manager.get_variable("items") == items

    def test_set_variable_with_task_id(self):
        manager = ContextManager()
        manager.set_variable("task1.output", "result", task_id="task1")
        assert manager.get_variable("task1.output") == "result"

    def test_set_variable_with_type(self):
        manager = ContextManager()
        manager.set_variable("output", "data", ContextVariableType.OUTPUT)
        entry = manager._entries["output"]
        assert entry.variable_type == ContextVariableType.OUTPUT

    def test_set_variable_empty_name_raises(self):
        manager = ContextManager()
        with pytest.raises(ValueError, match="cannot be empty"):
            manager.set_variable("", "value")

    def test_set_variable_whitespace_name_raises(self):
        manager = ContextManager()
        with pytest.raises(ValueError, match="cannot be empty"):
            manager.set_variable("   ", "value")

    def test_set_variable_long_name_raises(self):
        manager = ContextManager()
        long_name = "x" * 101
        with pytest.raises(ValueError, match="too long"):
            manager.set_variable(long_name, "value")

    def test_set_variable_invalid_name_raises(self):
        manager = ContextManager()
        with pytest.raises(ValueError, match="must start with"):
            manager.set_variable("123invalid", "value")

    def test_set_variable_special_chars_raises(self):
        manager = ContextManager()
        with pytest.raises(ValueError, match="must start with"):
            manager.set_variable("name@invalid", "value")

    def test_set_variable_null_byte_name_raises(self):
        manager = ContextManager()
        with pytest.raises(ValueError, match="null bytes"):
            manager.set_variable("name\x00", "value")

    def test_set_variable_null_byte_value_raises(self):
        manager = ContextManager()
        with pytest.raises(ValueError, match="null bytes"):
            manager.set_variable("name", "value\x00")

    def test_set_variable_long_value_raises(self):
        manager = ContextManager()
        long_value = "x" * 50001
        with pytest.raises(ValueError, match="too long"):
            manager.set_variable("name", long_value)

    def test_set_variable_none_name_raises(self):
        manager = ContextManager()
        with pytest.raises(TypeError, match="must be a string"):
            manager.set_variable(None, "value")

    def test_set_variable_max_limit(self):
        manager = ContextManager()
        for i in range(1000):
            manager.set_variable(f"var{i}", i)
        assert len(manager) == 1000
        with pytest.raises(ValueError, match="Maximum variables"):
            manager.set_variable("var1000", 1000)

    def test_set_variable_overwrite_existing(self):
        manager = ContextManager()
        manager.set_variable("name", "Alice")
        manager.set_variable("name", "Bob")
        assert manager.get_variable("name") == "Bob"
        assert len(manager) == 1


class TestContextManagerGetVariable:
    def test_get_existing_variable(self):
        manager = ContextManager()
        manager.set_variable("name", "Alice")
        assert manager.get_variable("name") == "Alice"

    def test_get_nonexistent_variable_returns_none(self):
        manager = ContextManager()
        assert manager.get_variable("nonexistent") is None

    def test_get_nonexistent_variable_returns_default(self):
        manager = ContextManager()
        assert manager.get_variable("nonexistent", "default") == "default"

    def test_get_variable_none_name_raises(self):
        manager = ContextManager()
        with pytest.raises(TypeError, match="must be a string"):
            manager.get_variable(None)


class TestContextManagerHasVariable:
    def test_has_existing_variable(self):
        manager = ContextManager()
        manager.set_variable("name", "Alice")
        assert manager.has_variable("name") is True

    def test_has_nonexistent_variable(self):
        manager = ContextManager()
        assert manager.has_variable("nonexistent") is False


class TestContextManagerDeleteVariable:
    def test_delete_existing_variable(self):
        manager = ContextManager()
        manager.set_variable("name", "Alice")
        assert manager.delete_variable("name") is True
        assert manager.get_variable("name") is None

    def test_delete_nonexistent_variable(self):
        manager = ContextManager()
        assert manager.delete_variable("nonexistent") is False


class TestContextManagerRecordTaskResult:
    def test_record_task_result(self):
        manager = ContextManager()
        result = TaskExecutionResult(
            task_id="task1",
            status="COMPLETED",
            output="success",
            exit_code=0,
            duration_ms=100,
        )
        manager.record_task_result(result)
        assert manager.result_count == 1

    def test_record_task_result_auto_sets_variables(self):
        manager = ContextManager()
        result = TaskExecutionResult(
            task_id="task1",
            status="COMPLETED",
            output="success",
            stdout="stdout data",
            stderr="stderr data",
            exit_code=0,
            duration_ms=100,
        )
        manager.record_task_result(result)
        assert manager.get_variable("task1.status") == "COMPLETED"
        assert manager.get_variable("task1.output") == "success"
        assert manager.get_variable("task1.stdout") == "stdout data"
        assert manager.get_variable("task1.stderr") == "stderr data"
        assert manager.get_variable("task1.exit_code") == 0
        assert manager.get_variable("task1.duration_ms") == 100

    def test_record_task_result_with_error(self):
        manager = ContextManager()
        result = TaskExecutionResult(
            task_id="task1",
            status="FAILED",
            error="Command failed",
            exit_code=1,
        )
        manager.record_task_result(result)
        assert manager.get_variable("task1.status") == "FAILED"
        assert manager.get_variable("task1.error") == "Command failed"
        assert manager.get_variable("task1.exit_code") == 1

    def test_record_task_result_invalid_type_raises(self):
        manager = ContextManager()
        with pytest.raises(TypeError, match="must be a TaskExecutionResult"):
            manager.record_task_result({"task_id": "task1"})


class TestContextManagerGetPreviousResult:
    def test_get_previous_result_empty(self):
        manager = ContextManager()
        assert manager.get_previous_result() is None

    def test_get_previous_result_single(self):
        manager = ContextManager()
        result = TaskExecutionResult(task_id="task1", status="COMPLETED")
        manager.record_task_result(result)
        assert manager.get_previous_result() == result

    def test_get_previous_result_multiple(self):
        manager = ContextManager()
        result1 = TaskExecutionResult(task_id="task1", status="COMPLETED")
        result2 = TaskExecutionResult(task_id="task2", status="FAILED")
        manager.record_task_result(result1)
        manager.record_task_result(result2)
        assert manager.get_previous_result() == result2


class TestContextManagerGetTaskResult:
    def test_get_task_result_existing(self):
        manager = ContextManager()
        result = TaskExecutionResult(task_id="task1", status="COMPLETED")
        manager.record_task_result(result)
        assert manager.get_task_result("task1") == result

    def test_get_task_result_nonexistent(self):
        manager = ContextManager()
        assert manager.get_task_result("nonexistent") is None

    def test_get_task_result_multiple(self):
        manager = ContextManager()
        result1 = TaskExecutionResult(task_id="task1", status="COMPLETED")
        result2 = TaskExecutionResult(task_id="task2", status="FAILED")
        manager.record_task_result(result1)
        manager.record_task_result(result2)
        assert manager.get_task_result("task1") == result1
        assert manager.get_task_result("task2") == result2


class TestContextManagerSubstitute:
    def test_substitute_single_variable(self):
        manager = ContextManager()
        manager.set_variable("name", "Alice")
        result = manager.substitute("Hello, ${name}!")
        assert result == "Hello, Alice!"

    def test_substitute_multiple_variables(self):
        manager = ContextManager()
        manager.set_variable("name", "Alice")
        manager.set_variable("age", 30)
        result = manager.substitute("${name} is ${age} years old")
        assert result == "Alice is 30 years old"

    def test_substitute_nonexistent_variable_default(self):
        manager = ContextManager()
        result = manager.substitute("Hello, ${name}!")
        assert result == "Hello, !"

    def test_substitute_nonexistent_variable_custom_default(self):
        manager = ContextManager()
        result = manager.substitute("Hello, ${name}!", default="UNKNOWN")
        assert result == "Hello, UNKNOWN!"

    def test_substitute_dotted_variable(self):
        manager = ContextManager()
        manager.set_variable("task1.output", "success")
        result = manager.substitute("Result: ${task1.output}")
        assert result == "Result: success"

    def test_substitute_no_variables(self):
        manager = ContextManager()
        result = manager.substitute("Hello, world!")
        assert result == "Hello, world!"

    def test_substitute_empty_string(self):
        manager = ContextManager()
        result = manager.substitute("")
        assert result == ""

    def test_substitute_null_byte_raises(self):
        manager = ContextManager()
        with pytest.raises(ValueError, match="null bytes"):
            manager.substitute("text\x00")

    def test_substitute_none_raises(self):
        manager = ContextManager()
        with pytest.raises(TypeError, match="must be a string"):
            manager.substitute(None)

    def test_substitute_integer_variable(self):
        manager = ContextManager()
        manager.set_variable("count", 42)
        result = manager.substitute("Count: ${count}")
        assert result == "Count: 42"


class TestContextManagerFindVariables:
    def test_find_single_variable(self):
        manager = ContextManager()
        variables = manager.find_variables("Hello, ${name}!")
        assert variables == ["name"]

    def test_find_multiple_variables(self):
        manager = ContextManager()
        variables = manager.find_variables("${name} is ${age} years old")
        assert variables == ["name", "age"]

    def test_find_dotted_variable(self):
        manager = ContextManager()
        variables = manager.find_variables("Result: ${task1.output}")
        assert variables == ["task1.output"]

    def test_find_no_variables(self):
        manager = ContextManager()
        variables = manager.find_variables("Hello, world!")
        assert variables == []

    def test_find_empty_string(self):
        manager = ContextManager()
        variables = manager.find_variables("")
        assert variables == []

    def test_find_none_raises(self):
        manager = ContextManager()
        with pytest.raises(TypeError, match="must be a string"):
            manager.find_variables(None)


class TestContextManagerListVariables:
    def test_list_all_variables(self):
        manager = ContextManager()
        manager.set_variable("a", 1)
        manager.set_variable("b", 2)
        manager.set_variable("c", 3)
        assert manager.list_variables() == ["a", "b", "c"]

    def test_list_variables_with_prefix(self):
        manager = ContextManager()
        manager.set_variable("task1.output", "a")
        manager.set_variable("task1.status", "b")
        manager.set_variable("task2.output", "c")
        assert manager.list_variables(prefix="task1") == ["task1.output", "task1.status"]

    def test_list_variables_empty(self):
        manager = ContextManager()
        assert manager.list_variables() == []

    def test_list_variables_no_match(self):
        manager = ContextManager()
        manager.set_variable("a", 1)
        assert manager.list_variables(prefix="b") == []


class TestContextManagerClear:
    def test_clear_empty(self):
        manager = ContextManager()
        manager.clear()
        assert len(manager) == 0
        assert manager.result_count == 0

    def test_clear_with_data(self):
        manager = ContextManager()
        manager.set_variable("name", "Alice")
        result = TaskExecutionResult(task_id="task1", status="COMPLETED")
        manager.record_task_result(result)
        manager.clear()
        assert len(manager) == 0
        assert manager.result_count == 0


class TestContextManagerSnapshot:
    def test_snapshot_empty(self):
        manager = ContextManager(session_id="test")
        snapshot = manager.snapshot()
        assert snapshot.session_id == "test"
        assert len(snapshot.entries) == 0
        assert len(snapshot.task_results) == 0

    def test_snapshot_with_data(self):
        manager = ContextManager(session_id="test")
        manager.set_variable("name", "Alice")
        result = TaskExecutionResult(task_id="task1", status="COMPLETED")
        manager.record_task_result(result)
        snapshot = manager.snapshot()
        assert snapshot.session_id == "test"
        assert len(snapshot.entries) == 2  # name + auto-set task1.status
        assert len(snapshot.task_results) == 1


class TestContextManagerMagicMethods:
    def test_len(self):
        manager = ContextManager()
        assert len(manager) == 0
        manager.set_variable("a", 1)
        assert len(manager) == 1
        manager.set_variable("b", 2)
        assert len(manager) == 2

    def test_contains(self):
        manager = ContextManager()
        manager.set_variable("name", "Alice")
        assert "name" in manager
        assert "nonexistent" not in manager

    def test_repr(self):
        manager = ContextManager(session_id="test")
        manager.set_variable("a", 1)
        repr_str = repr(manager)
        assert "test" in repr_str
        assert "entries=1" in repr_str
        assert "results=0" in repr_str


class TestContextManagerEdgeCases:
    def test_unicode_variable_name_rejected(self):
        manager = ContextManager()
        with pytest.raises(ValueError, match="must start with letter/underscore"):
            manager.set_variable("名前", "アリス")

    def test_unicode_variable_value(self):
        manager = ContextManager()
        manager.set_variable("name", "日本語テスト")
        assert manager.get_variable("name") == "日本語テスト"

    def test_emoji_variable_value(self):
        manager = ContextManager()
        manager.set_variable("emoji", "🎉🚀✨")
        assert manager.get_variable("emoji") == "🎉🚀✨"

    def test_special_chars_variable_value(self):
        manager = ContextManager()
        special = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        manager.set_variable("special", special)
        assert manager.get_variable("special") == special

    def test_newline_variable_value(self):
        manager = ContextManager()
        manager.set_variable("multiline", "line1\nline2\nline3")
        assert manager.get_variable("multiline") == "line1\nline2\nline3"

    def test_tab_variable_value(self):
        manager = ContextManager()
        manager.set_variable("tabs", "col1\tcol2\tcol3")
        assert manager.get_variable("tabs") == "col1\tcol2\tcol3"

    def test_very_long_variable_name(self):
        manager = ContextManager()
        name = "a" * 100
        manager.set_variable(name, "value")
        assert manager.get_variable(name) == "value"

    def test_very_long_variable_value(self):
        manager = ContextManager()
        value = "x" * 50000
        manager.set_variable("long", value)
        assert manager.get_variable("long") == value

    def test_sql_injection_attempt(self):
        manager = ContextManager()
        malicious = "'; DROP TABLE tasks; --"
        manager.set_variable("name", malicious)
        assert manager.get_variable("name") == malicious

    def test_shell_injection_attempt(self):
        manager = ContextManager()
        malicious = "value; rm -rf /"
        manager.set_variable("name", malicious)
        assert manager.get_variable("name") == malicious

    def test_command_substitution_attempt(self):
        manager = ContextManager()
        malicious = "$(whoami)"
        manager.set_variable("name", malicious)
        assert manager.get_variable("name") == malicious

    def test_concurrent_sessions_isolation(self):
        manager1 = ContextManager(session_id="session1")
        manager2 = ContextManager(session_id="session2")
        manager1.set_variable("name", "Alice")
        manager2.set_variable("name", "Bob")
        assert manager1.get_variable("name") == "Alice"
        assert manager2.get_variable("name") == "Bob"

    def test_bulk_operations_performance(self):
        manager = ContextManager()
        for i in range(100):
            manager.set_variable(f"var{i}", i)
        assert len(manager) == 100
        for i in range(100):
            assert manager.get_variable(f"var{i}") == i
