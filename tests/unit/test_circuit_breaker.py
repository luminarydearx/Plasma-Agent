import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from plasmaagent.reliability import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
)


class TestCircuitState:
    def test_states_exist(self):
        assert CircuitState.CLOSED == "closed"
        assert CircuitState.OPEN == "open"
        assert CircuitState.HALF_OPEN == "half_open"

    def test_is_string_enum(self):
        assert isinstance(CircuitState.CLOSED, str)


class TestCircuitBreakerConfig:
    def test_default_values(self):
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout_seconds == 30.0
        assert config.success_threshold == 2
        assert config.half_open_max_calls == 1

    def test_custom_values(self):
        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout_seconds=60.0,
            success_threshold=3,
            half_open_max_calls=2,
        )
        assert config.failure_threshold == 10
        assert config.recovery_timeout_seconds == 60.0
        assert config.success_threshold == 3
        assert config.half_open_max_calls == 2

    def test_failure_threshold_bounds(self):
        with pytest.raises(Exception):
            CircuitBreakerConfig(failure_threshold=0)
        with pytest.raises(Exception):
            CircuitBreakerConfig(failure_threshold=101)

    def test_recovery_timeout_bounds(self):
        with pytest.raises(Exception):
            CircuitBreakerConfig(recovery_timeout_seconds=0.0)
        with pytest.raises(Exception):
            CircuitBreakerConfig(recovery_timeout_seconds=3601.0)

    def test_success_threshold_bounds(self):
        with pytest.raises(Exception):
            CircuitBreakerConfig(success_threshold=0)
        with pytest.raises(Exception):
            CircuitBreakerConfig(success_threshold=51)

    def test_half_open_max_calls_bounds(self):
        with pytest.raises(Exception):
            CircuitBreakerConfig(half_open_max_calls=0)
        with pytest.raises(Exception):
            CircuitBreakerConfig(half_open_max_calls=11)

    def test_boundary_values(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.1,
            success_threshold=1,
            half_open_max_calls=1,
        )
        assert config.failure_threshold == 1
        assert config.recovery_timeout_seconds == 0.1

    def test_max_boundary_values(self):
        config = CircuitBreakerConfig(
            failure_threshold=100,
            recovery_timeout_seconds=3600,
            success_threshold=50,
            half_open_max_calls=10,
        )
        assert config.failure_threshold == 100


class TestCircuitBreakerOpenError:
    def test_error_attributes(self):
        error = CircuitBreakerOpenError("test-cb", CircuitState.OPEN, 15.5)
        assert error.name == "test-cb"
        assert error.state == CircuitState.OPEN
        assert error.remaining_seconds == 15.5

    def test_error_message(self):
        error = CircuitBreakerOpenError("my-service", CircuitState.OPEN, 10.0)
        assert "my-service" in str(error)
        assert "open" in str(error)
        assert "10.0" in str(error)


class TestCircuitBreakerInit:
    def test_default_config(self):
        cb = CircuitBreaker("test")
        assert cb.name == "test"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0

    def test_custom_config(self):
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config)
        assert cb.name == "test"

    def test_initial_state_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerClosedState:
    def test_allow_request_when_closed(self):
        cb = CircuitBreaker("test")
        assert cb.allow_request() is True

    def test_record_success_decrements_failure(self):
        cb = CircuitBreaker("test")
        cb.record_failure()
        assert cb.failure_count == 1
        cb.record_success()
        assert cb.failure_count == 0

    def test_record_success_increments_success(self):
        cb = CircuitBreaker("test")
        cb.record_success()
        assert cb.success_count == 1
        cb.record_success()
        assert cb.success_count == 2

    def test_failure_count_does_not_go_below_zero(self):
        cb = CircuitBreaker("test")
        cb.record_success()
        assert cb.failure_count == 0

    def test_transitions_to_open_after_threshold(self):
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_resets_on_open_transition(self):
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("test", config)
        cb.record_success()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        assert cb.success_count == 0


class TestCircuitBreakerOpenState:
    def test_deny_request_when_open(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=60.0,
        )
        cb = CircuitBreaker("test", config)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_remaining_recovery_seconds(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=30.0,
        )
        cb = CircuitBreaker("test", config)
        cb.record_failure()
        remaining = cb.remaining_recovery_seconds()
        assert 29.0 <= remaining <= 30.0

    def test_remaining_recovery_zero_when_closed(self):
        cb = CircuitBreaker("test")
        assert cb.remaining_recovery_seconds() == 0.0

    def test_transition_to_half_open_after_timeout(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.2,
        )
        cb = CircuitBreaker("test", config)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.3)
        assert cb.state == CircuitState.HALF_OPEN


