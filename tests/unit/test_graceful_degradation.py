import pytest
import time
import asyncio
from datetime import datetime
from plasmaagent.reliability import (
    GracefulDegradation,
    DegradationLevel,
    DegradationReason,
    DegradationConfig,
    DegradationState,
    FallbackStrategy,
)


class TestDegradationLevel:
    def test_levels_exist(self):
        assert DegradationLevel.FULL == "full"
        assert DegradationLevel.PARTIAL == "partial"
        assert DegradationLevel.MINIMAL == "minimal"
        assert DegradationLevel.NONE == "none"


class TestDegradationReason:
    def test_reasons_exist(self):
        assert DegradationReason.CIRCUIT_OPEN == "circuit_open"
        assert DegradationReason.HIGH_ERROR_RATE == "high_error_rate"
        assert DegradationReason.HIGH_LATENCY == "high_latency"
        assert DegradationReason.RESOURCE_EXHAUSTION == "resource_exhaustion"
        assert DegradationReason.MANUAL == "manual"
        assert DegradationReason.DEPENDENCY_FAILURE == "dependency_failure"


class TestFallbackStrategy:
    def test_strategies_exist(self):
        assert FallbackStrategy.CACHED_RESPONSE == "cached_response"
        assert FallbackStrategy.DEFAULT_VALUE == "default_value"
        assert FallbackStrategy.SKIP == "skip"
        assert FallbackStrategy.RAISE == "raise"
        assert FallbackStrategy.RETRY_LATER == "retry_later"


class TestDegradationConfig:
    def test_default_values(self):
        config = DegradationConfig()
        assert config.error_rate_threshold == 0.5
        assert config.latency_threshold_ms == 5000.0
        assert config.window_size == 100
        assert config.min_requests_for_evaluation == 10
        assert config.cooldown_seconds == 60.0

    def test_custom_values(self):
        config = DegradationConfig(
            error_rate_threshold=0.3,
            latency_threshold_ms=2000.0,
            window_size=50,
            min_requests_for_evaluation=5,
            cooldown_seconds=30.0,
        )
        assert config.error_rate_threshold == 0.3

    def test_error_rate_bounds(self):
        with pytest.raises(Exception):
            DegradationConfig(error_rate_threshold=-0.1)
        with pytest.raises(Exception):
            DegradationConfig(error_rate_threshold=1.1)

    def test_latency_bounds(self):
        with pytest.raises(Exception):
            DegradationConfig(latency_threshold_ms=-1.0)
        with pytest.raises(Exception):
            DegradationConfig(latency_threshold_ms=60001.0)

    def test_window_size_bounds(self):
        with pytest.raises(Exception):
            DegradationConfig(window_size=0)
        with pytest.raises(Exception):
            DegradationConfig(window_size=1001)

    def test_cooldown_bounds(self):
        with pytest.raises(Exception):
            DegradationConfig(cooldown_seconds=-1.0)
        with pytest.raises(Exception):
            DegradationConfig(cooldown_seconds=3601.0)


class TestDegradationState:
    def test_default_state(self):
        state = DegradationState()
        assert state.level == DegradationLevel.FULL
        assert state.reason is None
        assert state.since is None
        assert state.error_rate == 0.0
        assert state.avg_latency_ms == 0.0
        assert state.total_requests == 0
        assert state.window_requests == 0
        assert state.fallback_strategy == FallbackStrategy.RAISE


class TestGracefulDegradationInit:
    def test_default_init(self):
        gd = GracefulDegradation("test-service")
        assert gd.name == "test-service"
        assert gd.level == DegradationLevel.FULL
        assert gd.is_degraded is False

    def test_init_with_cached_value(self):
        gd = GracefulDegradation("test", cached_value="cached")
        stats = gd.get_stats()
        assert stats["has_cached_value"] is True

    def test_init_with_default_value(self):
        gd = GracefulDegradation("test", default_value="default")
        stats = gd.get_stats()
        assert stats["has_default_value"] is True


