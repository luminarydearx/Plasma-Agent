import pytest
from datetime import datetime
from plasmaagent.ai.context import ContextManager, ExecutionContext, SessionContext


class TestContextManagerInit:
    def test_init_empty(self):
        manager = ContextManager()
        assert manager.session_count == 0
        assert manager.list_sessions() == []
    
    def test_max_variable_length(self):
        manager = ContextManager()
        assert manager.MAX_VARIABLE_LENGTH == 10000
    
    def test_max_sessions(self):
        manager = ContextManager()
        assert manager.MAX_SESSIONS == 100


class TestContextManagerSessionCreation:
    def test_create_session_with_id(self):
        manager = ContextManager()
        session = manager.create_session("test-session-1")
        assert session.session_id == "test-session-1"
        assert manager.session_count == 1
        assert "test-session-1" in manager.list_sessions()
    
    def test_create_session_without_id(self):
        manager = ContextManager()
        session = manager.create_session()
        assert session.session_id is not None
        assert len(session.session_id) == 36
        assert manager.session_count == 1
    
    def test_create_multiple_sessions(self):
        manager = ContextManager()
        manager.create_session("session-1")
        manager.create_session("session-2")
        manager.create_session("session-3")
        assert manager.session_count == 3
        assert len(manager.list_sessions()) == 3
    
    def test_create_session_auto_eviction(self):
        manager = ContextManager()
        for i in range(100):
            manager.create_session(f"session-{i}")
        assert manager.session_count == 100
        
        manager.create_session("session-101")
        assert manager.session_count == 100
        assert "session-101" in manager.list_sessions()
    
    def test_get_session_exists(self):
        manager = ContextManager()
        manager.create_session("test-session")
        session = manager.get_session("test-session")
        assert session is not None
        assert session.session_id == "test-session"
    
    def test_get_session_not_exists(self):
        manager = ContextManager()
        session = manager.get_session("nonexistent")
        assert session is None


class TestContextManagerSessionDeletion:
    def test_delete_session_exists(self):
        manager = ContextManager()
        manager.create_session("test-session")
        result = manager.delete_session("test-session")
        assert result is True
        assert manager.session_count == 0
    
    def test_delete_session_not_exists(self):
        manager = ContextManager()
        result = manager.delete_session("nonexistent")
        assert result is False
    
    def test_clear_all_sessions(self):
        manager = ContextManager()
        manager.create_session("session-1")
        manager.create_session("session-2")
        manager.create_session("session-3")
        count = manager.clear_all_sessions()
        assert count == 3
        assert manager.session_count == 0


class TestContextManagerExecutions:
    def test_add_execution_success(self):
        manager = ContextManager()
        manager.create_session("test-session")
        execution = manager.add_execution(
            session_id="test-session",
            task_id="task-1",
            output="Success output",
            exit_code=0,
            duration_ms=150
        )
        assert execution.task_id == "task-1"
        assert execution.output == "Success output"
        assert execution.exit_code == 0
        assert execution.duration_ms == 150
        assert execution.success is True
        assert execution.failed is False
    
    def test_add_execution_failure(self):
        manager = ContextManager()
        manager.create_session("test-session")
        execution = manager.add_execution(
            session_id="test-session",
            task_id="task-1",
            output="Error output",
            exit_code=1,
            duration_ms=200
        )
        assert execution.exit_code == 1
        assert execution.success is False
        assert execution.failed is True
    
    def test_add_execution_with_metadata(self):
        manager = ContextManager()
        manager.create_session("test-session")
        execution = manager.add_execution(
            session_id="test-session",
            task_id="task-1",
            output="Output",
            exit_code=0,
            duration_ms=100,
            metadata={"template": "backup", "confidence": 0.95}
        )
        assert execution.metadata["template"] == "backup"
        assert execution.metadata["confidence"] == 0.95
    
    def test_add_execution_session_not_found(self):
        manager = ContextManager()
        with pytest.raises(ValueError, match="Session nonexistent not found"):
            manager.add_execution(
                session_id="nonexistent",
                task_id="task-1",
                output="Output",
                exit_code=0,
                duration_ms=100
            )
    
    def test_add_multiple_executions(self):
        manager = ContextManager()
        manager.create_session("test-session")
        manager.add_execution("test-session", "task-1", "Output 1", 0, 100)
        manager.add_execution("test-session", "task-2", "Output 2", 0, 150)
        manager.add_execution("test-session", "task-3", "Output 3", 1, 200)
        
        session = manager.get_session("test-session")
        assert session.execution_count == 3
        assert session.success_count == 2
        assert session.failure_count == 1
        assert session.success_rate == 2.0 / 3.0
    
    def test_get_execution_history(self):
        manager = ContextManager()
        manager.create_session("test-session")
        manager.add_execution("test-session", "task-1", "Output 1", 0, 100)
        manager.add_execution("test-session", "task-2", "Output 2", 0, 150)
        
        history = manager.get_execution_history("test-session")
        assert len(history) == 2
        assert history[0].task_id == "task-1"
        assert history[1].task_id == "task-2"
    
    def test_get_execution_history_empty(self):
        manager = ContextManager()
        manager.create_session("test-session")
        history = manager.get_execution_history("test-session")
        assert history == []
    
    def test_get_execution_history_session_not_found(self):
        manager = ContextManager()
        history = manager.get_execution_history("nonexistent")
        assert history == []
    
    def test_get_last_execution(self):
        manager = ContextManager()
        manager.create_session("test-session")
        manager.add_execution("test-session", "task-1", "Output 1", 0, 100)
        manager.add_execution("test-session", "task-2", "Output 2", 0, 150)
        
        last = manager.get_last_execution("test-session")
        assert last is not None
        assert last.task_id == "task-2"
    
    def test_get_last_execution_empty(self):
        manager = ContextManager()
        manager.create_session("test-session")
        last = manager.get_last_execution("test-session")
        assert last is None
    
    def test_get_last_execution_session_not_found(self):
        manager = ContextManager()
        last = manager.get_last_execution("nonexistent")
        assert last is None


