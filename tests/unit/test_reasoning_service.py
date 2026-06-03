from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import pytest

from plasmaagent.ai.context.manager import ContextManager
from plasmaagent.ai.reasoning import (
    ReasoningPlan,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningService,
    StepResult,
    StepStatus,
)


class TestReasoningRequest:
    def test_valid_request(self) -> None:
        req = ReasoningRequest(natural_language="backup database")
        assert req.natural_language == "backup database"
        assert req.max_parallel == 5
        assert req.max_retries == 3
        assert req.fail_fast is True

    def test_empty_input_rejected(self) -> None:
        with pytest.raises(Exception):
            ReasoningRequest(natural_language="")

    def test_input_too_long_rejected(self) -> None:
        with pytest.raises(Exception):
            ReasoningRequest(natural_language="x" * 10001)

    def test_invalid_max_parallel_rejected(self) -> None:
        with pytest.raises(Exception):
            ReasoningRequest(natural_language="test", max_parallel=0)
        with pytest.raises(Exception):
            ReasoningRequest(natural_language="test", max_parallel=51)

    def test_invalid_max_retries_rejected(self) -> None:
        with pytest.raises(Exception):
            ReasoningRequest(natural_language="test", max_retries=-1)
        with pytest.raises(Exception):
            ReasoningRequest(natural_language="test", max_retries=11)

    def test_invalid_timeout_rejected(self) -> None:
        with pytest.raises(Exception):
            ReasoningRequest(natural_language="test", timeout_seconds=0.0)
        with pytest.raises(Exception):
            ReasoningRequest(natural_language="test", timeout_seconds=86401.0)

    def test_with_context_variables(self) -> None:
        req = ReasoningRequest(
            natural_language="test",
            context_variables={"db_name": "plasmaagent", "path": "/tmp"},
        )
        assert req.context_variables["db_name"] == "plasmaagent"

    def test_with_session_id(self) -> None:
        req = ReasoningRequest(natural_language="test", session_id="my_session")
        assert req.session_id == "my_session"


class TestReasoningPlan:
    def test_create_plan_single_task(self) -> None:
        service = ReasoningService()
        req = ReasoningRequest(natural_language="backup database postgresql")
        plan = service.create_plan(req)

        assert isinstance(plan, ReasoningPlan)
        assert plan.total_steps == 1
        assert plan.execution_mode == "sequential"
        assert len(plan.steps) == 1

    def test_create_plan_multi_step(self) -> None:
        service = ReasoningService()
        req = ReasoningRequest(natural_language="backup database then verify backup")
        plan = service.create_plan(req)

        assert plan.total_steps == 2
        assert len(plan.steps) == 2

    def test_create_plan_with_custom_session(self) -> None:
        service = ReasoningService()
        req = ReasoningRequest(natural_language="test", session_id="custom_session_123")
        plan = service.create_plan(req)

        assert plan.session_id == "custom_session_123"

    def test_plan_has_estimated_duration(self) -> None:
        service = ReasoningService()
        req = ReasoningRequest(natural_language="step 1 then step 2 then step 3")
        plan = service.create_plan(req)

        assert plan.estimated_duration_ms > 0


class TestReasoningServiceBasicExecution:
    @pytest.mark.asyncio
    async def test_execute_single_task(self) -> None:
        service = ReasoningService()
        req = ReasoningRequest(natural_language="backup database")

        response = await service.execute(req)

        assert isinstance(response, ReasoningResponse)
        assert response.success is True
        assert response.total_steps == 1
        assert response.completed_steps == 1
        assert response.failed_steps == 0
        assert len(response.step_results) == 1

    @pytest.mark.asyncio
    async def test_execute_multi_step_sequential(self) -> None:
        service = ReasoningService()
        req = ReasoningRequest(natural_language="backup database then verify backup then cleanup")

        response = await service.execute(req)

        assert response.success is True
        assert response.total_steps == 3
        assert response.completed_steps == 3

    @pytest.mark.asyncio
    async def test_execute_with_custom_executor(self) -> None:
        service = ReasoningService()

        call_count = 0

        async def custom_executor(nl: str, ctx: ContextManager) -> tuple[int, str, str]:
            nonlocal call_count
            call_count += 1
            return 0, f"Custom: {nl}", ""

        req = ReasoningRequest(natural_language="step 1 then step 2")
        response = await service.execute(req, step_executor=custom_executor)

        assert response.success is True
        assert call_count == 2
        assert all("Custom:" in (r.output or "") for r in response.step_results)

    @pytest.mark.asyncio
    async def test_execute_returns_session_id(self) -> None:
        service = ReasoningService()
        req = ReasoningRequest(natural_language="test", session_id="my_session")

        response = await service.execute(req)

        assert response.session_id == "my_session"

    @pytest.mark.asyncio
    async def test_execute_auto_generates_session_id(self) -> None:
        service = ReasoningService()
        req = ReasoningRequest(natural_language="test")

        response = await service.execute(req)

        assert response.session_id.startswith("session_")


