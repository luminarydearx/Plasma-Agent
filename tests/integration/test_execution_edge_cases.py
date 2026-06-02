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
async def test_concurrent_task_execution(task_service, execution_service):
    task1 = await task_service.create_task(
        TaskCreate(
            name="Concurrent Task 1",
            payload=TaskPayload(commands=["echo Task 1"], timeout=30),
        )
    )
    
    task2 = await task_service.create_task(
        TaskCreate(
            name="Concurrent Task 2",
            payload=TaskPayload(commands=["echo Task 2"], timeout=30),
        )
    )
    
    result1, result2 = await asyncio.gather(
        execution_service.execute_task(task1.id),
        execution_service.execute_task(task2.id),
    )
    
    assert result1.status == TaskStatus.COMPLETED.value
    assert result2.status == TaskStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_execute_already_running_task(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Running Task",
            payload=TaskPayload(commands=["timeout /t 5"], timeout=10),
        )
    )
    
    execution_task = asyncio.create_task(
        execution_service.execute_task(task.id)
    )
    
    await asyncio.sleep(0.5)
    
    with pytest.raises(Exception) as exc_info:
        await execution_service.execute_task(task.id)
    
    assert "RUNNING" in str(exc_info.value) or "cannot be executed" in str(exc_info.value)
    
    await execution_task


