import asyncio
import pytest
from datetime import datetime
from plasmaagent.ai.parallel import (
    ParallelGroup,
    ParallelResult,
    StepResult,
    StepStatus,
    ParallelExecutor,
)


class TestStepResult:
    def test_step_result_creation(self):
        result = StepResult(
            step_id="step1",
            status=StepStatus.COMPLETED,
            output="success",
            exit_code=0,
            duration_ms=100,
        )
        assert result.step_id == "step1"
        assert result.status == StepStatus.COMPLETED
        assert result.output == "success"
        assert result.exit_code == 0
        assert result.duration_ms == 100
    
    def test_step_result_is_success(self):
        result = StepResult(
            step_id="step1",
            status=StepStatus.COMPLETED,
            exit_code=0,
            duration_ms=100,
        )
        assert result.is_success() is True
    
    def test_step_result_is_success_non_zero_exit(self):
        result = StepResult(
            step_id="step1",
            status=StepStatus.COMPLETED,
            exit_code=1,
            duration_ms=100,
        )
        assert result.is_success() is False
    
    def test_step_result_is_failure(self):
        result = StepResult(
            step_id="step1",
            status=StepStatus.FAILED,
            error="error",
            duration_ms=100,
        )
        assert result.is_failure() is True
    
    def test_step_result_cancelled_is_failure(self):
        result = StepResult(
            step_id="step1",
            status=StepStatus.CANCELLED,
            duration_ms=100,
        )
        assert result.is_failure() is True
    
    def test_step_result_frozen(self):
        result = StepResult(
            step_id="step1",
            status=StepStatus.COMPLETED,
            exit_code=0,
            duration_ms=100,
        )
        with pytest.raises(Exception):
            result.step_id = "step2"


class TestParallelGroup:
    def test_parallel_group_creation(self):
        group = ParallelGroup(
            group_id="group1",
            step_ids=["step1", "step2", "step3"],
        )
        assert group.group_id == "group1"
        assert len(group.step_ids) == 3
        assert group.timeout_seconds == 300.0
        assert group.max_concurrent == 10
        assert group.fail_fast is True
    
    def test_parallel_group_custom_values(self):
        group = ParallelGroup(
            group_id="group1",
            step_ids=["step1"],
            timeout_seconds=60.0,
            max_concurrent=5,
            fail_fast=False,
        )
        assert group.timeout_seconds == 60.0
        assert group.max_concurrent == 5
        assert group.fail_fast is False
    
    def test_parallel_group_frozen(self):
        group = ParallelGroup(
            group_id="group1",
            step_ids=["step1"],
        )
        with pytest.raises(Exception):
            group.group_id = "group2"
    
    def test_parallel_group_empty_steps(self):
        with pytest.raises(Exception):
            ParallelGroup(group_id="group1", step_ids=[])
    
    def test_parallel_group_too_many_steps(self):
        with pytest.raises(Exception):
            ParallelGroup(group_id="group1", step_ids=[f"step{i}" for i in range(51)])


class TestParallelResult:
    def test_parallel_result_from_results(self):
        results = [
            StepResult(step_id="s1", status=StepStatus.COMPLETED, exit_code=0, duration_ms=100),
            StepResult(step_id="s2", status=StepStatus.COMPLETED, exit_code=0, duration_ms=200),
            StepResult(step_id="s3", status=StepStatus.FAILED, exit_code=1, duration_ms=150),
        ]
        
        result = ParallelResult.from_results("group1", results, 500)
        
        assert result.group_id == "group1"
        assert len(result.results) == 3
        assert result.total_duration_ms == 500
        assert result.success_count == 2
        assert result.failure_count == 1
        assert result.cancelled_count == 0
    
    def test_parallel_result_all_succeeded(self):
        results = [
            StepResult(step_id="s1", status=StepStatus.COMPLETED, exit_code=0, duration_ms=100),
            StepResult(step_id="s2", status=StepStatus.COMPLETED, exit_code=0, duration_ms=200),
        ]
        
        result = ParallelResult.from_results("group1", results, 300)
        assert result.all_succeeded() is True
        assert result.any_failed() is False
    
    def test_parallel_result_any_failed(self):
        results = [
            StepResult(step_id="s1", status=StepStatus.COMPLETED, exit_code=0, duration_ms=100),
            StepResult(step_id="s2", status=StepStatus.FAILED, exit_code=1, duration_ms=200),
        ]
        
        result = ParallelResult.from_results("group1", results, 300)
        assert result.all_succeeded() is False
        assert result.any_failed() is True
    
    def test_parallel_result_get_failed_steps(self):
        results = [
            StepResult(step_id="s1", status=StepStatus.COMPLETED, exit_code=0, duration_ms=100),
            StepResult(step_id="s2", status=StepStatus.FAILED, exit_code=1, duration_ms=200),
            StepResult(step_id="s3", status=StepStatus.CANCELLED, duration_ms=50),
        ]
        
        result = ParallelResult.from_results("group1", results, 350)
        failed = result.get_failed_steps()
        
        assert len(failed) == 2
        assert failed[0].step_id == "s2"
        assert failed[1].step_id == "s3"
    
    def test_parallel_result_frozen(self):
        results = [
            StepResult(step_id="s1", status=StepStatus.COMPLETED, exit_code=0, duration_ms=100),
        ]
        result = ParallelResult.from_results("group1", results, 100)
        with pytest.raises(Exception):
            result.group_id = "group2"


