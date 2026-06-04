from typing import Dict, Any, Callable, Awaitable
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import asyncio
import json
import threading


class BackupType(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    SNAPSHOT = "snapshot"


class RecoveryStatus(str, Enum):
    IDLE = "idle"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLBACK = "rollback"


class BackupMetadata(BaseModel):
    backup_id: str
    backup_type: BackupType
    timestamp: datetime
    size_bytes: int = Field(ge=0)
    checksum: str = ""
    source: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecoveryPlan(BaseModel):
    plan_id: str
    name: str
    steps: list[str] = Field(default_factory=list)
    estimated_duration_seconds: float = Field(ge=0, default=0.0)
    rollback_steps: list[str] = Field(default_factory=list)
    requires_downtime: bool = False


class RecoveryResult(BaseModel):
    plan_id: str
    status: RecoveryStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    steps_completed: int = 0
    total_steps: int = 0
    error: str | None = None
    rolled_back: bool = False


class DisasterRecoveryConfig(BaseModel):
    max_backups: int = Field(ge=1, le=100, default=10)
    backup_retention_days: int = Field(ge=1, le=365, default=30)
    auto_backup_interval_seconds: float = Field(ge=60.0, le=86400.0, default=3600.0)
    max_recovery_attempts: int = Field(ge=1, le=10, default=3)
    verify_after_recovery: bool = True


class DisasterRecoveryManager:
    def __init__(self, config: DisasterRecoveryConfig | None = None):
        self._config = config or DisasterRecoveryConfig()
        self._backups: list[BackupMetadata] = []
        self._recovery_plans: Dict[str, RecoveryPlan] = {}
        self._recovery_history: list[RecoveryResult] = []
        self._current_recovery: RecoveryResult | None = None
        self._lock = threading.RLock()

    @property
    def config(self) -> DisasterRecoveryConfig:
        return self._config

    def create_backup(
        self,
        backup_type: BackupType,
        size_bytes: int,
        source: str = "",
        checksum: str = "",
        metadata: Dict[str, Any] | None = None,
    ) -> BackupMetadata:
        with self._lock:
            import uuid
            backup = BackupMetadata(
                backup_id=str(uuid.uuid4()),
                backup_type=backup_type,
                timestamp=datetime.now(),
                size_bytes=size_bytes,
                checksum=checksum,
                source=source,
                metadata=metadata or {},
            )
            self._backups.append(backup)
            if len(self._backups) > self._config.max_backups:
                self._backups = self._backups[-self._config.max_backups:]
            return backup

    def list_backups(self) -> list[BackupMetadata]:
        with self._lock:
            return [b.model_copy() for b in self._backups]

    def get_backup(self, backup_id: str) -> BackupMetadata | None:
        with self._lock:
            for b in self._backups:
                if b.backup_id == backup_id:
                    return b.model_copy()
            return None

    def delete_backup(self, backup_id: str) -> bool:
        with self._lock:
            for i, b in enumerate(self._backups):
                if b.backup_id == backup_id:
                    self._backups.pop(i)
                    return True
            return False

    def cleanup_old_backups(self) -> int:
        with self._lock:
            cutoff = datetime.now()
            from datetime import timedelta
            cutoff = cutoff - timedelta(days=self._config.backup_retention_days)
            original_count = len(self._backups)
            self._backups = [b for b in self._backups if b.timestamp >= cutoff]
            return original_count - len(self._backups)

    def register_recovery_plan(self, plan: RecoveryPlan) -> None:
        with self._lock:
            self._recovery_plans[plan.plan_id] = plan

    def unregister_recovery_plan(self, plan_id: str) -> bool:
        with self._lock:
            if plan_id in self._recovery_plans:
                del self._recovery_plans[plan_id]
                return True
            return False

    def get_recovery_plan(self, plan_id: str) -> RecoveryPlan | None:
        with self._lock:
            plan = self._recovery_plans.get(plan_id)
            return plan.model_copy() if plan else None

    def list_recovery_plans(self) -> list[RecoveryPlan]:
        with self._lock:
            return [p.model_copy() for p in self._recovery_plans.values()]

    async def execute_recovery(
        self,
        plan_id: str,
        step_executor: Callable[[str], Awaitable[bool]] | None = None,
    ) -> RecoveryResult:
        with self._lock:
            plan = self._recovery_plans.get(plan_id)
            if not plan:
                return RecoveryResult(
                    plan_id=plan_id,
                    status=RecoveryStatus.FAILED,
                    error="Recovery plan not found",
                )
            if self._current_recovery and self._current_recovery.status == RecoveryStatus.IN_PROGRESS:
                return RecoveryResult(
                    plan_id=plan_id,
                    status=RecoveryStatus.FAILED,
                    error="Recovery already in progress",
                )

            result = RecoveryResult(
                plan_id=plan_id,
                status=RecoveryStatus.IN_PROGRESS,
                started_at=datetime.now(),
                total_steps=len(plan.steps),
            )
            self._current_recovery = result

        attempts = 0
        for i, step in enumerate(plan.steps):
            attempts = 0
            success = False
            while attempts < self._config.max_recovery_attempts:
                attempts += 1
                try:
                    if step_executor:
                        success = await step_executor(step)
                    else:
                        success = True
                    if success:
                        break
                except Exception:
                    success = False

            with self._lock:
                if success:
                    result.steps_completed = i + 1
                else:
                    result.status = RecoveryStatus.FAILED
                    result.error = f"Step failed after {attempts} attempts: {step}"
                    result.completed_at = datetime.now()
                    if plan.rollback_steps:
                        result.rolled_back = True
                    self._current_recovery = None
                    self._recovery_history.append(result.model_copy())
                    return result

        with self._lock:
            result.status = RecoveryStatus.COMPLETED
            result.completed_at = datetime.now()
            self._current_recovery = None
            self._recovery_history.append(result.model_copy())
            return result

    def get_recovery_history(self) -> list[RecoveryResult]:
        with self._lock:
            return [r.model_copy() for r in self._recovery_history]

    def get_current_recovery(self) -> RecoveryResult | None:
        with self._lock:
            if self._current_recovery:
                return self._current_recovery.model_copy()
            return None

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total_backups = len(self._backups)
            total_size = sum(b.size_bytes for b in self._backups)
            total_recoveries = len(self._recovery_history)
            successful = sum(
                1 for r in self._recovery_history
                if r.status == RecoveryStatus.COMPLETED
            )
            failed = sum(
                1 for r in self._recovery_history
                if r.status == RecoveryStatus.FAILED
            )

            latest_backup = (
                self._backups[-1].timestamp.isoformat()
                if self._backups
                else None
            )

            return {
                "backups": {
                    "total": total_backups,
                    "total_size_bytes": total_size,
                    "latest": latest_backup,
                    "max_backups": self._config.max_backups,
                    "retention_days": self._config.backup_retention_days,
                },
                "recovery_plans": len(self._recovery_plans),
                "recovery_history": {
                    "total": total_recoveries,
                    "successful": successful,
                    "failed": failed,
                    "success_rate": (
                        successful / total_recoveries
                        if total_recoveries > 0
                        else 0.0
                    ),
                },
                "current_recovery": (
                    self._current_recovery.status.value
                    if self._current_recovery
                    else None
                ),
            }

    def export_backup_manifest(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "exported_at": datetime.now().isoformat(),
                "backup_count": len(self._backups),
                "backups": [b.model_dump() for b in self._backups],
                "recovery_plans": [
                    p.model_dump() for p in self._recovery_plans.values()
                ],
            }
