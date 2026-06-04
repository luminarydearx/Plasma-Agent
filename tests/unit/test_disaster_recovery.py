import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from plasmaagent.reliability import (
    DisasterRecoveryManager,
    DisasterRecoveryConfig,
    BackupMetadata,
    BackupType,
    RecoveryPlan,
    RecoveryResult,
    RecoveryStatus,
)


class TestBackupType:
    def test_types_exist(self):
        assert BackupType.FULL == "full"
        assert BackupType.INCREMENTAL == "incremental"
        assert BackupType.SNAPSHOT == "snapshot"


class TestRecoveryStatus:
    def test_statuses_exist(self):
        assert RecoveryStatus.IDLE == "idle"
        assert RecoveryStatus.IN_PROGRESS == "in_progress"
        assert RecoveryStatus.COMPLETED == "completed"
        assert RecoveryStatus.FAILED == "failed"
        assert RecoveryStatus.ROLLBACK == "rollback"


class TestDisasterRecoveryConfig:
    def test_default_values(self):
        config = DisasterRecoveryConfig()
        assert config.max_backups == 10
        assert config.backup_retention_days == 30
        assert config.auto_backup_interval_seconds == 3600.0
        assert config.max_recovery_attempts == 3
        assert config.verify_after_recovery is True

    def test_custom_values(self):
        config = DisasterRecoveryConfig(
            max_backups=5,
            backup_retention_days=7,
            max_recovery_attempts=5,
        )
        assert config.max_backups == 5

    def test_bounds(self):
        with pytest.raises(Exception):
            DisasterRecoveryConfig(max_backups=0)
        with pytest.raises(Exception):
            DisasterRecoveryConfig(max_backups=101)
        with pytest.raises(Exception):
            DisasterRecoveryConfig(backup_retention_days=0)
        with pytest.raises(Exception):
            DisasterRecoveryConfig(backup_retention_days=366)
        with pytest.raises(Exception):
            DisasterRecoveryConfig(auto_backup_interval_seconds=30.0)
        with pytest.raises(Exception):
            DisasterRecoveryConfig(max_recovery_attempts=0)


class TestBackupMetadata:
    def test_creation(self):
        backup = BackupMetadata(
            backup_id="test-123",
            backup_type=BackupType.FULL,
            timestamp=datetime.now(),
            size_bytes=1024,
            checksum="abc123",
            source="db",
        )
        assert backup.backup_id == "test-123"
        assert backup.size_bytes == 1024

    def test_negative_size_raises(self):
        with pytest.raises(Exception):
            BackupMetadata(
                backup_id="test",
                backup_type=BackupType.FULL,
                timestamp=datetime.now(),
                size_bytes=-1,
            )


class TestRecoveryPlan:
    def test_creation(self):
        plan = RecoveryPlan(
            plan_id="plan-1",
            name="Full Recovery",
            steps=["restore_db", "restore_cache", "restart_services"],
            estimated_duration_seconds=300.0,
            rollback_steps=["stop_services", "restore_original"],
            requires_downtime=True,
        )
        assert plan.plan_id == "plan-1"
        assert len(plan.steps) == 3
        assert plan.requires_downtime is True

    def test_negative_duration_raises(self):
        with pytest.raises(Exception):
            RecoveryPlan(
                plan_id="plan",
                name="test",
                estimated_duration_seconds=-1,
            )


class TestRecoveryResult:
    def test_creation(self):
        result = RecoveryResult(
            plan_id="plan-1",
            status=RecoveryStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            steps_completed=3,
            total_steps=3,
        )
        assert result.status == RecoveryStatus.COMPLETED
        assert result.steps_completed == 3


