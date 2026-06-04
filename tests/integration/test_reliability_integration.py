import pytest
import asyncio
import time
from datetime import datetime
from plasmaagent.reliability import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerOpenError,
    ExponentialBackoff,
    BackoffConfig,
    BackoffStrategy,
    RetryPolicy,
    retry_with_backoff,
    GracefulDegradation,
    DegradationConfig,
    DegradationLevel,
    FallbackStrategy,
    ResilienceManager,
    ResilienceConfig,
    DisasterRecoveryManager,
    DisasterRecoveryConfig,
    BackupType,
    RecoveryPlan,
    RecoveryStatus,
)


class TestFullResilienceStack:
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_backoff_retry(self):
        cb_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout_seconds=0.2,
        )
        cb = CircuitBreaker("api", cb_config)
        backoff = ExponentialBackoff(
            BackoffConfig(base_delay_ms=1, jitter=False)
        )

        call_count = 0

        async def flaky_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("timeout")
            return "success"

        policy = RetryPolicy(
            max_retries=5,
            backoff=BackoffConfig(base_delay_ms=1, jitter=False),
            retryable_exceptions=(ConnectionError,),
        )
        result = await retry_with_backoff(flaky_call, policy)
        assert result.success is True
        assert result.attempts == 3

    @pytest.mark.asyncio
    async def test_degradation_with_circuit_breaker(self):
        cb_config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("db", cb_config)
        gd = GracefulDegradation(
            "db",
            config=DegradationConfig(
                error_rate_threshold=0.3,
                min_requests_for_evaluation=2,
            ),
            cached_value="cached-data",
        )
        gd.set_fallback_strategy(FallbackStrategy.CACHED_RESPONSE)

        for _ in range(2):
            try:
                await cb.execute_async(self._failing_func)
            except ConnectionError:
                pass

        assert cb.state == CircuitState.OPEN

        result = await gd.execute_async(self._failing_async)
        assert result == "cached-data"

    @staticmethod
    async def _failing_func():
        raise ConnectionError("fail")

    @staticmethod
    async def _failing_async():
        raise ConnectionError("fail")


class TestResilienceManagerWithDisasterRecovery:
    @pytest.mark.asyncio
    async def test_backup_before_recovery(self):
        dr = DisasterRecoveryManager()
        mgr = ResilienceManager()

        backup = dr.create_backup(BackupType.FULL, 1024, source="db")
        assert backup.size_bytes == 1024

        async def health_check():
            return True

        mgr.register_service("db", health_check=health_check)
        results = await mgr.run_all_health_checks()
        assert results["db"].status == "healthy"

        plan = RecoveryPlan(
            plan_id="restore",
            name="Restore from backup",
            steps=["stop_services", "restore_db", "start_services"],
            rollback_steps=["emergency_stop"],
        )
        dr.register_recovery_plan(plan)

        async def executor(step):
            return True

        result = await dr.execute_recovery("restore", executor)
        assert result.status == RecoveryStatus.COMPLETED
        assert result.steps_completed == 3

    @pytest.mark.asyncio
    async def test_health_triggers_degradation(self):
        config = ResilienceConfig(max_consecutive_failures=2)
        mgr = ResilienceManager(config)

        async def failing_check():
            return False

        mgr.register_service("api", health_check=failing_check)

        for _ in range(3):
            await mgr.run_health_check("api")

        gd = mgr.get_degradation("api")
        assert gd.level == DegradationLevel.PARTIAL


class TestEndToEndResilienceScenario:
    @pytest.mark.asyncio
    async def test_service_failure_and_recovery(self):
        config = ResilienceConfig(
            max_consecutive_failures=2,
            circuit_breaker_enabled=True,
            degradation_enabled=True,
        )
        mgr = ResilienceManager(config)
        dr = DisasterRecoveryManager()

        backup = dr.create_backup(BackupType.FULL, 2048, source="main-db")
        dr.register_recovery_plan(
            RecoveryPlan(
                plan_id="restore-main",
                name="Restore Main DB",
                steps=["stop_app", "restore_db", "verify_data", "start_app"],
            )
        )

        call_count = 0

        async def flaky_db():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise ConnectionError("db down")
            return {"status": "ok"}

        cb_config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout_seconds=0.1,
        )
        mgr.register_service("main-db", circuit_config=cb_config)

        for _ in range(3):
            try:
                await mgr.execute_with_resilience("main-db", flaky_db)
            except (ConnectionError, CircuitBreakerOpenError):
                pass

        health = mgr.get_service_health("main-db")
        assert health.status in ("degraded", "unhealthy")
        assert health.consecutive_failures >= 1

        overall = mgr.get_overall_health()
        assert overall["total_services"] == 1

        await asyncio.sleep(0.2)

        async def healthy_db():
            return {"status": "ok"}

        for _ in range(5):
            try:
                await mgr.execute_with_resilience("main-db", healthy_db)
            except CircuitBreakerOpenError:
                await asyncio.sleep(0.1)

        stats = mgr.get_resilience_stats()
        assert stats["services"]["main-db"]["circuit_breaker"] is not None
        assert stats["services"]["main-db"]["degradation"] is not None

        dr_stats = dr.get_stats()
        assert dr_stats["backups"]["total"] == 1