class TestContextManagerVariables:
    def test_set_variable(self):
        manager = ContextManager()
        manager.create_session("test-session")
        manager.set_variable("test-session", "backup_path", "/tmp/backup.sql")
        
        value = manager.get_variable("test-session", "backup_path")
        assert value == "/tmp/backup.sql"
    
    def test_set_variable_session_not_found(self):
        manager = ContextManager()
        with pytest.raises(ValueError, match="Session nonexistent not found"):
            manager.set_variable("nonexistent", "key", "value")
    
    def test_get_variable_not_exists(self):
        manager = ContextManager()
        manager.create_session("test-session")
        value = manager.get_variable("test-session", "nonexistent")
        assert value is None
    
    def test_get_variable_session_not_found(self):
        manager = ContextManager()
        value = manager.get_variable("nonexistent", "key")
        assert value is None
    
    def test_set_multiple_variables(self):
        manager = ContextManager()
        manager.create_session("test-session")
        manager.set_variable("test-session", "var1", "value1")
        manager.set_variable("test-session", "var2", "value2")
        manager.set_variable("test-session", "var3", "value3")
        
        assert manager.get_variable("test-session", "var1") == "value1"
        assert manager.get_variable("test-session", "var2") == "value2"
        assert manager.get_variable("test-session", "var3") == "value3"
    
    def test_variable_max_length(self):
        manager = ContextManager()
        manager.create_session("test-session")
        long_value = "x" * 15000
        manager.set_variable("test-session", "long_var", long_value)
        
        value = manager.get_variable("test-session", "long_var")
        assert len(value) == 10000


