from enum import Enum
from typing import Callable, TypeVar, Generic, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import threading


T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerConfig(BaseModel):
    failure_threshold: int = Field(ge=1, le=100, default=5)
    recovery_timeout_seconds: float = Field(ge=0.1, le=3600, default=30.0)
    success_threshold: int = Field(ge=1, le=50, default=2)
    half_open_max_calls: int = Field(ge=1, le=10, default=1)


class CircuitBreakerOpenError(Exception):
    def __init__(self, name: str, state: CircuitState, remaining_seconds: float):
        self.name = name
        self.state = state
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"Circuit breaker '{name}' is {state.value}. "
            f"Try again in {remaining_seconds:.1f}s"
        )


class CircuitBreaker(Generic[T]):
    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self._name = name
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: datetime | None = None
        self._opened_at: datetime | None = None
        self._lock = threading.RLock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def success_count(self) -> int:
        return self._success_count

    def _maybe_transition_to_half_open(self) -> None:
        if self._state != CircuitState.OPEN:
            return
        if self._opened_at is None:
            return
        elapsed = (datetime.now() - self._opened_at).total_seconds()
        if elapsed >= self._config.recovery_timeout_seconds:
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0
            self._success_count = 0

    def _transition_to_open(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = datetime.now()
        self._half_open_calls = 0
        self._success_count = 0

    def _transition_to_closed(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._opened_at = None

    def record_success(self) -> None:
        with self._lock:
            self._last_failure_time = None
            if self._state == CircuitState.CLOSED:
                self._failure_count = max(0, self._failure_count - 1)
                self._success_count += 1
            elif self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self._config.success_threshold:
                    self._transition_to_closed()

    def record_failure(self, error: Exception | None = None) -> None:
        with self._lock:
            self._last_failure_time = datetime.now()
            self._failure_count += 1
            self._success_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to_open()
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self._config.failure_threshold:
                    self._transition_to_open()

    def allow_request(self) -> bool:
        with self._lock:
            self._maybe_transition_to_half_open()

            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self._config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
            return False

    def remaining_recovery_seconds(self) -> float:
        with self._lock:
            if self._state != CircuitState.OPEN or self._opened_at is None:
                return 0.0
            elapsed = (datetime.now() - self._opened_at).total_seconds()
            remaining = self._config.recovery_timeout_seconds - elapsed
            return max(0.0, remaining)

    def reset(self) -> None:
        with self._lock:
            self._transition_to_closed()

    def execute(self, func: Callable[[], T], fallback: Callable[[], T] | None = None) -> T:
        if not self.allow_request():
            remaining = self.remaining_recovery_seconds()
            if fallback is not None:
                return fallback()
            raise CircuitBreakerOpenError(self._name, self._state, remaining)

        try:
            result = func()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            raise

    async def execute_async(
        self,
        func: Callable,
        fallback: Callable | None = None,
    ) -> Any:
        if not self.allow_request():
            remaining = self.remaining_recovery_seconds()
            if fallback is not None:
                return await fallback()
            raise CircuitBreakerOpenError(self._name, self._state, remaining)

        try:
            result = await func()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            raise

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "name": self._name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "failure_threshold": self._config.failure_threshold,
                "recovery_timeout_seconds": self._config.recovery_timeout_seconds,
                "remaining_recovery_seconds": self.remaining_recovery_seconds(),
                "last_failure_time": (
                    self._last_failure_time.isoformat()
                    if self._last_failure_time
                    else None
                ),
            }
