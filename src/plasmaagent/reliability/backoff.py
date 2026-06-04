from typing import Callable, TypeVar, Any, Awaitable
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
import asyncio
import random
import time


T = TypeVar("T")


class BackoffStrategy(str, Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"
    FIBONACCI = "fibonacci"


@dataclass(frozen=True)
class BackoffConfig:
    base_delay_ms: int = field(default=100)
    max_delay_ms: int = field(default=30000)
    multiplier: float = field(default=2.0)
    jitter: bool = field(default=True)
    strategy: BackoffStrategy = field(default=BackoffStrategy.EXPONENTIAL)

    def __post_init__(self):
        if self.base_delay_ms < 0:
            raise ValueError("base_delay_ms must be non-negative")
        if self.max_delay_ms < self.base_delay_ms:
            raise ValueError("max_delay_ms must be >= base_delay_ms")
        if self.multiplier < 1.0:
            raise ValueError("multiplier must be >= 1.0")


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = field(default=3)
    backoff: BackoffConfig = field(default_factory=BackoffConfig)
    retryable_exceptions: tuple = field(default=(Exception,))

    def __post_init__(self):
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.max_retries > 20:
            raise ValueError("max_retries must be <= 20")


@dataclass
class RetryResult:
    success: bool
    value: Any = None
    attempts: int = 0
    total_duration_ms: float = 0.0
    last_error: Exception | None = None
    delays_ms: list = field(default_factory=list)


class ExponentialBackoff:
    def __init__(self, config: BackoffConfig | None = None):
        self._config = config or BackoffConfig()

    def calculate_delay_ms(self, attempt: int) -> int:
        if attempt < 0:
            raise ValueError("attempt must be non-negative")

        strategy = self._config.strategy
        base = self._config.base_delay_ms
        multiplier = self._config.multiplier
        max_delay = self._config.max_delay_ms

        if strategy == BackoffStrategy.EXPONENTIAL:
            delay = base * (multiplier ** attempt)
        elif strategy == BackoffStrategy.LINEAR:
            delay = base * (attempt + 1) * multiplier
        elif strategy == BackoffStrategy.CONSTANT:
            delay = base
        elif strategy == BackoffStrategy.FIBONACCI:
            a, b = 1, 1
            for _ in range(attempt):
                a, b = b, a + b
            delay = base * b
        else:
            delay = base

        delay = min(delay, max_delay)

        if self._config.jitter and delay > 0:
            jitter_range = delay * 0.25
            delay = delay + random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay)

        return int(delay)

    async def wait(self, attempt: int) -> int:
        delay_ms = self.calculate_delay_ms(attempt)
        await asyncio.sleep(delay_ms / 1000.0)
        return delay_ms

    def wait_sync(self, attempt: int) -> int:
        delay_ms = self.calculate_delay_ms(attempt)
        time.sleep(delay_ms / 1000.0)
        return delay_ms


async def retry_with_backoff(
    func: Callable[[], Awaitable[T]],
    policy: RetryPolicy | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> RetryResult:
    policy = policy or RetryPolicy()
    backoff = ExponentialBackoff(policy.backoff)
    start_time = time.time()
    delays: list[int] = []
    last_error: Exception | None = None

    for attempt in range(policy.max_retries + 1):
        try:
            result = await func()
            duration_ms = (time.time() - start_time) * 1000
            return RetryResult(
                success=True,
                value=result,
                attempts=attempt + 1,
                total_duration_ms=duration_ms,
                delays_ms=delays,
            )
        except Exception as e:
            last_error = e
            is_retryable = any(
                isinstance(e, exc_type) for exc_type in policy.retryable_exceptions
            )

            if not is_retryable or attempt >= policy.max_retries:
                duration_ms = (time.time() - start_time) * 1000
                return RetryResult(
                    success=False,
                    attempts=attempt + 1,
                    total_duration_ms=duration_ms,
                    last_error=e,
                    delays_ms=delays,
                )

            delay_ms = await backoff.wait(attempt)
            delays.append(delay_ms)

            if on_retry:
                on_retry(attempt + 1, e, delay_ms)

    duration_ms = (time.time() - start_time) * 1000
    return RetryResult(
        success=False,
        attempts=policy.max_retries + 1,
        total_duration_ms=duration_ms,
        last_error=last_error,
        delays_ms=delays,
    )


def retry_with_backoff_sync(
    func: Callable[[], T],
    policy: RetryPolicy | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> RetryResult:
    policy = policy or RetryPolicy()
    backoff = ExponentialBackoff(policy.backoff)
    start_time = time.time()
    delays: list[int] = []
    last_error: Exception | None = None

    for attempt in range(policy.max_retries + 1):
        try:
            result = func()
            duration_ms = (time.time() - start_time) * 1000
            return RetryResult(
                success=True,
                value=result,
                attempts=attempt + 1,
                total_duration_ms=duration_ms,
                delays_ms=delays,
            )
        except Exception as e:
            last_error = e
            is_retryable = any(
                isinstance(e, exc_type) for exc_type in policy.retryable_exceptions
            )

            if not is_retryable or attempt >= policy.max_retries:
                duration_ms = (time.time() - start_time) * 1000
                return RetryResult(
                    success=False,
                    attempts=attempt + 1,
                    total_duration_ms=duration_ms,
                    last_error=e,
                    delays_ms=delays,
                )

            delay_ms = backoff.wait_sync(attempt)
            delays.append(delay_ms)

            if on_retry:
                on_retry(attempt + 1, e, delay_ms)

    duration_ms = (time.time() - start_time) * 1000
    return RetryResult(
        success=False,
        attempts=policy.max_retries + 1,
        total_duration_ms=duration_ms,
        last_error=last_error,
        delays_ms=delays,
    )