class TestContextManagerSubstitution:
    def test_substitute_execution_output(self):
        manager = ContextManager()
        manager.create_session("test-session")
        manager.add_execution("test-session", "task-1", "Backup completed", 0, 100)
        
        text = "Result: ${task-1.output}"
        result = manager.substitute_variables("test-session", text)
        assert result == "Result: Backup completed"
    
    def test_substitute_exit_code(self):
        manager = ContextManager()
        manager.create_session("test-session")
        manager.add_execution("test-session", "task-1", "Output", 1, 100)
        
        text = "Exit: ${task-1.exit_code}"
        result = manager.substitute_variables("test-session", text)
        assert result == "Exit: 1"
    
    def test_substitute_duration(self):
        manager = ContextManager()
        manager.create_session("test-session")
        manager.add_execution("test-session", "task-1", "Output", 0, 250)
        
        text = "Duration: ${task-1.duration}ms"
        result = manager.substitute_variables("test-session", text)
        assert result == "Duration: 250ms"
    
    def test_substitute_success(self):
        manager = ContextManager()
        manager.create_session("test-session")
        manager.add_execution("test-session", "task-1", "Output", 0, 100)
        
        text = "Success: ${task-1.success}"
        result = manager.substitute_variables("test-session", text)
        assert result == "Success: true"
    
    def test_substitute_failed(self):
        manager = ContextManager()
        manager.create_session("test-session")
        manager.add_execution("test-session", "task-1", "Output", 1, 100)
        
        text = "Failed: ${task-1.failed}"
        result = manager.substitute_variables("test-session", text)
        assert result == "Failed: true"
    
    def test_substitute_custom_variable(self):
        manager = ContextManager()
        manager.create_session("test-session")
        manager.set_variable("test-session", "backup_path", "/tmp/backup.sql")
        
        text = "Path: ${var.backup_path}"
        result = manager.substitute_variables("test-session", text)
        assert result == "Path: /tmp/backup.sql"
    
    def test_substitute_multiple_variables(self):
        manager = ContextManager()
        manager.create_session("test-session")
        manager.add_execution("test-session", "task-1", "Output 1", 0, 100)
        manager.add_execution("test-session", "task-2", "Output 2", 0, 150)
        manager.set_variable("test-session", "status", "completed")
        
        text = "${task-1.output} and ${task-2.output} - Status: ${var.status}"
        result = manager.substitute_variables("test-session", text)
        assert result == "Output 1 and Output 2 - Status: completed"
    
    def test_substitute_nonexistent_execution(self):
        manager = ContextManager()
        manager.create_session("test-session")
        
        text = "Result: ${nonexistent.output}"
        result = manager.substitute_variables("test-session", text)
        assert result == "Result: ${nonexistent.output}"
    
    def test_substitute_nonexistent_variable(self):
        manager = ContextManager()
        manager.create_session("test-session")
        
        text = "Value: ${var.nonexistent}"
        result = manager.substitute_variables("test-session", text)
        assert result == "Value: ${var.nonexistent}"
    
    def test_substitute_invalid_field(self):
        manager = ContextManager()
        manager.create_session("test-session")
        manager.add_execution("test-session", "task-1", "Output", 0, 100)
        
        text = "Invalid: ${task-1.invalid_field}"
        result = manager.substitute_variables("test-session", text)
        assert result == "Invalid: ${task-1.invalid_field}"
    
    def test_substitute_session_not_found(self):
        manager = ContextManager()
        
        text = "Result: ${task-1.output}"
        result = manager.substitute_variables("nonexistent", text)
        assert result == "Result: ${task-1.output}"
    
    def test_substitute_no_variables(self):
        manager = ContextManager()
        manager.create_session("test-session")
        
        text = "No variables here"
        result = manager.substitute_variables("test-session", text)
        assert result == "No variables here"


