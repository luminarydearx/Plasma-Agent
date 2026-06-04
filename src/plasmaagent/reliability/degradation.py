from typing import Callable, TypeVar, Generic, Any, Awaitable
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
import threading


T = TypeVar("T")


class DegradationLevel(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"


class DegradationReason(str, Enum):
    CIRCUIT_OPEN = "circuit_open"
    HIGH_ERROR_RATE = "high_error_rate"
    HIGH_LATENCY = "high_latency"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    MANUAL = "manual"
    DEPENDENCY_FAILURE = "dependency_failure"


class FallbackStrategy(str, Enum):
    CACHED_RESPONSE = "cached_response"
    DEFAULT_VALUE = "default_value"
    SKIP = "skip"
    RAISE = "raise"
    RETRY_LATER = "retry_later"


class DegradationConfig(BaseModel):
    error_rate_threshold: float = Field(ge=0.0, le=1.0, default=0.5)
    latency_threshold_ms: float = Field(ge=0.0, le=60000.0, default=5000.0)
    window_size: int = Field(ge=1, le=1000, default=100)
    min_requests_for_evaluation: int = Field(ge=1, le=100, default=10)
    cooldown_seconds: float = Field(ge=0.0, le=3600.0, default=60.0)


class DegradationState(BaseModel):
    level: DegradationLevel = DegradationLevel.FULL
    reason: DegradationReason | None = None
    since: datetime | None = None
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    total_requests: int = 0
    window_requests: int = 0
    fallback_strategy: FallbackStrategy = FallbackStrategy.RAISE


class GracefulDegradation(Generic[T]):
    def __init__(
        self,
        name: str,
        config: DegradationConfig | None = None,
        cached_value: T | None = None,
        default_value: T | None = None,
    ):
        self._name = name
        self._config = config or DegradationConfig()
        self._state = DegradationState()
        self._cached_value = cached_value
        self._default_value = default_value
        self._lock = threading.RLock()
        self._request_history: list[tuple[bool, float]] = []
        self._total_requests_all_time = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> DegradationState:
        with self._lock:
            return self._state.model_copy()

    @property
    def level(self) -> DegradationLevel:
        return self._state.level

    @property
    def is_degraded(self) -> bool:
        return self._state.level != DegradationLevel.FULL

    def record_request(self, success: bool, latency_ms: float) -> None:
        with self._lock:
            self._request_history.append((success, latency_ms))
            self._total_requests_all_time += 1
            if len(self._request_history) > self._config.window_size:
                self._request_history = self._request_history[
                    -self._config.window_size:
                ]
            self._state.total_requests = self._total_requests_all_time
            self._state.window_requests = len(self._request_history)
            self._evaluate_degradation()

    def _evaluate_degradation(self) -> None:
        if len(self._request_history) < self._config.min_requests_for_evaluation:
            return

        successes = sum(1 for s, _ in self._request_history if s)
        total = len(self._request_history)
        error_rate = 1.0 - (successes / total)
        avg_latency = sum(lat for _, lat in self._request_history) / total

        self._state.error_rate = error_rate
        self._state.avg_latency_ms = avg_latency

        if error_rate > self._config.error_rate_threshold:
            self._degrade(DegradationReason.HIGH_ERROR_RATE)
        elif avg_latency > self._config.latency_threshold_ms:
            self._degrade(DegradationReason.HIGH_LATENCY)
        elif self._state.level != DegradationLevel.FULL:
            if self._should_recover():
                self._recover()

    def _degrade(self, reason: DegradationReason) -> None:
        if self._state.level == DegradationLevel.FULL:
            self._state.level = DegradationLevel.PARTIAL
            self._state.reason = reason
            self._state.since = datetime.now()
        elif self._state.level == DegradationLevel.PARTIAL:
            if self._state.error_rate >= self._config.error_rate_threshold * 1.5:
                self._state.level = DegradationLevel.MINIMAL
                self._state.since = datetime.now()

    def _should_recover(self) -> bool:
        if self._state.since is None:
            return True
        elapsed = (datetime.now() - self._state.since).total_seconds()
        return elapsed >= self._config.cooldown_seconds

    def _recover(self) -> None:
        self._state.level = DegradationLevel.FULL
        self._state.reason = None
        self._state.since = None
        self._request_history.clear()
        self._state.window_requests = 0

    def degrade_manually(self, level: DegradationLevel) -> None:
        with self._lock:
            self._state.level = level
            self._state.reason = DegradationReason.MANUAL
            self._state.since = datetime.now()

    def recover(self) -> None:
        with self._lock:
            self._recover()

    def set_cached_value(self, value: T) -> None:
        with self._lock:
            self._cached_value = value

    def set_default_value(self, value: T) -> None:
        with self._lock:
            self._default_value = value

    def set_fallback_strategy(self, strategy: FallbackStrategy) -> None:
        with self._lock:
            self._state.fallback_strategy = strategy

    def get_fallback_value(self) -> T | None:
        with self._lock:
            strategy = self._state.fallback_strategy
            if strategy == FallbackStrategy.CACHED_RESPONSE:
                return self._cached_value
            if strategy == FallbackStrategy.DEFAULT_VALUE:
                return self._default_value
            if strategy == FallbackStrategy.SKIP:
                return None
            return None

    def execute(
        self,
        func: Callable[[], T],
        fallback: Callable[[], T] | None = None,
    ) -> T:
        import time

        if self.is_degraded:
            fallback_value = self.get_fallback_value()
            if fallback_value is not None:
                return fallback_value
            if fallback is not None:
                return fallback()
            if self._state.fallback_strategy == FallbackStrategy.RAISE:
                raise RuntimeError(
                    f"Service '{self._name}' is degraded "
                    f"(level={self._state.level.value}, "
                    f"reason={self._state.reason})"
                )

        start = time.time()
        try:
            result = func()
            latency_ms = (time.time() - start) * 1000
            self.record_request(True, latency_ms)
            if self._cached_value is None:
                self._cached_value = result
            return result
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            self.record_request(False, latency_ms)
            fallback_value = self.get_fallback_value()
            if fallback_value is not None:
                return fallback_value
            if fallback is not None:
                return fallback()
            raise

    async def execute_async(
        self,
        func: Callable[[], Awaitable[T]],
        fallback: Callable[[], Awaitable[T]] | None = None,
    ) -> T:
        import time

        if self.is_degraded:
            fallback_value = self.get_fallback_value()
            if fallback_value is not None:
                return fallback_value
            if fallback is not None:
                return await fallback()
            if self._state.fallback_strategy == FallbackStrategy.RAISE:
                raise RuntimeError(
                    f"Service '{self._name}' is degraded "
                    f"(level={self._state.level.value}, "
                    f"reason={self._state.reason})"
                )

        start = time.time()
        try:
            result = await func()
            latency_ms = (time.time() - start) * 1000
            self.record_request(True, latency_ms)
            if self._cached_value is None:
                self._cached_value = result
            return result
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            self.record_request(False, latency_ms)
            fallback_value = self.get_fallback_value()
            if fallback_value is not None:
                return fallback_value
            if fallback is not None:
                return await fallback()
            raise

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "name": self._name,
                "level": self._state.level.value,
                "reason": self._state.reason.value if self._state.reason else None,
                "since": (
                    self._state.since.isoformat() if self._state.since else None
                ),
                "error_rate": self._state.error_rate,
                "avg_latency_ms": self._state.avg_latency_ms,
                "total_requests": self._state.total_requests,
                "window_requests": self._state.window_requests,
                "fallback_strategy": self._state.fallback_strategy.value,
                "has_cached_value": self._cached_value is not None,
                "has_default_value": self._default_value is not None,
            }