class TestGracefulDegradationRequestTracking:
    def test_record_success(self):
        gd = GracefulDegradation(
            "test",
            config=DegradationConfig(min_requests_for_evaluation=1),
        )
        gd.record_request(True, 10.0)
        state = gd.state
        assert state.total_requests == 1
        assert state.error_rate == 0.0

    def test_record_failure(self):
        gd = GracefulDegradation(
            "test",
            config=DegradationConfig(min_requests_for_evaluation=1),
        )
        gd.record_request(False, 10.0)
        state = gd.state
        assert state.total_requests == 1
        assert state.error_rate == 1.0

    def test_mixed_requests(self):
        gd = GracefulDegradation(
            "test",
            config=DegradationConfig(min_requests_for_evaluation=2),
        )
        gd.record_request(True, 10.0)
        gd.record_request(False, 20.0)
        state = gd.state
        assert state.total_requests == 2
        assert state.error_rate == 0.5
        assert state.avg_latency_ms == 15.0

    def test_window_size_limit(self):
        gd = GracefulDegradation(
            "test",
            config=DegradationConfig(window_size=5, min_requests_for_evaluation=1),
        )
        for i in range(10):
            gd.record_request(True, float(i))
        state = gd.state
        assert state.total_requests == 10
        assert state.window_requests == 5


class TestGracefulDegradationAutoDegrade:
    def test_degrade_on_high_error_rate(self):
        config = DegradationConfig(
            error_rate_threshold=0.5,
            min_requests_for_evaluation=2,
        )
        gd = GracefulDegradation("test", config=config)
        gd.record_request(False, 10.0)
        gd.record_request(False, 10.0)
        assert gd.level == DegradationLevel.PARTIAL
        assert gd.state.reason == DegradationReason.HIGH_ERROR_RATE

    def test_degrade_on_high_latency(self):
        config = DegradationConfig(
            latency_threshold_ms=100.0,
            error_rate_threshold=1.0,
            min_requests_for_evaluation=2,
        )
        gd = GracefulDegradation("test", config=config)
        gd.record_request(True, 200.0)
        gd.record_request(True, 200.0)
        assert gd.level == DegradationLevel.PARTIAL
        assert gd.state.reason == DegradationReason.HIGH_LATENCY

    def test_no_degrade_below_threshold(self):
        config = DegradationConfig(
            error_rate_threshold=0.6,
            min_requests_for_evaluation=2,
        )
        gd = GracefulDegradation("test", config=config)
        gd.record_request(True, 10.0)
        gd.record_request(False, 10.0)
        assert gd.level == DegradationLevel.FULL

    def test_degrade_to_minimal_on_very_high_error(self):
        config = DegradationConfig(
            error_rate_threshold=0.3,
            min_requests_for_evaluation=2,
        )
        gd = GracefulDegradation("test", config=config)
        gd.record_request(False, 10.0)
        gd.record_request(False, 10.0)
        assert gd.level == DegradationLevel.PARTIAL
        gd.record_request(False, 10.0)
        gd.record_request(False, 10.0)
        assert gd.level == DegradationLevel.MINIMAL

    def test_no_evaluation_below_min_requests(self):
        config = DegradationConfig(
            error_rate_threshold=0.1,
            min_requests_for_evaluation=10,
        )
        gd = GracefulDegradation("test", config=config)
        for _ in range(5):
            gd.record_request(False, 10.0)
        assert gd.level == DegradationLevel.FULL


