import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch
from plasmaagent.reliability import (
    ResilienceManager,
    ResilienceConfig,
    ServiceHealth,
    CircuitBreakerConfig,
    DegradationConfig,
    DegradationLevel,
    CircuitState,
)


class TestResilienceConfig:
    def test_default_values(self):
        config = ResilienceConfig()
        assert config.health_check_interval_seconds == 30.0
        assert config.auto_degrade_on_failure is True
        assert config.circuit_breaker_enabled is True
        assert config.degradation_enabled is True
        assert config.max_consecutive_failures == 3

    def test_custom_values(self):
        config = ResilienceConfig(
            health_check_interval_seconds=60.0,
            auto_degrade_on_failure=False,
            max_consecutive_failures=5,
        )
        assert config.health_check_interval_seconds == 60.0
        assert config.auto_degrade_on_failure is False

    def test_bounds(self):
        with pytest.raises(Exception):
            ResilienceConfig(health_check_interval_seconds=0.5)
        with pytest.raises(Exception):
            ResilienceConfig(health_check_interval_seconds=3601.0)
        with pytest.raises(Exception):
            ResilienceConfig(max_consecutive_failures=0)
        with pytest.raises(Exception):
            ResilienceConfig(max_consecutive_failures=101)


class TestServiceHealth:
    def test_healthy(self):
        health = ServiceHealth(name="test", status="healthy")
        assert health.name == "test"
        assert health.status == "healthy"
        assert health.circuit_state == "closed"
        assert health.degradation_level == "full"

    def test_invalid_status(self):
        with pytest.raises(Exception):
            ServiceHealth(name="test", status="invalid")