class TestCircuitBreakerHalfOpenState:
    def test_allow_limited_requests_in_half_open(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.1,
            half_open_max_calls=1,
        )
        cb = CircuitBreaker("test", config)
        cb.record_failure()
        time.sleep(0.2)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True
        assert cb.allow_request() is False

    def test_success_transitions_to_closed(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.1,
            success_threshold=2,
            half_open_max_calls=2,
        )
        cb = CircuitBreaker("test", config)
        cb.record_failure()
        time.sleep(0.2)
        assert cb.state == CircuitState.HALF_OPEN
        cb.allow_request()
        cb.record_success()
        cb.allow_request()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_failure_transitions_to_open(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.1,
        )
        cb = CircuitBreaker("test", config)
        cb.record_failure()
        time.sleep(0.2)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerExecute:
    def test_execute_success(self):
        cb = CircuitBreaker("test")
        result = cb.execute(lambda: 42)
        assert result == 42
        assert cb.success_count == 1

    def test_execute_failure(self):
        cb = CircuitBreaker("test")

        def failing_func():
            raise ValueError("oops")

        with pytest.raises(ValueError):
            cb.execute(failing_func)
        assert cb.failure_count == 1

    def test_execute_raises_when_open(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config)
        cb.record_failure()
        with pytest.raises(CircuitBreakerOpenError):
            cb.execute(lambda: 42)

    def test_execute_with_fallback_when_open(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config)
        cb.record_failure()
        result = cb.execute(lambda: 42, fallback=lambda: "fallback")
        assert result == "fallback"

    def test_execute_fallback_not_called_when_closed(self):
        cb = CircuitBreaker("test")
        fallback_called = False

        def fallback():
            nonlocal fallback_called
            fallback_called = True
            return "fallback"

        result = cb.execute(lambda: 42, fallback=fallback)
        assert result == 42
        assert not fallback_called


class TestCircuitBreakerExecuteAsync:
    @pytest.mark.asyncio
    async def test_execute_async_success(self):
        cb = CircuitBreaker("test")

        async def async_func():
            return 42

        result = await cb.execute_async(async_func)
        assert result == 42
        assert cb.success_count == 1

    @pytest.mark.asyncio
    async def test_execute_async_failure(self):
        cb = CircuitBreaker("test")

        async def failing_func():
            raise ValueError("async oops")

        with pytest.raises(ValueError):
            await cb.execute_async(failing_func)
        assert cb.failure_count == 1

    @pytest.mark.asyncio
    async def test_execute_async_raises_when_open(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config)
        cb.record_failure()

        async def async_func():
            return 42

        with pytest.raises(CircuitBreakerOpenError):
            await cb.execute_async(async_func)

    @pytest.mark.asyncio
    async def test_execute_async_with_fallback(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config)
        cb.record_failure()

        async def async_func():
            return 42

        async def fallback():
            return "fallback"

        result = await cb.execute_async(async_func, fallback=fallback)
        assert result == "fallback"


class TestCircuitBreakerReset:
    def test_reset_from_open(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_reset_from_half_open(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.1,
        )
        cb = CircuitBreaker("test", config)
        cb.record_failure()
        time.sleep(0.2)
        assert cb.state == CircuitState.HALF_OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_reset_clears_all_counters(self):
        cb = CircuitBreaker("test")
        cb.record_success()
        cb.record_success()
        cb.record_failure()
        cb.reset()
        assert cb.failure_count == 0
        assert cb.success_count == 0


class TestCircuitBreakerStats:
    def test_get_stats_closed(self):
        cb = CircuitBreaker("test")
        stats = cb.get_stats()
        assert stats["name"] == "test"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0
        assert stats["success_count"] == 0
        assert stats["last_failure_time"] is None

    def test_get_stats_after_failure(self):
        cb = CircuitBreaker("test")
        cb.record_failure()
        stats = cb.get_stats()
        assert stats["failure_count"] == 1
        assert stats["last_failure_time"] is not None

    def test_get_stats_open(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config)
        cb.record_failure()
        stats = cb.get_stats()
        assert stats["state"] == "open"
        assert stats["remaining_recovery_seconds"] > 0


class TestCircuitBreakerConcurrency:
    def test_thread_safety(self):
        import threading
        config = CircuitBreakerConfig(failure_threshold=100)
        cb = CircuitBreaker("test", config)
        errors = []

        def worker():
            try:
                for _ in range(50):
                    cb.record_success()
                    cb.record_failure()
                    cb.allow_request()
                    _ = cb.state
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_execute(self):
        import threading
        config = CircuitBreakerConfig(failure_threshold=100)
        cb = CircuitBreaker("test", config)
        results = []

        def worker():
            for _ in range(20):
                try:
                    r = cb.execute(lambda: 42)
                    results.append(r)
                except Exception:
                    pass

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r == 42 for r in results)


class TestCircuitBreakerEdgeCases:
    def test_multiple_resets(self):
        cb = CircuitBreaker("test")
        cb.reset()
        cb.reset()
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_execute_with_none_return(self):
        cb = CircuitBreaker("test")
        result = cb.execute(lambda: None)
        assert result is None

    def test_execute_with_exception_in_fallback(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config)
        cb.record_failure()

        def bad_fallback():
            raise RuntimeError("fallback failed")

        with pytest.raises(RuntimeError, match="fallback failed"):
            cb.execute(lambda: 42, fallback=bad_fallback)

    def test_generic_type_preservation(self):
        cb: CircuitBreaker[int] = CircuitBreaker("test")
        result = cb.execute(lambda: 42)
        assert isinstance(result, int)

    def test_success_count_resets_on_half_open_transition(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.1,
            success_threshold=5,
        )
        cb = CircuitBreaker("test", config)
        cb.record_success()
        cb.record_success()
        cb.record_failure()
        time.sleep(0.2)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.success_count == 0