class TestGracefulDegradationRecovery:
    def test_recover_after_cooldown(self):
        config = DegradationConfig(
            error_rate_threshold=0.5,
            min_requests_for_evaluation=2,
            cooldown_seconds=0.1,
        )
        gd = GracefulDegradation("test", config=config)
        gd.record_request(False, 10.0)
        gd.record_request(False, 10.0)
        assert gd.level == DegradationLevel.PARTIAL
        time.sleep(0.2)
        gd.record_request(True, 10.0)
        gd.record_request(True, 10.0)
        assert gd.level == DegradationLevel.FULL

    def test_manual_recover(self):
        gd = GracefulDegradation("test")
        gd.degrade_manually(DegradationLevel.MINIMAL)
        assert gd.level == DegradationLevel.MINIMAL
        gd.recover()
        assert gd.level == DegradationLevel.FULL

    def test_manual_degrade(self):
        gd = GracefulDegradation("test")
        gd.degrade_manually(DegradationLevel.PARTIAL)
        assert gd.level == DegradationLevel.PARTIAL
        assert gd.state.reason == DegradationReason.MANUAL


class TestGracefulDegradationFallback:
    def test_cached_response_strategy(self):
        gd = GracefulDegradation("test", cached_value="cached")
        gd.set_fallback_strategy(FallbackStrategy.CACHED_RESPONSE)
        assert gd.get_fallback_value() == "cached"

    def test_default_value_strategy(self):
        gd = GracefulDegradation("test", default_value="default")
        gd.set_fallback_strategy(FallbackStrategy.DEFAULT_VALUE)
        assert gd.get_fallback_value() == "default"

    def test_skip_strategy(self):
        gd = GracefulDegradation("test")
        gd.set_fallback_strategy(FallbackStrategy.SKIP)
        assert gd.get_fallback_value() is None

    def test_raise_strategy_returns_none(self):
        gd = GracefulDegradation("test")
        gd.set_fallback_strategy(FallbackStrategy.RAISE)
        assert gd.get_fallback_value() is None

    def test_set_cached_value(self):
        gd = GracefulDegradation("test")
        gd.set_cached_value("new-cached")
        gd.set_fallback_strategy(FallbackStrategy.CACHED_RESPONSE)
        assert gd.get_fallback_value() == "new-cached"

    def test_set_default_value(self):
        gd = GracefulDegradation("test")
        gd.set_default_value("new-default")
        gd.set_fallback_strategy(FallbackStrategy.DEFAULT_VALUE)
        assert gd.get_fallback_value() == "new-default"


class TestGracefulDegradationExecute:
    def test_execute_success(self):
        gd = GracefulDegradation("test")
        result = gd.execute(lambda: 42)
        assert result == 42
        assert gd.state.total_requests == 1

    def test_execute_failure_raises(self):
        gd = GracefulDegradation("test")

        def failing():
            raise ValueError("oops")

        with pytest.raises(ValueError):
            gd.execute(failing)
        assert gd.state.total_requests == 1

    def test_execute_with_cached_fallback_on_failure(self):
        gd = GracefulDegradation("test", cached_value="cached")
        gd.set_fallback_strategy(FallbackStrategy.CACHED_RESPONSE)

        def failing():
            raise ValueError("oops")

        result = gd.execute(failing)
        assert result == "cached"

    def test_execute_with_default_fallback_on_failure(self):
        gd = GracefulDegradation("test", default_value="default")
        gd.set_fallback_strategy(FallbackStrategy.DEFAULT_VALUE)

        def failing():
            raise ValueError("oops")

        result = gd.execute(failing)
        assert result == "default"

    def test_execute_with_explicit_fallback(self):
        gd = GracefulDegradation("test")

        def failing():
            raise ValueError("oops")

        result = gd.execute(failing, fallback=lambda: "fallback")
        assert result == "fallback"

    def test_execute_degraded_with_cached(self):
        gd = GracefulDegradation("test", cached_value="cached")
        gd.set_fallback_strategy(FallbackStrategy.CACHED_RESPONSE)
        gd.degrade_manually(DegradationLevel.PARTIAL)
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            return 42

        result = gd.execute(func)
        assert result == "cached"
        assert call_count == 0

    def test_execute_degraded_raises_when_no_fallback(self):
        gd = GracefulDegradation("test")
        gd.set_fallback_strategy(FallbackStrategy.RAISE)
        gd.degrade_manually(DegradationLevel.PARTIAL)
        with pytest.raises(RuntimeError, match="degraded"):
            gd.execute(lambda: 42)

    def test_execute_updates_cached_on_first_success(self):
        gd = GracefulDegradation("test")
        gd.execute(lambda: "first")
        gd.set_fallback_strategy(FallbackStrategy.CACHED_RESPONSE)
        assert gd.get_fallback_value() == "first"


