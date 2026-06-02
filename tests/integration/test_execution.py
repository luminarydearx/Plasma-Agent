import asyncio
from uuid import UUID

import pytest

from plasmaagent.core.database import get_database
from plasmaagent.core.state_machine import StepStatus, TaskStatus
from plasmaagent.executor.result import ExecutionResult
from plasmaagent.models.task import TaskCreate, TaskPayload
from plasmaagent.services.execution_service import ExecutionService
from plasmaagent.services.task_service import TaskService


@pytest.fixture
async def db():
    database = get_database()
    await database.connect()
    yield database
    await database.disconnect()


@pytest.fixture
async def task_service(db):
    return TaskService(db)


@pytest.fixture
async def execution_service(db):
    return ExecutionService(db)


@pytest.mark.asyncio
async def test_execute_task_single_command(task_service, execution_service):
    task_data = TaskCreate(
        name="Test Single Command",
        description="Execute single echo command",
        payload=TaskPayload(
            commands=["echo Hello World"],
            timeout=30,
        ),
    )
    
    task = await task_service.create_task(task_data)
    assert task.status == TaskStatus.PENDING.value
    
    executed_task = await execution_service.execute_task(task.id)
    assert executed_task.status == TaskStatus.COMPLETED.value
    
    steps = await task_service.get_task_steps(task.id)
    assert len(steps) == 1
    assert steps[0]["command"] == "echo Hello World"
    assert steps[0]["status"] == StepStatus.COMPLETED.value
    assert steps[0]["exit_code"] == 0
    assert steps[0]["duration_ms"] is not None
    assert steps[0]["duration_ms"] > 0


@pytest.mark.asyncio
async def test_execute_task_multiple_commands(task_service, execution_service):
    task_data = TaskCreate(
        name="Test Multiple Commands",
        description="Execute multiple commands",
        payload=TaskPayload(
            commands=[
                "echo Step 1",
                "echo Step 2",
                "echo Step 3",
            ],
            timeout=30,
        ),
    )
    
    task = await task_service.create_task(task_data)
    executed_task = await execution_service.execute_task(task.id)
    
    assert executed_task.status == TaskStatus.COMPLETED.value
    
    steps = await task_service.get_task_steps(task.id)
    assert len(steps) == 3
    for i, step in enumerate(steps, start=1):
        assert step["step_order"] == i
        assert step["command"] == f"echo Step {i}"
        assert step["status"] == StepStatus.COMPLETED.value
        assert step["exit_code"] == 0


@pytest.mark.asyncio
async def test_execute_task_with_failure(task_service, execution_service):
    task_data = TaskCreate(
        name="Test Failure",
        description="Execute command that fails",
        payload=TaskPayload(
            commands=["exit 1"],
            timeout=30,
        ),
    )
    
    task = await task_service.create_task(task_data)
    executed_task = await execution_service.execute_task(task.id)
    
    assert executed_task.status == TaskStatus.FAILED.value
    
    steps = await task_service.get_task_steps(task.id)
    assert len(steps) == 1
    assert steps[0]["status"] == StepStatus.FAILED.value
    assert steps[0]["exit_code"] == 1


@pytest.mark.asyncio
async def test_execute_task_stops_on_failure(task_service, execution_service):
    task_data = TaskCreate(
        name="Test Stop on Failure",
        description="Should stop after first failure",
        payload=TaskPayload(
            commands=[
                "echo Step 1",
                "exit 1",
                "echo Step 3",
            ],
            timeout=30,
        ),
    )
    
    task = await task_service.create_task(task_data)
    executed_task = await execution_service.execute_task(task.id)
    
    assert executed_task.status == TaskStatus.FAILED.value
    
    steps = await task_service.get_task_steps(task.id)
    assert len(steps) == 2
    assert steps[0]["status"] == StepStatus.COMPLETED.value
    assert steps[1]["status"] == StepStatus.FAILED.value


@pytest.mark.asyncio
async def test_execute_task_with_callbacks(task_service, execution_service):
    task_data = TaskCreate(
        name="Test Callbacks",
        description="Test callback functions",
        payload=TaskPayload(
            commands=["echo Testing callbacks"],
            timeout=30,
        ),
    )
    
    task = await task_service.create_task(task_data)
    
    callback_data = {
        "step_start": [],
        "step_output": [],
        "step_complete": [],
    }
    
    async def on_step_start(step_order: int, command: str) -> None:
        callback_data["step_start"].append((step_order, command))
    
    async def on_step_output(step_order: int, chunk) -> None:
        callback_data["step_output"].append((step_order, chunk))
    
    async def on_step_complete(step_order: int, result: ExecutionResult) -> None:
        callback_data["step_complete"].append((step_order, result))
    
    await execution_service.execute_task(
        task.id,
        on_step_start=on_step_start,
        on_step_output=on_step_output,
        on_step_complete=on_step_complete,
    )
    
    assert len(callback_data["step_start"]) == 1
    assert callback_data["step_start"][0] == (1, "echo Testing callbacks")
    
    assert len(callback_data["step_complete"]) == 1
    assert callback_data["step_complete"][0][0] == 1
    assert callback_data["step_complete"][0][1].succeeded


@pytest.mark.asyncio
async def test_execute_task_empty_commands(task_service, execution_service):
    task_data = TaskCreate(
        name="Test Empty Commands",
        description="Task with no commands",
        payload=TaskPayload(commands=[]),
    )
    
    task = await task_service.create_task(task_data)
    executed_task = await execution_service.execute_task(task.id)
    
    assert executed_task.status == TaskStatus.COMPLETED.value
    
    steps = await task_service.get_task_steps(task.id)
    assert len(steps) == 0


@pytest.mark.asyncio
async def test_execution_logs_captured(task_service, execution_service):
    task_data = TaskCreate(
        name="Test Logs",
        description="Verify logs are captured",
        payload=TaskPayload(
            commands=["echo Log test"],
            timeout=30,
        ),
    )
    
    task = await task_service.create_task(task_data)
    await execution_service.execute_task(task.id)
    
    logs = await task_service.get_execution_logs(task.id)
    assert len(logs) > 0
    
    has_stdout = any(log["log_level"] == "STDOUT" for log in logs)
    assert has_stdout


@pytest.mark.asyncio
async def test_execute_task_with_stderr(task_service, execution_service):
    task_data = TaskCreate(
        name="Test Stderr",
        description="Capture stderr output",
        payload=TaskPayload(
            commands=["echo Error message 1>&2"],
            timeout=30,
        ),
    )
    
    task = await task_service.create_task(task_data)
    await execution_service.execute_task(task.id)
    
    steps = await task_service.get_task_steps(task.id)
    assert len(steps) == 1
    
    logs = await task_service.get_execution_logs(task.id)
    has_stderr = any(log["log_level"] == "STDERR" for log in logs)
    assert has_stderr


@pytest.mark.asyncio
async def test_execute_task_timeout(task_service, execution_service):
    task_data = TaskCreate(
        name="Test Timeout",
        description="Command exceeds timeout",
        payload=TaskPayload(
            commands=["ping -n 10 127.0.0.1"],
            timeout=2,
        ),
    )
    
    task = await task_service.create_task(task_data)
    executed_task = await execution_service.execute_task(task.id)
    
    assert executed_task.status == TaskStatus.FAILED.value
    
    steps = await task_service.get_task_steps(task.id)
    assert len(steps) == 1
    assert steps[0]["status"] == StepStatus.FAILED.value