class TestDisasterRecoveryManagerBackups:
    def test_create_backup(self):
        mgr = DisasterRecoveryManager()
        backup = mgr.create_backup(BackupType.FULL, 1024, source="db")
        assert backup.size_bytes == 1024
        assert backup.source == "db"

    def test_list_backups(self):
        mgr = DisasterRecoveryManager()
        mgr.create_backup(BackupType.FULL, 1024)
        mgr.create_backup(BackupType.INCREMENTAL, 512)
        backups = mgr.list_backups()
        assert len(backups) == 2

    def test_get_backup(self):
        mgr = DisasterRecoveryManager()
        backup = mgr.create_backup(BackupType.FULL, 1024)
        retrieved = mgr.get_backup(backup.backup_id)
        assert retrieved is not None
        assert retrieved.backup_id == backup.backup_id

    def test_get_nonexistent_backup(self):
        mgr = DisasterRecoveryManager()
        assert mgr.get_backup("nonexistent") is None

    def test_delete_backup(self):
        mgr = DisasterRecoveryManager()
        backup = mgr.create_backup(BackupType.FULL, 1024)
        assert mgr.delete_backup(backup.backup_id) is True
        assert mgr.get_backup(backup.backup_id) is None

    def test_delete_nonexistent(self):
        mgr = DisasterRecoveryManager()
        assert mgr.delete_backup("nonexistent") is False

    def test_max_backups_limit(self):
        config = DisasterRecoveryConfig(max_backups=3)
        mgr = DisasterRecoveryManager(config)
        for i in range(5):
            mgr.create_backup(BackupType.FULL, 100 * i)
        backups = mgr.list_backups()
        assert len(backups) == 3

    def test_cleanup_old_backups(self):
        mgr = DisasterRecoveryManager()
        backup = mgr.create_backup(BackupType.FULL, 1024)
        with pytest.MonkeyPatch.context() as m:
            pass
        removed = mgr.cleanup_old_backups()
        assert removed == 0


class TestDisasterRecoveryManagerPlans:
    def test_register_plan(self):
        mgr = DisasterRecoveryManager()
        plan = RecoveryPlan(plan_id="p1", name="Test Plan", steps=["step1"])
        mgr.register_recovery_plan(plan)
        assert mgr.get_recovery_plan("p1") is not None

    def test_unregister_plan(self):
        mgr = DisasterRecoveryManager()
        plan = RecoveryPlan(plan_id="p1", name="Test Plan")
        mgr.register_recovery_plan(plan)
        assert mgr.unregister_recovery_plan("p1") is True
        assert mgr.get_recovery_plan("p1") is None

    def test_unregister_nonexistent(self):
        mgr = DisasterRecoveryManager()
        assert mgr.unregister_recovery_plan("nonexistent") is False

    def test_list_plans(self):
        mgr = DisasterRecoveryManager()
        mgr.register_recovery_plan(RecoveryPlan(plan_id="p1", name="P1"))
        mgr.register_recovery_plan(RecoveryPlan(plan_id="p2", name="P2"))
        plans = mgr.list_recovery_plans()
        assert len(plans) == 2


class TestDisasterRecoveryManagerExecute:
    @pytest.mark.asyncio
    async def test_execute_recovery_success(self):
        mgr = DisasterRecoveryManager()
        plan = RecoveryPlan(
            plan_id="p1",
            name="Test",
            steps=["step1", "step2", "step3"],
        )
        mgr.register_recovery_plan(plan)

        async def executor(step):
            return True

        result = await mgr.execute_recovery("p1", executor)
        assert result.status == RecoveryStatus.COMPLETED
        assert result.steps_completed == 3

    @pytest.mark.asyncio
    async def test_execute_recovery_failure(self):
        mgr = DisasterRecoveryManager()
        plan = RecoveryPlan(
            plan_id="p1",
            name="Test",
            steps=["step1", "failing_step"],
        )
        mgr.register_recovery_plan(plan)

        call_count = 0

        async def executor(step):
            nonlocal call_count
            call_count += 1
            if step == "failing_step":
                return False
            return True

        result = await mgr.execute_recovery("p1", executor)
        assert result.status == RecoveryStatus.FAILED
        assert result.steps_completed == 1

    @pytest.mark.asyncio
    async def test_execute_nonexistent_plan(self):
        mgr = DisasterRecoveryManager()
        result = await mgr.execute_recovery("nonexistent")
        assert result.status == RecoveryStatus.FAILED
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_exception(self):
        mgr = DisasterRecoveryManager()
        plan = RecoveryPlan(plan_id="p1", name="Test", steps=["fail_step"])
        mgr.register_recovery_plan(plan)

        async def executor(step):
            raise RuntimeError("boom")

        result = await mgr.execute_recovery("p1", executor)
        assert result.status == RecoveryStatus.FAILED

    @pytest.mark.asyncio
    async def test_concurrent_recovery_blocked(self):
        mgr = DisasterRecoveryManager()
        plan = RecoveryPlan(
            plan_id="p1",
            name="Test",
            steps=["step1"],
        )
        mgr.register_recovery_plan(plan)

        barrier = asyncio.Event()

        async def slow_executor(step):
            await barrier.wait()
            return True

        task1 = asyncio.create_task(mgr.execute_recovery("p1", slow_executor))
        await asyncio.sleep(0.05)
        task2 = asyncio.create_task(mgr.execute_recovery("p1", slow_executor))
        await asyncio.sleep(0.05)

        result2 = await task2
        assert result2.status == RecoveryStatus.FAILED
        assert "already in progress" in result2.error

        barrier.set()
        result1 = await task1
        assert result1.status == RecoveryStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_recovery_with_rollback_on_failure(self):
        mgr = DisasterRecoveryManager()
        plan = RecoveryPlan(
            plan_id="p1",
            name="Test",
            steps=["fail_step"],
            rollback_steps=["rollback1"],
        )
        mgr.register_recovery_plan(plan)

        async def executor(step):
            return False

        result = await mgr.execute_recovery("p1", executor)
        assert result.status == RecoveryStatus.FAILED
        assert result.rolled_back is True


