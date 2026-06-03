from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Awaitable, Callable

from plasmaagent.ai.conditional.evaluator import ConditionEvaluator
from plasmaagent.ai.context.manager import ContextManager
from plasmaagent.ai.context.models import ContextVariableType, TaskExecutionResult
from plasmaagent.ai.dag.graph import DependencyGraph
from plasmaagent.ai.decomposer.engine import TaskDecomposer
from plasmaagent.ai.reasoning.models import (
    ReasoningPlan,
    ReasoningRequest,
    ReasoningResponse,
    StepResult,
    StepStatus,
)
from plasmaagent.ai.recovery.analyzer import ErrorAnalyzer
from plasmaagent.ai.retry.executor import RetryExecutor
from plasmaagent.ai.retry.models import RetryConfig

StepExecutor = Callable[[str, ContextManager], Awaitable[tuple[int, str, str]]]


class ReasoningService:
    def __init__(self) -> None:
        self._decomposer = TaskDecomposer()
        self._evaluator = ConditionEvaluator()
        self._error_analyzer = ErrorAnalyzer()

    def create_plan(self, request: ReasoningRequest) -> ReasoningPlan:
        session_id = request.session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        decomposed = self._decomposer.decompose(request.natural_language)

        steps_data: list[dict[str, Any]] = []
        for sub_task in decomposed.sub_tasks:
            steps_data.append({
                "step_id": sub_task.task_id,
                "natural_language": sub_task.natural_language,
                "depends_on": list(sub_task.depends_on),
                "parallel_group": sub_task.parallel_group,
                "priority": sub_task.priority,
            })

        estimated_duration = len(decomposed.sub_tasks) * 1000

        return ReasoningPlan(
            session_id=session_id,
            original_input=request.natural_language,
            total_steps=len(decomposed.sub_tasks),
            execution_mode=decomposed.execution_mode.value,
            parallel_groups=decomposed.total_parallel_groups,
            estimated_duration_ms=estimated_duration,
            steps=tuple(steps_data),
            created_at=datetime.now(),
        )

    async def execute(
        self,
        request: ReasoningRequest,
        step_executor: StepExecutor | None = None,
    ) -> ReasoningResponse:
        start_time = time.monotonic()
        session_id = request.session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        context = ContextManager(session_id)
        for var_name, var_value in request.context_variables.items():
            context.set_variable(var_name, var_value, ContextVariableType.CUSTOM)

        try:
            decomposed = self._decomposer.decompose(request.natural_language)
            decomposition_time = decomposed.decomposition_time_ms
        except Exception as exc:
            return self._build_error_response(
                session_id,
                request.natural_language,
                f"Decomposition failed: {exc}",
                start_time,
                decomposition_time=0.0,
            )

        if not decomposed.sub_tasks:
            return self._build_error_response(
                session_id,
                request.natural_language,
                "No sub-tasks generated",
                start_time,
                decomposition_time=decomposition_time,
            )

        graph = DependencyGraph()
        for sub_task in decomposed.sub_tasks:
            graph.add_node(
                node_id=sub_task.task_id,
                name=sub_task.natural_language[:200],
                metadata={"natural_language": sub_task.natural_language},
            )

        for sub_task in decomposed.sub_tasks:
            for dep_id in sub_task.depends_on:
                graph.add_edge(from_node=dep_id, to_node=sub_task.task_id)

        execution_plan = graph.get_execution_plan()
        if execution_plan.has_cycles:
            return self._build_error_response(
                session_id,
                request.natural_language,
                f"Cyclic dependency detected: {execution_plan.cycle_nodes}",
                start_time,
                decomposition_time=decomposition_time,
            )

        step_results: list[StepResult] = []
        retry_config = RetryConfig(max_attempts=request.max_retries + 1)
        retry_executor = RetryExecutor(retry_config)

        executor = step_executor or self._default_step_executor

        for group in execution_plan.parallel_groups:
            group_results: list[StepResult] = []
            for node_id in group:
                result = await self._execute_single_step(
                    node_id,
                    decomposed,
                    context,
                    executor,
                    retry_executor,
                )
                group_results.append(result)

            step_results.extend(group_results)

            if any(r.status == StepStatus.FAILED for r in group_results) and request.fail_fast:
                break

        total_duration = int((time.monotonic() - start_time) * 1000)
        completed = sum(1 for r in step_results if r.status == StepStatus.COMPLETED)
        failed = sum(1 for r in step_results if r.status == StepStatus.FAILED)
        skipped = sum(1 for r in step_results if r.status == StepStatus.SKIPPED)
        success = failed == 0 and completed == len(decomposed.sub_tasks)

        context_vars = {name: context.get_variable(name) for name in context.list_variables()}

        return ReasoningResponse(
            session_id=session_id,
            original_input=request.natural_language,
            total_steps=len(decomposed.sub_tasks),
            completed_steps=completed,
            failed_steps=failed,
            skipped_steps=skipped,
            step_results=tuple(step_results),
            context_variables=context_vars,
            total_duration_ms=total_duration,
            decomposition_time_ms=decomposition_time,
            success=success,
            error_message=None if success else f"{failed} step(s) failed",
            created_at=datetime.now(),
        )

    async def _execute_single_step(
        self,
        node_id: str,
        decomposed: Any,
        context: ContextManager,
        executor: StepExecutor,
        retry_executor: RetryExecutor,
    ) -> StepResult:
        sub_task = next((t for t in decomposed.sub_tasks if t.task_id == node_id), None)
        if sub_task is None:
            return StepResult(
                step_id=node_id,
                natural_language="",
                status=StepStatus.FAILED,
                error="Step not found in decomposed task",
                duration_ms=0,
            )

        substituted_nl = context.substitute(sub_task.natural_language)
        started_at = datetime.now()

        def make_operation() -> Callable[[], Awaitable[tuple[int, str, str]]]:
            async def op() -> tuple[int, str, str]:
                return await executor(substituted_nl, context)
            return op

        retry_result = await retry_executor.execute(make_operation())

        completed_at = datetime.now()
        duration_ms = retry_result.total_duration_ms

        final_attempt = retry_result.attempts[-1] if retry_result.attempts else None
        exit_code = final_attempt.exit_code if final_attempt else None
        output = final_attempt.output if final_attempt else None
        error = final_attempt.error if final_attempt else None

        if retry_result.final_status.value == "success":
            status = StepStatus.COMPLETED
        elif retry_result.final_status.value == "cancelled":
            status = StepStatus.CANCELLED
        else:
            status = StepStatus.FAILED

        task_result = TaskExecutionResult(
            task_id=sub_task.task_id,
            status=status.value,
            output=output,
            stdout=output,
            stderr=error,
            error=error,
            exit_code=exit_code,
            duration_ms=duration_ms,
        )
        context.record_task_result(task_result)

        return StepResult(
            step_id=sub_task.task_id,
            natural_language=substituted_nl,
            status=status,
            output=output,
            error=error,
            exit_code=exit_code,
            duration_ms=duration_ms,
            retry_count=retry_result.total_attempts - 1,
            started_at=started_at,
            completed_at=completed_at,
        )

    async def _default_step_executor(
        self, natural_language: str, context: ContextManager
    ) -> tuple[int, str, str]:
        return 0, f"Executed: {natural_language}", ""

    def _build_error_response(
        self,
        session_id: str,
        original_input: str,
        error_message: str,
        start_time: float,
        decomposition_time: float,
    ) -> ReasoningResponse:
        total_duration = int((time.monotonic() - start_time) * 1000)
        return ReasoningResponse(
            session_id=session_id,
            original_input=original_input,
            total_steps=0,
            completed_steps=0,
            failed_steps=0,
            skipped_steps=0,
            step_results=tuple(),
            context_variables={},
            total_duration_ms=total_duration,
            decomposition_time_ms=decomposition_time,
            success=False,
            error_message=error_message,
            created_at=datetime.now(),
        )
