from __future__ import annotations

import asyncio
import time

import pytest

from plasmaagent.ai.retry import (
    AttemptResult,
    AttemptStatus,
    RetryConfig,
    RetryExecutor,
    RetryResult,
)


class TestRetryConfig:
    def test_default_values(self) -> None:
        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert cfg.base_delay_seconds == 1.0
        assert cfg.max_delay_seconds == 60.0
        assert cfg.backoff_factor == 2.0
        assert cfg.jitter is True

    def test_custom_values(self) -> None:
        cfg = RetryConfig(
            max_attempts=5,
            base_delay_seconds=0.1,
            max_delay_seconds=10.0,
            backoff_factor=1.5,
            jitter=False,
            retryable_exceptions=("ValueError",),
            retry_on_exit_codes=(1, 2),
        )
        assert cfg.max_attempts == 5
        assert cfg.retryable_exceptions == ("ValueError",)
        assert cfg.retry_on_exit_codes == (1, 2)

    def test_frozen(self) -> None:
        cfg = RetryConfig()
        with pytest.raises(Exception):
            cfg.max_attempts = 10  # type: ignore[misc]

    def test_invalid_max_attempts(self) -> None:
        with pytest.raises(Exception):
            RetryConfig(max_attempts=0)
        with pytest.raises(Exception):
            RetryConfig(max_attempts=100)

    def test_max_delay_less_than_base(self) -> None:
        with pytest.raises(ValueError):
            RetryConfig(base_delay_seconds=10.0, max_delay_seconds=5.0)

    def test_invalid_backoff(self) -> None:
        with pytest.raises(Exception):
            RetryConfig(backoff_factor=0.5)
        with pytest.raises(Exception):
            RetryConfig(backoff_factor=20.0)


class TestAttemptResult:
    def test_creation(self) -> None:
        r = AttemptResult(
            attempt_number=1,
            status=AttemptStatus.SUCCESS,
            output="ok",
            exit_code=0,
            duration_ms=50,
        )
        assert r.attempt_number == 1
        assert r.is_success()
        assert not r.is_failure()

    def test_failure(self) -> None:
        r = AttemptResult(
            attempt_number=2,
            status=AttemptStatus.FAILED,
            error="bad",
            exit_code=1,
            duration_ms=30,
        )
        assert r.is_failure()
        assert not r.is_success()
        assert r.exception_type is None

    def test_with_exception_type(self) -> None:
        r = AttemptResult(
            attempt_number=1,
            status=AttemptStatus.FAILED,
            error="boom",
            exception_type="ValueError",
            duration_ms=10,
        )
        assert r.exception_type == "ValueError"


class TestRetryResult:
    def test_succeeded_property(self) -> None:
        cfg = RetryConfig(max_attempts=1)
        r = RetryResult(
            config=cfg,
            attempts=(AttemptResult(attempt_number=1, status=AttemptStatus.SUCCESS, duration_ms=10),),
            final_status=AttemptStatus.SUCCESS,
            total_duration_ms=10,
            total_attempts=1,
        )
        assert r.succeeded is True
        assert r.failure_count() == 0
        assert r.last_attempt is not None

    def test_failed_property(self) -> None:
        cfg = RetryConfig(max_attempts=2)
        attempts = (
            AttemptResult(attempt_number=1, status=AttemptStatus.FAILED, duration_ms=10),
            AttemptResult(attempt_number=2, status=AttemptStatus.FAILED, duration_ms=10),
        )
        r = RetryResult(
            config=cfg,
            attempts=attempts,
            final_status=AttemptStatus.FAILED,
            total_duration_ms=20,
            total_attempts=2,
        )
        assert r.succeeded is False
        assert r.failure_count() == 2

    def test_empty_attempts(self) -> None:
        r = RetryResult(
            config=RetryConfig(),
            final_status=AttemptStatus.SKIPPED,
            total_duration_ms=0,
            total_attempts=0,
        )
        assert r.last_attempt is None