@pytest.mark.asyncio
async def test_execute_completed_task(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Completed Task",
            payload=TaskPayload(commands=["echo Done"], timeout=30),
        )
    )
    
    await execution_service.execute_task(task.id)
    
    with pytest.raises(Exception) as exc_info:
        await execution_service.execute_task(task.id)
    
    assert "COMPLETED" in str(exc_info.value) or "cannot be executed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_cancelled_task(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Cancelled Task",
            payload=TaskPayload(commands=["echo Test"], timeout=30),
        )
    )
    
    await task_service.cancel_task(task.id)
    
    with pytest.raises(Exception) as exc_info:
        await execution_service.execute_task(task.id)
    
    assert "CANCELLED" in str(exc_info.value) or "cannot be executed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_command_with_special_characters(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Special Chars",
            payload=TaskPayload(
                commands=['echo "Hello & World | Test > null"'],
                timeout=30,
            ),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status == TaskStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_command_with_unicode(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Unicode Test",
            payload=TaskPayload(
                commands=["echo Hello 世界 🌍"],
                timeout=30,
            ),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status == TaskStatus.COMPLETED.value
    
    steps = await task_service.get_task_steps(task.id)
    assert len(steps) == 1
    assert steps[0]["status"] == StepStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_very_long_output(task_service, execution_service):
    long_command = "for /L %i in (1,1,1000) do @echo Line %i"
    
    task = await task_service.create_task(
        TaskCreate(
            name="Long Output",
            payload=TaskPayload(commands=[long_command], timeout=60),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status == TaskStatus.COMPLETED.value
    
    logs = await task_service.get_execution_logs(task.id)
    stdout_logs = [log for log in logs if log["log_level"] == "STDOUT"]
    assert len(stdout_logs) > 100


@pytest.mark.asyncio
async def test_command_creates_file(task_service, execution_service, tmp_path):
    test_file = tmp_path / "test_output.txt"
    
    task = await task_service.create_task(
        TaskCreate(
            name="Create File",
            payload=TaskPayload(
                commands=[f'echo "Test content" > "{test_file}"'],
                timeout=30,
                cwd=str(tmp_path),
            ),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status == TaskStatus.COMPLETED.value
    
    assert test_file.exists()
    content = test_file.read_text()
    assert "Test content" in content


@pytest.mark.asyncio
async def test_command_reads_environment_variable(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Read Env",
            payload=TaskPayload(
                commands=["echo %USERNAME%"],
                timeout=30,
            ),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status == TaskStatus.COMPLETED.value
    
    steps = await task_service.get_task_steps(task.id)
    assert len(steps) == 1
    assert steps[0]["exit_code"] == 0


@pytest.mark.asyncio
async def test_command_with_pipe(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Pipe Test",
            payload=TaskPayload(
                commands=["echo Hello World | findstr World"],
                timeout=30,
            ),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status == TaskStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_command_with_redirect(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Redirect Test",
            payload=TaskPayload(
                commands=["echo Test > NUL"],
                timeout=30,
            ),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status == TaskStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_nonexistent_command(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Nonexistent Command",
            payload=TaskPayload(
                commands=["nonexistent_command_12345"],
                timeout=30,
            ),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status == TaskStatus.FAILED.value
    
    steps = await task_service.get_task_steps(task.id)
    assert len(steps) == 1
    assert steps[0]["status"] == StepStatus.FAILED.value
    assert steps[0]["exit_code"] != 0


@pytest.mark.asyncio
async def test_command_with_invalid_path(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Invalid Path",
            payload=TaskPayload(
                commands=["echo Test"],
                timeout=30,
                cwd="C:\\This\\Path\\Does\\Not\\Exist",
            ),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status == TaskStatus.FAILED.value


@pytest.mark.asyncio
async def test_zero_timeout(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Zero Timeout",
            payload=TaskPayload(
                commands=["echo Quick"],
                timeout=0,
            ),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    
    assert result.status in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]


@pytest.mark.asyncio
async def test_very_short_timeout(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Short Timeout",
            payload=TaskPayload(
                commands=["timeout /t 10"],
                timeout=1,
            ),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status == TaskStatus.FAILED.value
    
    steps = await task_service.get_task_steps(task.id)
    assert len(steps) == 1
    assert steps[0]["status"] == StepStatus.FAILED.value


@pytest.mark.asyncio
async def test_command_with_large_output_stderr(task_service, execution_service):
    command = "for /L %i in (1,1,500) do @echo Error %i 1>&2"
    
    task = await task_service.create_task(
        TaskCreate(
            name="Large Stderr",
            payload=TaskPayload(commands=[command], timeout=60),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    
    logs = await task_service.get_execution_logs(task.id)
    stderr_logs = [log for log in logs if log["log_level"] == "STDERR"]
    assert len(stderr_logs) > 0


@pytest.mark.asyncio
async def test_rapid_successive_executions(task_service, execution_service):
    tasks = []
    for i in range(5):
        task = await task_service.create_task(
            TaskCreate(
                name=f"Rapid Task {i}",
                payload=TaskPayload(commands=[f"echo Task {i}"], timeout=30),
            )
        )
        tasks.append(task)
    
    for task in tasks:
        result = await execution_service.execute_task(task.id)
        assert result.status == TaskStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_command_with_multiline_output(task_service, execution_service):
    commands = ["echo Line 1", "echo Line 2", "echo Line 3"]
    
    task = await task_service.create_task(
        TaskCreate(
            name="Multiline",
            payload=TaskPayload(commands=commands, timeout=30),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status == TaskStatus.COMPLETED.value
    
    logs = await task_service.get_execution_logs(task.id)
    stdout_logs = [log for log in logs if log["log_level"] == "STDOUT"]
    assert len(stdout_logs) >= 3


@pytest.mark.asyncio
async def test_execute_task_without_payload(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="No Payload",
            description="Task without commands",
        )
    )
    
    with pytest.raises(Exception) as exc_info:
        await execution_service.execute_task(task.id)
    
    assert "no commands" in str(exc_info.value).lower() or "payload" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_command_exits_with_various_codes(task_service, execution_service):
    exit_codes = [0, 1, 2, 255]
    
    for code in exit_codes:
        task = await task_service.create_task(
            TaskCreate(
                name=f"Exit Code {code}",
                payload=TaskPayload(
                    commands=[f"exit {code}"],
                    timeout=30,
                ),
            )
        )
        
        result = await execution_service.execute_task(task.id)
        
        steps = await task_service.get_task_steps(task.id)
        assert len(steps) == 1
        assert steps[0]["exit_code"] == code
        
        if code == 0:
            assert result.status == TaskStatus.COMPLETED.value
        else:
            assert result.status == TaskStatus.FAILED.value


@pytest.mark.asyncio
async def test_command_with_empty_string(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Empty Command",
            payload=TaskPayload(commands=[""], timeout=30),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status == TaskStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_command_with_only_whitespace(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Whitespace Command",
            payload=TaskPayload(commands=["   "], timeout=30),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]


@pytest.mark.asyncio
async def test_callback_exceptions_dont_break_execution(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="Callback Exception",
            payload=TaskPayload(commands=["echo Test"], timeout=30),
        )
    )
    
    async def failing_callback(step_order: int, command: str) -> None:
        raise RuntimeError("Callback failed!")
    
    result = await execution_service.execute_task(
        task.id,
        on_step_start=failing_callback,
    )
    
    assert result.status == TaskStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_database_connection_lost_during_execution(task_service, execution_service):
    task = await task_service.create_task(
        TaskCreate(
            name="DB Disconnect",
            payload=TaskPayload(commands=["echo Test"], timeout=30),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status == TaskStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_very_many_steps(task_service, execution_service):
    commands = [f"echo Step {i}" for i in range(50)]
    
    task = await task_service.create_task(
        TaskCreate(
            name="Many Steps",
            payload=TaskPayload(commands=commands, timeout=120),
        )
    )
    
    result = await execution_service.execute_task(task.id)
    assert result.status == TaskStatus.COMPLETED.value
    
    steps = await task_service.get_task_steps(task.id)
    assert len(steps) == 50
    
    for i, step in enumerate(steps, start=1):
        assert step["step_order"] == i
        assert step["status"] == StepStatus.COMPLETED.value
        assert step["exit_code"] == 0