class TestParallelExecutorBasic:
    @pytest.mark.asyncio
    async def test_execute_group_all_success(self):
        async def mock_executor(step_id: str) -> StepResult:
            await asyncio.sleep(0.01)
            return StepResult(
                step_id=step_id,
                status=StepStatus.COMPLETED,
                output=f"output from {step_id}",
                exit_code=0,
                duration_ms=10,
            )
        
        group = ParallelGroup(
            group_id="group1",
            step_ids=["s1", "s2", "s3"],
            timeout_seconds=10.0,
        )
        
        executor = ParallelExecutor(max_concurrent=10)
        result = await executor.execute_group(group, mock_executor)
        
        assert result.group_id == "group1"
        assert len(result.results) == 3
        assert result.success_count == 3
        assert result.failure_count == 0
        assert result.all_succeeded() is True
    
    @pytest.mark.asyncio
    async def test_execute_group_with_failure(self):
        async def mock_executor(step_id: str) -> StepResult:
            await asyncio.sleep(0.01)
            if step_id == "s2":
                return StepResult(
                    step_id=step_id,
                    status=StepStatus.FAILED,
                    error="step2 failed",
                    exit_code=1,
                    duration_ms=10,
                )
            return StepResult(
                step_id=step_id,
                status=StepStatus.COMPLETED,
                exit_code=0,
                duration_ms=10,
            )
        
        group = ParallelGroup(
            group_id="group1",
            step_ids=["s1", "s2", "s3"],
            timeout_seconds=10.0,
            fail_fast=False,
        )
        
        executor = ParallelExecutor(max_concurrent=10)
        result = await executor.execute_group(group, mock_executor)
        
        assert result.success_count == 2
        assert result.failure_count == 1
        assert result.any_failed() is True
    
    @pytest.mark.asyncio
    async def test_execute_group_fail_fast(self):
        async def mock_executor(step_id: str) -> StepResult:
            if step_id == "s1":
                await asyncio.sleep(0.01)
                return StepResult(
                    step_id=step_id,
                    status=StepStatus.FAILED,
                    error="s1 failed",
                    exit_code=1,
                    duration_ms=10,
                )
            else:
                await asyncio.sleep(0.5)
                return StepResult(
                    step_id=step_id,
                    status=StepStatus.COMPLETED,
                    exit_code=0,
                    duration_ms=500,
                )
        
        group = ParallelGroup(
            group_id="group1",
            step_ids=["s1", "s2", "s3"],
            timeout_seconds=10.0,
            fail_fast=True,
        )
        
        executor = ParallelExecutor(max_concurrent=10)
        result = await executor.execute_group(group, mock_executor)
        
        assert result.failure_count >= 1
        assert any(r.status == StepStatus.CANCELLED for r in result.results)
    
    @pytest.mark.asyncio
    async def test_execute_group_timeout(self):
        async def slow_executor(step_id: str) -> StepResult:
            await asyncio.sleep(10.0)
            return StepResult(
                step_id=step_id,
                status=StepStatus.COMPLETED,
                exit_code=0,
                duration_ms=10000,
            )
        
        group = ParallelGroup(
            group_id="group1",
            step_ids=["s1", "s2"],
            timeout_seconds=0.1,
        )
        
        executor = ParallelExecutor(max_concurrent=10)
        result = await executor.execute_group(group, slow_executor)
        
        assert result.failure_count == 2
        assert all("Timeout" in r.error for r in result.results if r.error)
    
    @pytest.mark.asyncio
    async def test_execute_group_concurrency_limit(self):
        concurrent_count = 0
        max_concurrent = 0
        
        async def mock_executor(step_id: str) -> StepResult:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.05)
            concurrent_count -= 1
            return StepResult(
                step_id=step_id,
                status=StepStatus.COMPLETED,
                exit_code=0,
                duration_ms=50,
            )
        
        group = ParallelGroup(
            group_id="group1",
            step_ids=[f"s{i}" for i in range(10)],
            timeout_seconds=10.0,
        )
        
        executor = ParallelExecutor(max_concurrent=3)
        result = await executor.execute_group(group, mock_executor)
        
        assert result.success_count == 10
        assert max_concurrent <= 3
    
    @pytest.mark.asyncio
    async def test_execute_group_invalid_type(self):
        async def mock_executor(step_id: str) -> StepResult:
            return StepResult(step_id=step_id, status=StepStatus.COMPLETED, exit_code=0, duration_ms=0)
        
        executor = ParallelExecutor()
        with pytest.raises(TypeError, match="must be a ParallelGroup"):
            await executor.execute_group("not a group", mock_executor)
    
    @pytest.mark.asyncio
    async def test_execute_group_invalid_executor(self):
        group = ParallelGroup(group_id="group1", step_ids=["s1"])
        executor = ParallelExecutor()
        with pytest.raises(TypeError, match="must be a callable"):
            await executor.execute_group(group, "not a callable")