class TestGracefulDegradationExecuteAsync:
    @pytest.mark.asyncio
    async def test_execute_async_success(self):
        gd = GracefulDegradation("test")

        async def func():
            return 42

        result = await gd.execute_async(func)
        assert result == 42

    @pytest.mark.asyncio
    async def test_execute_async_failure(self):
        gd = GracefulDegradation("test")

        async def failing():
            raise ValueError("async oops")

        with pytest.raises(ValueError):
            await gd.execute_async(failing)

    @pytest.mark.asyncio
    async def test_execute_async_with_fallback(self):
        gd = GracefulDegradation("test", cached_value="cached")
        gd.set_fallback_strategy(FallbackStrategy.CACHED_RESPONSE)

        async def failing():
            raise ValueError("async oops")

        result = await gd.execute_async(failing)
        assert result == "cached"

    @pytest.mark.asyncio
    async def test_execute_async_with_explicit_fallback(self):
        gd = GracefulDegradation("test")

        async def failing():
            raise ValueError("oops")

        async def fallback():
            return "fallback"

        result = await gd.execute_async(failing, fallback=fallback)
        assert result == "fallback"


class TestGracefulDegradationStats:
    def test_get_stats_initial(self):
        gd = GracefulDegradation("test")
        stats = gd.get_stats()
        assert stats["name"] == "test"
        assert stats["level"] == "full"
        assert stats["reason"] is None
        assert stats["error_rate"] == 0.0
        assert stats["total_requests"] == 0

    def test_get_stats_after_requests(self):
        gd = GracefulDegradation(
            "test",
            config=DegradationConfig(min_requests_for_evaluation=1),
        )
        gd.record_request(True, 10.0)
        gd.record_request(False, 20.0)
        stats = gd.get_stats()
        assert stats["total_requests"] == 2
        assert stats["error_rate"] == 0.5
        assert stats["avg_latency_ms"] == 15.0

    def test_get_stats_degraded(self):
        gd = GracefulDegradation(
            "test",
            config=DegradationConfig(
                error_rate_threshold=0.5,
                min_requests_for_evaluation=2,
            ),
        )
        gd.record_request(False, 10.0)
        gd.record_request(False, 10.0)
        stats = gd.get_stats()
        assert stats["level"] == "partial"
        assert stats["reason"] == "high_error_rate"
        assert stats["since"] is not None


class TestGracefulDegradationEdgeCases:
    def test_state_copy_is_independent(self):
        gd = GracefulDegradation("test")
        state1 = gd.state
        gd.record_request(True, 10.0)
        state2 = gd.state
        assert state1.total_requests == 0
        assert state2.total_requests == 1

    def test_execute_with_none_return(self):
        gd = GracefulDegradation("test")
        result = gd.execute(lambda: None)
        assert result is None

    def test_multiple_manual_degrades(self):
        gd = GracefulDegradation("test")
        gd.degrade_manually(DegradationLevel.PARTIAL)
        gd.degrade_manually(DegradationLevel.MINIMAL)
        gd.degrade_manually(DegradationLevel.NONE)
        assert gd.level == DegradationLevel.NONE

    def test_recover_when_already_full(self):
        gd = GracefulDegradation("test")
        gd.recover()
        assert gd.level == DegradationLevel.FULL

    def test_concurrent_record_requests(self):
        import threading
        gd = GracefulDegradation("test")
        errors = []

        def worker():
            try:
                for i in range(50):
                    gd.record_request(i % 2 == 0, float(i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert gd.state.total_requests == 500