class TestRetryExecutorBasic:
    @pytest.mark.asyncio
    async def test_succeeds_first_attempt(self) -> None:
        executor = RetryExecutor(RetryConfig(max_attempts=3, base_delay_seconds=0.0, jitter=False))

        async def op() -> tuple[int, str, str]:
            return 0, "output", ""

        result = await executor.execute(op)
        assert result.succeeded
        assert result.total_attempts == 1
        assert result.attempts[0].status == AttemptStatus.SUCCESS
        assert result.attempts[0].output == "output"

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self) -> None:
        executor = RetryExecutor(RetryConfig(max_attempts=5, base_delay_seconds=0.01, max_delay_seconds=0.1, jitter=False))
        call_count = 0

        async def op() -> tuple[int, str, str]:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return 1, "", "fail"
            return 0, "success", ""

        result = await executor.execute(op)
        assert result.succeeded
        assert result.total_attempts == 3
        assert call_count == 3
        assert result.attempts[0].is_failure()
        assert result.attempts[1].is_failure()
        assert result.attempts[2].is_success()

    @pytest.mark.asyncio
    async def test_exhausts_all_attempts(self) -> None:
        executor = RetryExecutor(RetryConfig(max_attempts=3, base_delay_seconds=0.01, jitter=False))

        async def op() -> tuple[int, str, str]:
            return 1, "", "always fails"

        result = await executor.execute(op)
        assert not result.succeeded
        assert result.total_attempts == 3
        assert result.final_status == AttemptStatus.FAILED
        assert result.failure_count() == 3

    @pytest.mark.asyncio
    async def test_handles_exception(self) -> None:
        executor = RetryExecutor(RetryConfig(max_attempts=2, base_delay_seconds=0.01, jitter=False))
        call_count = 0

        async def op() -> tuple[int, str, str]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("boom")
            return 0, "recovered", ""

        result = await executor.execute(op)
        assert result.succeeded
        assert result.total_attempts == 2
        assert result.attempts[0].exception_type == "ValueError"
        assert result.attempts[0].error == "boom"

    @pytest.mark.asyncio
    async def test_non_retryable_exception_stops(self) -> None:
        executor = RetryExecutor(RetryConfig(
            max_attempts=5,
            base_delay_seconds=0.0,
            jitter=False,
            retryable_exceptions=("ValueError",),
        ))

        async def op() -> tuple[int, str, str]:
            raise TypeError("not retryable")

        result = await executor.execute(op)
        assert not result.succeeded
        assert result.total_attempts == 1
        assert result.attempts[0].exception_type == "TypeError"

    @pytest.mark.asyncio
    async def test_specific_exit_codes_only(self) -> None:
        executor = RetryExecutor(RetryConfig(
            max_attempts=5,
            base_delay_seconds=0.0,
            jitter=False,
            retry_on_exit_codes=(5,),
        ))

        async def op() -> tuple[int, str, str]:
            return 3, "", "not retryable exit"

        result = await executor.execute(op)
        assert not result.succeeded
        assert result.total_attempts == 1

    @pytest.mark.asyncio
    async def test_specific_exit_code_retries(self) -> None:
        executor = RetryExecutor(RetryConfig(
            max_attempts=3,
            base_delay_seconds=0.0,
            jitter=False,
            retry_on_exit_codes=(5,),
        ))
        call_count = 0

        async def op() -> tuple[int, str, str]:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return 5, "", "retry me"
            return 0, "ok", ""

        result = await executor.execute(op)
        assert result.succeeded
        assert result.total_attempts == 3


class TestRetryExecutorTiming:
    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self) -> None:
        executor = RetryExecutor(RetryConfig(
            max_attempts=3,
            base_delay_seconds=0.05,
            max_delay_seconds=1.0,
            backoff_factor=2.0,
            jitter=False,
        ))

        async def op() -> tuple[int, str, str]:
            return 1, "", "fail"

        start = time.monotonic()
        result = await executor.execute(op)
        elapsed = time.monotonic() - start

        assert not result.succeeded
        assert result.total_attempts == 3
        assert elapsed >= 0.14
        assert result.attempts[1].delay_before_ms >= 40
        assert result.attempts[2].delay_before_ms >= 90

    @pytest.mark.asyncio
    async def test_max_delay_cap(self) -> None:
        executor = RetryExecutor(RetryConfig(
            max_attempts=3,
            base_delay_seconds=0.1,
            max_delay_seconds=0.15,
            backoff_factor=10.0,
            jitter=False,
        ))

        async def op() -> tuple[int, str, str]:
            return 1, "", "fail"

        result = await executor.execute(op)
        assert result.attempts[1].delay_before_ms <= 160
        assert result.attempts[2].delay_before_ms <= 160