class TestReasoningServiceFailureHandling:
    @pytest.mark.asyncio
    async def test_execute_with_step_failure(self) -> None:
        service = ReasoningService()

        async def failing_executor(nl: str, ctx: ContextManager) -> tuple[int, str, str]:
            return 1, "", "Step failed"

        req = ReasoningRequest(natural_language="step 1 then step 2", fail_fast=True, max_retries=0)
        response = await service.execute(req, step_executor=failing_executor)

        assert response.success is False
        assert response.failed_steps >= 1

    @pytest.mark.asyncio
    async def test_fail_fast_stops_on_first_failure(self) -> None:
        service = ReasoningService()

        call_count = 0

        async def failing_first(nl: str, ctx: ContextManager) -> tuple[int, str, str]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 1, "", "First step failed"
            return 0, "OK", ""

        req = ReasoningRequest(natural_language="step 1 then step 2 then step 3", fail_fast=True, max_retries=0)
        response = await service.execute(req, step_executor=failing_first)

        assert response.success is False
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_no_fail_fast_continues_after_failure(self) -> None:
        service = ReasoningService()

        call_count = 0

        async def failing_first(nl: str, ctx: ContextManager) -> tuple[int, str, str]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 1, "", "First step failed"
            return 0, "OK", ""

        req = ReasoningRequest(natural_language="step 1 then step 2 then step 3", fail_fast=False, max_retries=0)
        response = await service.execute(req, step_executor=failing_first)

        assert call_count == 3
        assert response.failed_steps == 1
        assert response.completed_steps == 2


class TestReasoningServiceRetry:
    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(self) -> None:
        service = ReasoningService()

        attempt_count = 0

        async def flaky_executor(nl: str, ctx: ContextManager) -> tuple[int, str, str]:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                return 1, "", "Transient error"
            return 0, "Success after retry", ""

        req = ReasoningRequest(natural_language="test", max_retries=3)
        response = await service.execute(req, step_executor=flaky_executor)

        assert response.success is True
        assert attempt_count == 3
        assert response.step_results[0].retry_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self) -> None:
        service = ReasoningService()

        async def always_fail(nl: str, ctx: ContextManager) -> tuple[int, str, str]:
            return 1, "", "Always fails"

        req = ReasoningRequest(natural_language="test", max_retries=2)
        response = await service.execute(req, step_executor=always_fail)

        assert response.success is False
        assert response.step_results[0].retry_count == 2


class TestReasoningServiceContext:
    @pytest.mark.asyncio
    async def test_context_variables_passed_to_executor(self) -> None:
        service = ReasoningService()

        captured_context: dict[str, Any] = {}

        async def capturing_executor(nl: str, ctx: ContextManager) -> tuple[int, str, str]:
            captured_context["db_name"] = ctx.get_variable("db_name")
            captured_context["path"] = ctx.get_variable("path")
            return 0, "OK", ""

        req = ReasoningRequest(
            natural_language="backup",
            context_variables={"db_name": "plasmaagent", "path": "/backups"},
        )
        response = await service.execute(req, step_executor=capturing_executor)

        assert response.success is True
        assert captured_context["db_name"] == "plasmaagent"
        assert captured_context["path"] == "/backups"

    @pytest.mark.asyncio
    async def test_context_updated_after_execution(self) -> None:
        service = ReasoningService()

        async def output_executor(nl: str, ctx: ContextManager) -> tuple[int, str, str]:
            return 0, "output_value_123", ""

        req = ReasoningRequest(natural_language="test")
        response = await service.execute(req, step_executor=output_executor)

        assert response.success is True
        assert "t0.output" in response.context_variables
        assert response.context_variables["t0.output"] == "output_value_123"

    @pytest.mark.asyncio
    async def test_variable_substitution_in_steps(self) -> None:
        service = ReasoningService()

        captured_inputs: list[str] = []

        async def capturing_executor(nl: str, ctx: ContextManager) -> tuple[int, str, str]:
            captured_inputs.append(nl)
            return 0, "result_abc", ""

        req = ReasoningRequest(
            natural_language="backup ${db_name} then verify ${t0.output}",
            context_variables={"db_name": "mydb"},
        )
        response = await service.execute(req, step_executor=capturing_executor)

        assert response.success is True
        assert "backup mydb" in captured_inputs[0]