class TestResilienceManagerRegistration:
    def test_register_service(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        assert "db" in mgr.get_service_names()

    def test_register_multiple(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        mgr.register_service("cache")
        mgr.register_service("api")
        assert len(mgr.get_service_names()) == 3

    def test_unregister_service(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        assert mgr.unregister_service("db") is True
        assert "db" not in mgr.get_service_names()

    def test_unregister_nonexistent(self):
        mgr = ResilienceManager()
        assert mgr.unregister_service("nonexistent") is False

    def test_register_with_configs(self):
        mgr = ResilienceManager()
        cb_config = CircuitBreakerConfig(failure_threshold=10)
        dg_config = DegradationConfig(error_rate_threshold=0.3)
        mgr.register_service("db", circuit_config=cb_config, degradation_config=dg_config)
        cb = mgr.get_circuit_breaker("db")
        assert cb is not None

    def test_register_without_circuit_breaker(self):
        config = ResilienceConfig(circuit_breaker_enabled=False)
        mgr = ResilienceManager(config)
        mgr.register_service("db")
        assert mgr.get_circuit_breaker("db") is None

    def test_register_without_degradation(self):
        config = ResilienceConfig(degradation_enabled=False)
        mgr = ResilienceManager(config)
        mgr.register_service("db")
        assert mgr.get_degradation("db") is None


class TestResilienceManagerRecordSuccess:
    def test_record_success(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        mgr.record_success("db", 10.0)
        health = mgr.get_service_health("db")
        assert health.status == "healthy"
        assert health.consecutive_failures == 0

    def test_record_success_resets_failures(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        mgr.record_failure("db")
        mgr.record_failure("db")
        mgr.record_success("db")
        health = mgr.get_service_health("db")
        assert health.consecutive_failures == 0

    def test_record_success_updates_circuit(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        mgr.record_success("db")
        cb = mgr.get_circuit_breaker("db")
        assert cb.success_count == 1

    def test_record_success_updates_degradation(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        mgr.record_success("db", 10.0)
        gd = mgr.get_degradation("db")
        assert gd.state.total_requests == 1

    def test_record_success_nonexistent(self):
        mgr = ResilienceManager()
        mgr.record_success("nonexistent")


class TestResilienceManagerRecordFailure:
    def test_record_failure(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        mgr.record_failure("db")
        health = mgr.get_service_health("db")
        assert health.consecutive_failures == 1

    def test_auto_degrade_after_max_failures(self):
        config = ResilienceConfig(max_consecutive_failures=3)
        mgr = ResilienceManager(config)
        mgr.register_service("db")
        mgr.record_failure("db")
        mgr.record_failure("db")
        mgr.record_failure("db")
        gd = mgr.get_degradation("db")
        assert gd.level == DegradationLevel.PARTIAL

    def test_no_auto_degrade_when_disabled(self):
        config = ResilienceConfig(auto_degrade_on_failure=False, max_consecutive_failures=1)
        mgr = ResilienceManager(config)
        mgr.register_service("db")
        mgr.record_failure("db")
        gd = mgr.get_degradation("db")
        assert gd.level == DegradationLevel.FULL

    def test_record_failure_nonexistent(self):
        mgr = ResilienceManager()
        mgr.record_failure("nonexistent")


class TestResilienceManagerHealthCheck:
    @pytest.mark.asyncio
    async def test_run_health_check_healthy(self):
        async def check():
            return True

        mgr = ResilienceManager()
        mgr.register_service("db", health_check=check)
        health = await mgr.run_health_check("db")
        assert health.status == "healthy"

    @pytest.mark.asyncio
    async def test_run_health_check_unhealthy(self):
        async def check():
            return False

        mgr = ResilienceManager()
        mgr.register_service("db", health_check=check)
        health = await mgr.run_health_check("db")
        assert health.status == "degraded"
        assert health.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_run_health_check_exception(self):
        async def check():
            raise RuntimeError("db down")

        mgr = ResilienceManager()
        mgr.register_service("db", health_check=check)
        health = await mgr.run_health_check("db")
        assert health.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_run_health_check_nonexistent(self):
        mgr = ResilienceManager()
        health = await mgr.run_health_check("nonexistent")
        assert health.status == "unhealthy"

    @pytest.mark.asyncio
    async def test_run_all_health_checks(self):
        async def healthy_check():
            return True

        async def unhealthy_check():
            return False

        mgr = ResilienceManager()
        mgr.register_service("db", health_check=healthy_check)
        mgr.register_service("cache", health_check=unhealthy_check)
        results = await mgr.run_all_health_checks()
        assert len(results) == 2
        assert results["db"].status == "healthy"
        assert results["cache"].consecutive_failures == 1


class TestResilienceManagerServiceHealth:
    def test_healthy_when_no_failures(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        health = mgr.get_service_health("db")
        assert health.status == "healthy"

    def test_degraded_with_consecutive_failures(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        mgr.record_failure("db")
        health = mgr.get_service_health("db")
        assert health.status == "degraded"

    def test_unhealthy_when_circuit_open(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        mgr = ResilienceManager()
        mgr.register_service("db", circuit_config=config)
        mgr.record_failure("db")
        cb = mgr.get_circuit_breaker("db")
        assert cb.state == CircuitState.OPEN
        health = mgr.get_service_health("db")
        assert health.status == "unhealthy"

    def test_nonexistent_service(self):
        mgr = ResilienceManager()
        health = mgr.get_service_health("nonexistent")
        assert health.status == "unhealthy"
        assert health.message == "Service not registered"


class TestResilienceManagerOverallHealth:
    def test_all_healthy(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        mgr.register_service("cache")
        result = mgr.get_overall_health()
        assert result["status"] == "healthy"
        assert result["total_services"] == 2
        assert result["healthy"] == 2

    def test_some_degraded(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        mgr.register_service("cache")
        mgr.record_failure("cache")
        result = mgr.get_overall_health()
        assert result["status"] == "degraded"
        assert result["degraded"] == 1

    def test_some_unhealthy(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        mgr = ResilienceManager()
        mgr.register_service("db", circuit_config=config)
        mgr.register_service("cache")
        mgr.record_failure("db")
        result = mgr.get_overall_health()
        assert result["status"] == "unhealthy"
        assert result["unhealthy"] == 1

    def test_uptime_tracking(self):
        mgr = ResilienceManager()
        result = mgr.get_overall_health()
        assert result["uptime_seconds"] >= 0


class TestResilienceManagerExecute:
    @pytest.mark.asyncio
    async def test_execute_success(self):
        mgr = ResilienceManager()
        mgr.register_service("db")

        async def func():
            return 42

        result = await mgr.execute_with_resilience("db", func)
        assert result == 42

    @pytest.mark.asyncio
    async def test_execute_failure_records(self):
        mgr = ResilienceManager()
        mgr.register_service("db")

        async def func():
            raise ValueError("oops")

        with pytest.raises(ValueError):
            await mgr.execute_with_resilience("db", func)
        health = mgr.get_service_health("db")
        assert health.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_execute_nonexistent_service(self):
        mgr = ResilienceManager()

        async def func():
            return 42

        with pytest.raises(ValueError, match="not registered"):
            await mgr.execute_with_resilience("nonexistent", func)

    @pytest.mark.asyncio
    async def test_execute_with_circuit_breaker(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        mgr = ResilienceManager()
        mgr.register_service("db", circuit_config=config)

        async def failing():
            raise ValueError("oops")

        with pytest.raises(ValueError):
            await mgr.execute_with_resilience("db", failing)

        async def func():
            return 42

        from plasmaagent.reliability import CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await mgr.execute_with_resilience("db", func)

    @pytest.mark.asyncio
    async def test_execute_without_circuit_or_degradation(self):
        config = ResilienceConfig(
            circuit_breaker_enabled=False,
            degradation_enabled=False,
        )
        mgr = ResilienceManager(config)
        mgr.register_service("db")

        async def func():
            return 42

        result = await mgr.execute_with_resilience("db", func)
        assert result == 42


class TestResilienceManagerStats:
    def test_get_resilience_stats(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        mgr.register_service("cache")
        stats = mgr.get_resilience_stats()
        assert "overall" in stats
        assert "services" in stats
        assert "config" in stats
        assert "db" in stats["services"]
        assert "cache" in stats["services"]

    def test_stats_include_circuit_breaker(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        stats = mgr.get_resilience_stats()
        assert stats["services"]["db"]["circuit_breaker"] is not None

    def test_stats_include_degradation(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        stats = mgr.get_resilience_stats()
        assert stats["services"]["db"]["degradation"] is not None

    def test_stats_after_failures(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        mgr.record_failure("db")
        mgr.record_failure("db")
        stats = mgr.get_resilience_stats()
        assert stats["services"]["db"]["consecutive_failures"] == 2


class TestResilienceManagerEdgeCases:
    def test_empty_manager(self):
        mgr = ResilienceManager()
        result = mgr.get_overall_health()
        assert result["status"] == "healthy"
        assert result["total_services"] == 0

    def test_register_same_name_twice(self):
        mgr = ResilienceManager()
        mgr.register_service("db")
        mgr.register_service("db")
        assert len(mgr.get_service_names()) == 1

    def test_get_circuit_breaker_nonexistent(self):
        mgr = ResilienceManager()
        assert mgr.get_circuit_breaker("nonexistent") is None

    def test_get_degradation_nonexistent(self):
        mgr = ResilienceManager()
        assert mgr.get_degradation("nonexistent") is None

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self):
        async def check():
            await asyncio.sleep(0.01)
            return True

        mgr = ResilienceManager()
        for i in range(10):
            mgr.register_service(f"svc-{i}", health_check=check)

        results = await mgr.run_all_health_checks()
        assert len(results) == 10
        assert all(r.status == "healthy" for r in results.values())
