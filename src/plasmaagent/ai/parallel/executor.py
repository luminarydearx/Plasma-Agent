import asyncio
import time
from typing import Callable, Awaitable
from datetime import datetime
from .models import ParallelGroup, ParallelResult, StepResult, StepStatus


StepExecutor = Callable[[str], Awaitable[StepResult]]


class ParallelExecutor:
    def __init__(self, max_concurrent: int = 10):
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def execute_group(
        self,
        group: ParallelGroup,
        executor: StepExecutor,
        cancel_event: asyncio.Event | None = None
    ) -> ParallelResult:
        if not isinstance(group, ParallelGroup):
            raise TypeError("group must be a ParallelGroup instance")
        
        if not callable(executor):
            raise TypeError("executor must be a callable")
        
        start_time = time.time()
        cancel_event = cancel_event or asyncio.Event()
        
        async_tasks = []
        try:
            results = await asyncio.wait_for(
                self._execute_with_concurrency(group, executor, cancel_event, async_tasks),
                timeout=group.timeout_seconds
            )
        except asyncio.TimeoutError:
            for task in async_tasks:
                if not task.done():
                    task.cancel()
            
            await asyncio.gather(*async_tasks, return_exceptions=True)
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            timeout_results = [
                StepResult(
                    step_id=step_id,
                    status=StepStatus.FAILED,
                    error=f"Timeout after {group.timeout_seconds}s",
                    duration_ms=elapsed_ms,
                )
                for step_id in group.step_ids
            ]
            return ParallelResult.from_results(group.group_id, timeout_results, elapsed_ms)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        return ParallelResult.from_results(group.group_id, results, elapsed_ms)
    
    async def _execute_with_concurrency(
        self,
        group: ParallelGroup,
        executor: StepExecutor,
        cancel_event: asyncio.Event,
        async_tasks: list[asyncio.Task]
    ) -> list[StepResult]:
        tasks_with_ids = []
        for step_id in group.step_ids:
            task = asyncio.create_task(
                self._execute_step(step_id, executor, cancel_event, group.fail_fast)
            )
            async_tasks.append(task)
            tasks_with_ids.append((step_id, task))
        
        results = []
        for step_id, task in tasks_with_ids:
            try:
                result = await task
                results.append(result)
                
                if group.fail_fast and result.is_failure():
                    cancel_event.set()
                    
                    for remaining_step_id, remaining_task in tasks_with_ids:
                        if remaining_step_id != step_id and not remaining_task.done():
                            remaining_task.cancel()
                            try:
                                cancelled_result = await remaining_task
                                results.append(cancelled_result)
                            except asyncio.CancelledError:
                                results.append(
                                    StepResult(
                                        step_id=remaining_step_id,
                                        status=StepStatus.CANCELLED,
                                        error="Cancelled due to fail_fast",
                                        duration_ms=0,
                                    )
                                )
                    
                    break
            except asyncio.CancelledError:
                raise
            except Exception as e:
                results.append(
                    StepResult(
                        step_id=step_id,
                        status=StepStatus.FAILED,
                        error=f"Unexpected error: {str(e)}",
                        duration_ms=0,
                    )
                )
        
        return results
    
    async def _execute_step(
        self,
        step_id: str,
        executor: StepExecutor,
        cancel_event: asyncio.Event,
        fail_fast: bool
    ) -> StepResult:
        if cancel_event.is_set():
            return StepResult(
                step_id=step_id,
                status=StepStatus.CANCELLED,
                error="Cancelled due to fail_fast",
                duration_ms=0,
            )
        
        async with self._semaphore:
            if cancel_event.is_set():
                return StepResult(
                    step_id=step_id,
                    status=StepStatus.CANCELLED,
                    error="Cancelled due to fail_fast",
                    duration_ms=0,
                )
            
            start_time = time.time()
            started_at = datetime.now()
            
            try:
                result = await executor(step_id)
                duration_ms = int((time.time() - start_time) * 1000)
                
                return StepResult(
                    step_id=step_id,
                    status=result.status,
                    output=result.output,
                    error=result.error,
                    exit_code=result.exit_code,
                    duration_ms=duration_ms,
                    started_at=started_at,
                    completed_at=datetime.now(),
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                return StepResult(
                    step_id=step_id,
                    status=StepStatus.FAILED,
                    error=f"Execution error: {str(e)}",
                    duration_ms=duration_ms,
                    started_at=started_at,
                    completed_at=datetime.now(),
                )
    
    async def execute_multiple_groups(
        self,
        groups: list[ParallelGroup],
        executor: StepExecutor
    ) -> list[ParallelResult]:
        if not isinstance(groups, list):
            raise TypeError("groups must be a list")
        
        results = []
        for group in groups:
            result = await self.execute_group(group, executor)
            results.append(result)
            
            if result.any_failed():
                break
        
        return results