class TestRetryExecutorCancellation:
    @pytest.mark.asyncio
    async def test_cancelled_during_delay_returns_cancelled(self) -> None:
        executor = RetryExecutor(RetryConfig(
            max_attempts=5,
            base_delay_seconds=2.0,
            max_delay_seconds=5.0,
            jitter=False,
        ))

        async def op() -> tuple[int, str, str]:
            return 1, "", "fail"

        task = asyncio.create_task(executor.execute(op))
        await asyncio.sleep(0.1)
        task.cancel()

        result = await task
        assert result.final_status == AttemptStatus.CANCELLED
        cancelled_attempts = [a for a in result.attempts if a.status == AttemptStatus.CANCELLED]
        assert len(cancelled_attempts) >= 1

    @pytest.mark.asyncio
    async def test_cancelled_during_operation_returns_cancelled(self) -> None:
        executor = RetryExecutor(RetryConfig(max_attempts=3, base_delay_seconds=0.0, jitter=False))

        async def op() -> tuple[int, str, str]:
            await asyncio.sleep(5.0)
            return 0, "never", ""

        task = asyncio.create_task(executor.execute(op))
        await asyncio.sleep(0.05)
        task.cancel()

        result = await task
        assert result.final_status == AttemptStatus.CANCELLED
        assert result.total_attempts == 1


class TestRetryExecutorEdgeCases:
    @pytest.mark.asyncio
    async def test_max_attempts_one(self) -> None:
        executor = RetryExecutor(RetryConfig(max_attempts=1, base_delay_seconds=0.0, jitter=False))

        async def op() -> tuple[int, str, str]:
            return 1, "", "fail"

        result = await executor.execute(op)
        assert not result.succeeded
        assert result.total_attempts == 1

    @pytest.mark.asyncio
    async def test_preserves_output_on_success(self) -> None:
        executor = RetryExecutor(RetryConfig(max_attempts=1))

        async def op() -> tuple[int, str, str]:
            return 0, "important output", "warning text"

        result = await executor.execute(op)
        assert result.attempts[0].output == "important output"
        assert result.attempts[0].error == "warning text"

    @pytest.mark.asyncio
    async def test_single_attempt_success_no_delay(self) -> None:
        executor = RetryExecutor(RetryConfig(max_attempts=3, base_delay_seconds=0.5, jitter=False))

        async def op() -> tuple[int, str, str]:
            return 0, "ok", ""

        start = time.monotonic()
        result = await executor.execute(op)
        elapsed = time.monotonic() - start

        assert result.succeeded
        assert elapsed < 0.3
        assert result.attempts[0].delay_before_ms == 0

    @pytest.mark.asyncio
    async def test_jitter_produces_variance(self) -> None:
        executor = RetryExecutor(RetryConfig(
            max_attempts=3,
            base_delay_seconds=0.05,
            max_delay_seconds=1.0,
            backoff_factor=2.0,
            jitter=True,
        ))

        async def op() -> tuple[int, str, str]:
            return 1, "", "fail"

        result = await executor.execute(op)
        delays = [a.delay_before_ms for a in result.attempts[1:]]
        assert len(delays) == 2
        assert all(d >= 0 for d in delays)

    @pytest.mark.asyncio
    async def test_default_config_used(self) -> None:
        executor = RetryExecutor()
        assert executor.config.max_attempts == 3
        assert executor.config.jitter is True

    @pytest.mark.asyncio
    async def test_mixed_exception_and_exit_code(self) -> None:
        executor = RetryExecutor(RetryConfig(max_attempts=3, base_delay_seconds=0.0, jitter=False))
        call_count = 0

        async def op() -> tuple[int, str, str]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("boom")
            if call_count == 2:
                return 1, "", "fail"
            return 0, "final ok", ""

        result = await executor.execute(op)
        assert result.succeeded
        assert result.total_attempts == 3
        assert result.attempts[0].exception_type == "RuntimeError"
        assert result.attempts[1].exit_code == 1
        assert result.attempts[2].output == "final ok"

    @pytest.mark.asyncio
    async def test_zero_exit_code_is_success(self) -> None:
        executor = RetryExecutor(RetryConfig(max_attempts=3, base_delay_seconds=0.0, jitter=False))

        async def op() -> tuple[int, str, str]:
            return 0, "", ""

        result = await executor.execute(op)
        assert result.succeeded
        assert result.total_attempts == 1

    @pytest.mark.asyncio
    async def test_negative_exit_code_treated_as_failure(self) -> None:
        executor = RetryExecutor(RetryConfig(max_attempts=2, base_delay_seconds=0.0, jitter=False))

        async def op() -> tuple[int, str, str]:
            return -9, "", "signal killed"

        result = await executor.execute(op)
        assert not result.succeeded
        assert result.attempts[0].exit_code == -9