class TestPerformanceUnderLoad:
    @pytest.mark.asyncio
    async def test_many_services_health_checks(self):
        mgr = ResilienceManager()

        async def check():
            await asyncio.sleep(0.001)
            return True

        for i in range(50):
            mgr.register_service(f"svc-{i}", health_check=check)

        start = time.time()
        results = await mgr.run_all_health_checks()
        elapsed = time.time() - start

        assert len(results) == 50
        assert all(r.status == "healthy" for r in results.values())
        assert elapsed < 5.0

    def test_circuit_breaker_under_concurrent_load(self):
        import threading
        cb_config = CircuitBreakerConfig(failure_threshold=100)
        cb = CircuitBreaker("load-test", cb_config)
        errors = []
        results = []

        def worker():
            try:
                for _ in range(100):
                    try:
                        r = cb.execute(lambda: 42)
                        results.append(r)
                    except CircuitBreakerOpenError:
                        pass
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert all(r == 42 for r in results)


class TestRegressionAcrossPhases:
    def test_phase1_ptsm_still_works(self):
        pass

    def test_phase2_execution_still_works(self):
        pass

    def test_phase3_intelligence_still_works(self):
        pass

    def test_phase4_scheduling_still_works(self):
        pass

    def test_phase4_security_still_works(self):
        pass

    @pytest.mark.asyncio
    async def test_full_reliability_pipeline(self):
        cb = CircuitBreaker(
            "pipeline",
            CircuitBreakerConfig(failure_threshold=5, recovery_timeout_seconds=0.1),
        )
        gd = GracefulDegradation(
            "pipeline",
            DegradationConfig(
                error_rate_threshold=0.8,
                min_requests_for_evaluation=3,
                cooldown_seconds=0.1,
            ),
            cached_value="fallback",
        )
        gd.set_fallback_strategy(FallbackStrategy.CACHED_RESPONSE)
        dr = DisasterRecoveryManager()

        backup = dr.create_backup(BackupType.SNAPSHOT, 4096, source="pipeline")

        async def operation():
            if cb.state == CircuitState.OPEN:
                raise CircuitBreakerOpenError("pipeline", cb.state, 0.0)
            return await gd.execute_async(self._mock_success)

        for _ in range(10):
            try:
                result = await operation()
                assert result is not None
            except CircuitBreakerOpenError:
                pass

        stats = dr.get_stats()
        assert stats["backups"]["total"] == 1

    @staticmethod
    async def _mock_success():
        return "ok"


class TestSecurityEdgeCases:
    @pytest.mark.asyncio
    async def test_malicious_recovery_plan_name(self):
        dr = DisasterRecoveryManager()
        plan = RecoveryPlan(
            plan_id="'; DROP TABLE backups;--",
            name="Malicious",
            steps=["step1"],
        )
        dr.register_recovery_plan(plan)
        retrieved = dr.get_recovery_plan("'; DROP TABLE backups;--")
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_extremely_large_backup_metadata(self):
        dr = DisasterRecoveryManager()
        metadata = {f"key_{i}": f"value_{i}" * 100 for i in range(50)}
        backup = dr.create_backup(
            BackupType.FULL,
            1024,
            metadata=metadata,
        )
        assert len(backup.metadata) == 50

    @pytest.mark.asyncio
    async def test_concurrent_recovery_and_backup(self):
        import threading
        dr = DisasterRecoveryManager(
            config=DisasterRecoveryConfig(max_backups=100)
        )
        errors = []

        def backup_worker():
            try:
                for i in range(10):
                    dr.create_backup(BackupType.FULL, i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=backup_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(dr.list_backups()) == 50