class TestParallelExecutorMultipleGroups:
    @pytest.mark.asyncio
    async def test_execute_multiple_groups_all_success(self):
        async def mock_executor(step_id: str) -> StepResult:
            await asyncio.sleep(0.01)
            return StepResult(
                step_id=step_id,
                status=StepStatus.COMPLETED,
                exit_code=0,
                duration_ms=10,
            )
        
        groups = [
            ParallelGroup(group_id="g1", step_ids=["s1", "s2"], timeout_seconds=10.0),
            ParallelGroup(group_id="g2", step_ids=["s3", "s4"], timeout_seconds=10.0),
        ]
        
        executor = ParallelExecutor(max_concurrent=10)
        results = await executor.execute_multiple_groups(groups, mock_executor)
        
        assert len(results) == 2
        assert all(r.all_succeeded() for r in results)
    
    @pytest.mark.asyncio
    async def test_execute_multiple_groups_stops_on_failure(self):
        async def mock_executor(step_id: str) -> StepResult:
            await asyncio.sleep(0.01)
            if step_id == "s2":
                return StepResult(
                    step_id=step_id,
                    status=StepStatus.FAILED,
                    error="failed",
                    exit_code=1,
                    duration_ms=10,
                )
            return StepResult(
                step_id=step_id,
                status=StepStatus.COMPLETED,
                exit_code=0,
                duration_ms=10,
            )
        
        groups = [
            ParallelGroup(group_id="g1", step_ids=["s1", "s2"], timeout_seconds=10.0),
            ParallelGroup(group_id="g2", step_ids=["s3", "s4"], timeout_seconds=10.0),
        ]
        
        executor = ParallelExecutor(max_concurrent=10)
        results = await executor.execute_multiple_groups(groups, mock_executor)
        
        assert len(results) == 1
        assert results[0].group_id == "g1"
    
    @pytest.mark.asyncio
    async def test_execute_multiple_groups_invalid_type(self):
        async def mock_executor(step_id: str) -> StepResult:
            return StepResult(step_id=step_id, status=StepStatus.COMPLETED, exit_code=0, duration_ms=0)
        
        executor = ParallelExecutor()
        with pytest.raises(TypeError, match="must be a list"):
            await executor.execute_multiple_groups("not a list", mock_executor)


class TestParallelExecutorPerformance:
    @pytest.mark.asyncio
    async def test_parallel_execution_speed(self):
        async def mock_executor(step_id: str) -> StepResult:
            await asyncio.sleep(0.1)
            return StepResult(
                step_id=step_id,
                status=StepStatus.COMPLETED,
                exit_code=0,
                duration_ms=100,
            )
        
        group = ParallelGroup(
            group_id="group1",
            step_ids=[f"s{i}" for i in range(5)],
            timeout_seconds=10.0,
        )
        
        executor = ParallelExecutor(max_concurrent=10)
        
        import time
        start = time.time()
        result = await executor.execute_group(group, mock_executor)
        elapsed = time.time() - start
        
        assert result.success_count == 5
        assert elapsed < 0.3, f"Parallel execution took {elapsed:.2f}s (expected < 0.3s)"
    
    @pytest.mark.asyncio
    async def test_sequential_execution_speed(self):
        async def mock_executor(step_id: str) -> StepResult:
            await asyncio.sleep(0.1)
            return StepResult(
                step_id=step_id,
                status=StepStatus.COMPLETED,
                exit_code=0,
                duration_ms=100,
            )
        
        group = ParallelGroup(
            group_id="group1",
            step_ids=[f"s{i}" for i in range(5)],
            timeout_seconds=10.0,
        )
        
        executor = ParallelExecutor(max_concurrent=1)
        
        import time
        start = time.time()
        result = await executor.execute_group(group, mock_executor)
        elapsed = time.time() - start
        
        assert result.success_count == 5
        assert elapsed >= 0.5, f"Sequential execution took {elapsed:.2f}s (expected >= 0.5s)"


class TestParallelExecutorEdgeCases:
    @pytest.mark.asyncio
    async def test_executor_raises_exception(self):
        async def failing_executor(step_id: str) -> StepResult:
            raise RuntimeError("executor crashed")
        
        group = ParallelGroup(
            group_id="group1",
            step_ids=["s1"],
            timeout_seconds=10.0,
        )
        
        executor = ParallelExecutor(max_concurrent=10)
        result = await executor.execute_group(group, failing_executor)
        
        assert result.failure_count == 1
        assert "Execution error" in result.results[0].error
    
    @pytest.mark.asyncio
    async def test_empty_output_and_error(self):
        async def mock_executor(step_id: str) -> StepResult:
            return StepResult(
                step_id=step_id,
                status=StepStatus.COMPLETED,
                exit_code=0,
                duration_ms=10,
            )
        
        group = ParallelGroup(group_id="group1", step_ids=["s1"], timeout_seconds=10.0)
        executor = ParallelExecutor()
        result = await executor.execute_group(group, mock_executor)
        
        assert result.results[0].output is None
        assert result.results[0].error is None
