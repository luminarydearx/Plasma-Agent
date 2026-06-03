from __future__ import annotations

import asyncio
import random
import time
from typing import Awaitable, Callable, Optional

from plasmaagent.ai.retry.models import (
    AttemptResult,
    AttemptStatus,
    RetryConfig,
    RetryResult,
)


StepCallable = Callable[[], Awaitable[tuple[int, str, str]]]


class RetryExecutor:
    def __init__(self, config: Optional[RetryConfig] = None) -> None:
        self._config = config or RetryConfig()

    @property
    def config(self) -> RetryConfig:
        return self._config

    def _compute_delay(self, attempt_index: int) -> float:
        cfg = self._config
        delay = cfg.base_delay_seconds * (cfg.backoff_factor ** attempt_index)
        delay = min(delay, cfg.max_delay_seconds)
        if cfg.jitter and delay > 0:
            delay = delay * (0.5 + random.random() * 0.5)
        return max(0.0, delay)

    def _is_retryable_exception(self, exc: BaseException) -> bool:
        if not self._config.retryable_exceptions:
            return True
        exc_name = type(exc).__name__
        exc_full = f"{type(exc).__module__}.{exc_name}"
        return exc_name in self._config.retryable_exceptions or exc_full in self._config.retryable_exceptions

    def _is_retryable_exit_code(self, exit_code: int) -> bool:
        if not self._config.retry_on_exit_codes:
            return exit_code != 0
        return exit_code in self._config.retry_on_exit_codes

    async def execute(self, operation: StepCallable) -> RetryResult:
        attempts: list[AttemptResult] = []
        start_time = time.monotonic()
        cfg = self._config

        for attempt_index in range(cfg.max_attempts):
            delay_before_ms = 0
            if attempt_index > 0:
                delay_seconds = self._compute_delay(attempt_index - 1)
                delay_before_ms = int(delay_seconds * 1000)
                if delay_before_ms > 0:
                    try:
                        await asyncio.sleep(delay_seconds)
                    except asyncio.CancelledError:
                        attempts.append(AttemptResult(
                            attempt_number=attempt_index + 1,
                            status=AttemptStatus.CANCELLED,
                            delay_before_ms=delay_before_ms,
                        ))
                        return self._build_result(cfg, attempts, start_time)

            step_start = time.monotonic()
            try:
                exit_code, output, error = await operation()
                duration_ms = int((time.monotonic() - step_start) * 1000)

                if exit_code == 0:
                    attempts.append(AttemptResult(
                        attempt_number=attempt_index + 1,
                        status=AttemptStatus.SUCCESS,
                        output=output,
                        error=error,
                        exit_code=exit_code,
                        duration_ms=duration_ms,
                        delay_before_ms=delay_before_ms,
                    ))
                    return self._build_result(cfg, attempts, start_time)

                attempts.append(AttemptResult(
                    attempt_number=attempt_index + 1,
                    status=AttemptStatus.FAILED,
                    output=output,
                    error=error,
                    exit_code=exit_code,
                    duration_ms=duration_ms,
                    delay_before_ms=delay_before_ms,
                ))

                if not self._is_retryable_exit_code(exit_code):
                    return self._build_result(cfg, attempts, start_time)

            except asyncio.CancelledError:
                duration_ms = int((time.monotonic() - step_start) * 1000)
                attempts.append(AttemptResult(
                    attempt_number=attempt_index + 1,
                    status=AttemptStatus.CANCELLED,
                    duration_ms=duration_ms,
                    delay_before_ms=delay_before_ms,
                ))
                return self._build_result(cfg, attempts, start_time)

            except Exception as exc:
                duration_ms = int((time.monotonic() - step_start) * 1000)
                attempts.append(AttemptResult(
                    attempt_number=attempt_index + 1,
                    status=AttemptStatus.FAILED,
                    error=str(exc),
                    exit_code=-1,
                    duration_ms=duration_ms,
                    delay_before_ms=delay_before_ms,
                    exception_type=type(exc).__name__,
                ))

                if not self._is_retryable_exception(exc):
                    return self._build_result(cfg, attempts, start_time)

        return self._build_result(cfg, attempts, start_time)

    def _build_result(
        self,
        cfg: RetryConfig,
        attempts: list[AttemptResult],
        start_time: float,
    ) -> RetryResult:
        total_duration_ms = int((time.monotonic() - start_time) * 1000)
        final_status = attempts[-1].status if attempts else AttemptStatus.SKIPPED
        return RetryResult(
            config=cfg,
            attempts=tuple(attempts),
            final_status=final_status,
            total_duration_ms=total_duration_ms,
            total_attempts=len(attempts),
        )