class TestReasoningServiceEdgeCases:
    @pytest.mark.asyncio
    async def test_executor_raises_exception(self) -> None:
        service = ReasoningService()

        async def crashing_executor(nl: str, ctx: ContextManager) -> tuple[int, str, str]:
            raise RuntimeError("Executor crashed")

        req = ReasoningRequest(natural_language="test", max_retries=0)
        response = await service.execute(req, step_executor=crashing_executor)

        assert response.success is False
        assert response.step_results[0].status == StepStatus.FAILED

    @pytest.mark.asyncio
    async def test_performance_single_step(self) -> None:
        service = ReasoningService()
        req = ReasoningRequest(natural_language="simple task")

        response = await service.execute(req)

        assert response.total_duration_ms < 5000

    @pytest.mark.asyncio
    async def test_performance_multi_step(self) -> None:
        service = ReasoningService()
        req = ReasoningRequest(natural_language="step 1 then step 2 then step 3 then step 4 then step 5")

        response = await service.execute(req)

        assert response.total_duration_ms < 10000

    @pytest.mark.asyncio
    async def test_step_results_have_timestamps(self) -> None:
        service = ReasoningService()
        req = ReasoningRequest(natural_language="test")

        response = await service.execute(req)

        assert response.step_results[0].started_at is not None
        assert response.step_results[0].completed_at is not None

    @pytest.mark.asyncio
    async def test_step_results_have_duration(self) -> None:
        service = ReasoningService()
        req = ReasoningRequest(natural_language="test")

        response = await service.execute(req)

        assert response.step_results[0].duration_ms >= 0

    @pytest.mark.asyncio
    async def test_response_has_decomposition_time(self) -> None:
        service = ReasoningService()
        req = ReasoningRequest(natural_language="test")

        response = await service.execute(req)

        assert response.decomposition_time_ms >= 0


class TestStepResult:
    def test_create_completed_result(self) -> None:
        result = StepResult(
            step_id="t0",
            natural_language="backup database",
            status=StepStatus.COMPLETED,
            output="Backup completed",
            exit_code=0,
            duration_ms=100,
        )
        assert result.status == StepStatus.COMPLETED
        assert result.exit_code == 0

    def test_create_failed_result(self) -> None:
        result = StepResult(
            step_id="t0",
            natural_language="backup database",
            status=StepStatus.FAILED,
            error="Connection refused",
            exit_code=1,
            duration_ms=50,
        )
        assert result.status == StepStatus.FAILED
        assert result.error == "Connection refused"

    def test_frozen_model(self) -> None:
        result = StepResult(
            step_id="t0",
            natural_language="test",
            status=StepStatus.COMPLETED,
        )
        with pytest.raises(Exception):
            result.status = StepStatus.FAILED

    def test_with_retry_count(self) -> None:
        result = StepResult(
            step_id="t0",
            natural_language="test",
            status=StepStatus.COMPLETED,
            retry_count=2,
        )
        assert result.retry_count == 2


class TestReasoningResponse:
    def test_successful_response(self) -> None:
        response = ReasoningResponse(
            session_id="session_123",
            original_input="test",
            total_steps=3,
            completed_steps=3,
            failed_steps=0,
            skipped_steps=0,
            step_results=tuple(),
            context_variables={},
            total_duration_ms=500,
            decomposition_time_ms=10.0,
            success=True,
        )
        assert response.success is True
        assert response.completed_steps == 3

    def test_failed_response(self) -> None:
        response = ReasoningResponse(
            session_id="session_123",
            original_input="test",
            total_steps=3,
            completed_steps=2,
            failed_steps=1,
            skipped_steps=0,
            step_results=tuple(),
            context_variables={},
            total_duration_ms=500,
            decomposition_time_ms=10.0,
            success=False,
            error_message="1 step failed",
        )
        assert response.success is False
        assert response.error_message == "1 step failed"

    def test_frozen_model(self) -> None:
        response = ReasoningResponse(
            session_id="session_123",
            original_input="test",
            total_steps=1,
            completed_steps=1,
            failed_steps=0,
            skipped_steps=0,
            step_results=tuple(),
            context_variables={},
            total_duration_ms=100,
            decomposition_time_ms=5.0,
            success=True,
        )
        with pytest.raises(Exception):
            response.success = False