class TestContextManagerStats:
    def test_get_session_stats_empty(self):
        manager = ContextManager()
        manager.create_session("test-session")
        stats = manager.get_session_stats("test-session")
        
        assert stats["execution_count"] == 0
        assert stats["success_count"] == 0
        assert stats["failure_count"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["total_duration_ms"] == 0
        assert stats["avg_duration_ms"] == 0.0
    
    def test_get_session_stats_with_data(self):
        manager = ContextManager()
        manager.create_session("test-session")
        manager.add_execution("test-session", "task-1", "Output", 0, 100)
        manager.add_execution("test-session", "task-2", "Output", 0, 150)
        manager.add_execution("test-session", "task-3", "Output", 1, 200)
        
        stats = manager.get_session_stats("test-session")
        
        assert stats["execution_count"] == 3
        assert stats["success_count"] == 2
        assert stats["failure_count"] == 1
        assert stats["success_rate"] == 2.0 / 3.0
        assert stats["total_duration_ms"] == 450
        assert stats["avg_duration_ms"] == 150.0
    
    def test_get_session_stats_session_not_found(self):
        manager = ContextManager()
        stats = manager.get_session_stats("nonexistent")
        
        assert stats["execution_count"] == 0
        assert stats["success_count"] == 0
        assert stats["failure_count"] == 0
        assert stats["success_rate"] == 0.0


class TestContextManagerSessionIsolation:
    def test_sessions_isolated(self):
        manager = ContextManager()
        manager.create_session("session-1")
        manager.create_session("session-2")
        
        manager.add_execution("session-1", "task-1", "Output 1", 0, 100)
        manager.add_execution("session-2", "task-2", "Output 2", 0, 150)
        
        session1 = manager.get_session("session-1")
        session2 = manager.get_session("session-2")
        
        assert session1.execution_count == 1
        assert session2.execution_count == 1
        assert session1.executions[0].task_id == "task-1"
        assert session2.executions[0].task_id == "task-2"
    
    def test_variables_isolated(self):
        manager = ContextManager()
        manager.create_session("session-1")
        manager.create_session("session-2")
        
        manager.set_variable("session-1", "var1", "value1")
        manager.set_variable("session-2", "var1", "value2")
        
        assert manager.get_variable("session-1", "var1") == "value1"
        assert manager.get_variable("session-2", "var1") == "value2"
    
    def test_substitution_isolated(self):
        manager = ContextManager()
        manager.create_session("session-1")
        manager.create_session("session-2")
        
        manager.add_execution("session-1", "task-1", "Output 1", 0, 100)
        manager.add_execution("session-2", "task-1", "Output 2", 0, 150)
        
        result1 = manager.substitute_variables("session-1", "${task-1.output}")
        result2 = manager.substitute_variables("session-2", "${task-1.output}")
        
        assert result1 == "Output 1"
        assert result2 == "Output 2"


class TestContextManagerEdgeCases:
    def test_output_max_length(self):
        manager = ContextManager()
        manager.create_session("test-session")
        long_output = "x" * 150000
        execution = manager.add_execution(
            "test-session",
            "task-1",
            long_output,
            0,
            100
        )
        assert len(execution.output) == 100000
    
    def test_empty_output(self):
        manager = ContextManager()
        manager.create_session("test-session")
        execution = manager.add_execution("test-session", "task-1", "", 0, 100)
        assert execution.output == ""
    
    def test_negative_exit_code(self):
        manager = ContextManager()
        manager.create_session("test-session")
        execution = manager.add_execution("test-session", "task-1", "Output", -1, 100)
        assert execution.exit_code == -1
        assert execution.failed is True
    
    def test_large_exit_code(self):
        manager = ContextManager()
        manager.create_session("test-session")
        execution = manager.add_execution("test-session", "task-1", "Output", 255, 100)
        assert execution.exit_code == 255
    
    def test_zero_duration(self):
        manager = ContextManager()
        manager.create_session("test-session")
        execution = manager.add_execution("test-session", "task-1", "Output", 0, 0)
        assert execution.duration_ms == 0
    
    def test_special_characters_in_output(self):
        manager = ContextManager()
        manager.create_session("test-session")
        special_output = "Output with $pecial ch@rs! & <tags> ${not-a-variable}"
        execution = manager.add_execution("test-session", "task-1", special_output, 0, 100)
        assert execution.output == special_output
    
    def test_unicode_in_output(self):
        manager = ContextManager()
        manager.create_session("test-session")
        unicode_output = "Unicode: 日本語 العربية 🚀"
        execution = manager.add_execution("test-session", "task-1", unicode_output, 0, 100)
        assert execution.output == unicode_output
    
    def test_multiline_output(self):
        manager = ContextManager()
        manager.create_session("test-session")
        multiline = "Line 1\nLine 2\nLine 3"
        execution = manager.add_execution("test-session", "task-1", multiline, 0, 100)
        assert execution.output == multiline


class TestContextManagerPerformance:
    def test_many_executions(self):
        manager = ContextManager()
        manager.create_session("test-session")
        
        for i in range(100):
            manager.add_execution("test-session", f"task-{i}", f"Output {i}", 0, 100)
        
        session = manager.get_session("test-session")
        assert session.execution_count == 100
    
    def test_many_sessions(self):
        manager = ContextManager()
        
        for i in range(50):
            manager.create_session(f"session-{i}")
        
        assert manager.session_count == 50
    
    def test_substitution_performance(self):
        manager = ContextManager()
        manager.create_session("test-session")
        
        for i in range(50):
            manager.add_execution("test-session", f"task-{i}", f"Output {i}", 0, 100)
        
        text = " ".join([f"${{task-{i}.output}}" for i in range(50)])
        result = manager.substitute_variables("test-session", text)
        
        assert len(result) > 0
        assert "Output 0" in result
        assert "Output 49" in result