class TestDisasterRecoveryManagerHistory:
    @pytest.mark.asyncio
    async def test_recovery_history(self):
        mgr = DisasterRecoveryManager()
        plan = RecoveryPlan(plan_id="p1", name="Test", steps=["s1"])
        mgr.register_recovery_plan(plan)

        async def executor(step):
            return True

        await mgr.execute_recovery("p1", executor)
        history = mgr.get_recovery_history()
        assert len(history) == 1

    def test_empty_history(self):
        mgr = DisasterRecoveryManager()
        assert mgr.get_recovery_history() == []

    def test_current_recovery_idle(self):
        mgr = DisasterRecoveryManager()
        assert mgr.get_current_recovery() is None


class TestDisasterRecoveryManagerStats:
    def test_stats_empty(self):
        mgr = DisasterRecoveryManager()
        stats = mgr.get_stats()
        assert stats["backups"]["total"] == 0
        assert stats["recovery_plans"] == 0
        assert stats["recovery_history"]["total"] == 0

    def test_stats_with_backups(self):
        mgr = DisasterRecoveryManager()
        mgr.create_backup(BackupType.FULL, 1024)
        mgr.create_backup(BackupType.INCREMENTAL, 512)
        stats = mgr.get_stats()
        assert stats["backups"]["total"] == 2
        assert stats["backups"]["total_size_bytes"] == 1536

    def test_stats_with_plans(self):
        mgr = DisasterRecoveryManager()
        mgr.register_recovery_plan(RecoveryPlan(plan_id="p1", name="P1"))
        stats = mgr.get_stats()
        assert stats["recovery_plans"] == 1

    @pytest.mark.asyncio
    async def test_stats_with_recoveries(self):
        mgr = DisasterRecoveryManager()
        plan = RecoveryPlan(plan_id="p1", name="Test", steps=["s1"])
        mgr.register_recovery_plan(plan)

        async def executor(step):
            return True

        await mgr.execute_recovery("p1", executor)
        stats = mgr.get_stats()
        assert stats["recovery_history"]["total"] == 1
        assert stats["recovery_history"]["successful"] == 1
        assert stats["recovery_history"]["success_rate"] == 1.0


class TestDisasterRecoveryManagerExport:
    def test_export_manifest(self):
        mgr = DisasterRecoveryManager()
        mgr.create_backup(BackupType.FULL, 1024, source="db")
        mgr.register_recovery_plan(
            RecoveryPlan(plan_id="p1", name="Test", steps=["s1"])
        )
        manifest = mgr.export_backup_manifest()
        assert manifest["backup_count"] == 1
        assert len(manifest["backups"]) == 1
        assert len(manifest["recovery_plans"]) == 1
        assert "exported_at" in manifest


class TestDisasterRecoveryEdgeCases:
    def test_list_backups_returns_copies(self):
        mgr = DisasterRecoveryManager()
        mgr.create_backup(BackupType.FULL, 1024)
        list1 = mgr.list_backups()
        list2 = mgr.list_backups()
        assert list1[0].backup_id == list2[0].backup_id
        assert list1 is not list2

    def test_create_backup_with_metadata(self):
        mgr = DisasterRecoveryManager()
        backup = mgr.create_backup(
            BackupType.FULL,
            1024,
            metadata={"key": "value"},
        )
        assert backup.metadata["key"] == "value"

    @pytest.mark.asyncio
    async def test_recovery_with_no_executor(self):
        mgr = DisasterRecoveryManager()
        plan = RecoveryPlan(plan_id="p1", name="Test", steps=["s1", "s2"])
        mgr.register_recovery_plan(plan)
        result = await mgr.execute_recovery("p1")
        assert result.status == RecoveryStatus.COMPLETED
        assert result.steps_completed == 2

    def test_concurrent_backup_creation(self):
        import threading
        mgr = DisasterRecoveryManager(
            config=DisasterRecoveryConfig(max_backups=100)
        )
        errors = []

        def worker(i):
            try:
                mgr.create_backup(BackupType.FULL, i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(mgr.list_backups()) == 20
