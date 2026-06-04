from typing import Dict, Any
from datetime import datetime
import asyncio
from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    status: str = Field(..., pattern="^(healthy|degraded|unhealthy)$")
    timestamp: datetime
    version: str = "1.0.0"
    uptime_seconds: float = Field(..., ge=0)
    checks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    message: str = ""


class HealthChecker:
    def __init__(self, db_pool, start_time: datetime):
        self.db_pool = db_pool
        self.start_time = start_time

    async def check_database(self) -> Dict[str, Any]:
        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                if result == 1:
                    return {"status": "healthy", "message": "Database connection OK"}
                return {"status": "unhealthy", "message": "Database query failed"}
        except Exception as e:
            return {"status": "unhealthy", "message": f"Database error: {str(e)}"}

    async def check_task_queue(self) -> Dict[str, Any]:
        try:
            async with self.db_pool.acquire() as conn:
                pending = await conn.fetchval(
                    "SELECT COUNT(*) FROM tasks WHERE status = 'pending'"
                )
                running = await conn.fetchval(
                    "SELECT COUNT(*) FROM tasks WHERE status = 'running'"
                )
                return {
                    "status": "healthy",
                    "message": f"Pending: {pending}, Running: {running}",
                    "pending_tasks": pending,
                    "running_tasks": running,
                }
        except Exception as e:
            return {"status": "unhealthy", "message": f"Task queue error: {str(e)}"}

    async def check_scheduler(self) -> Dict[str, Any]:
        try:
            async with self.db_pool.acquire() as conn:
                active = await conn.fetchval(
                    "SELECT COUNT(*) FROM scheduled_tasks WHERE enabled = true"
                )
                return {
                    "status": "healthy",
                    "message": f"Active schedules: {active}",
                    "active_schedules": active,
                }
        except Exception as e:
            return {"status": "degraded", "message": f"Scheduler error: {str(e)}"}

    async def get_health_status(self) -> HealthStatus:
        uptime = (datetime.utcnow() - self.start_time).total_seconds()

        checks = {
            "database": await self.check_database(),
            "task_queue": await self.check_task_queue(),
            "scheduler": await self.check_scheduler(),
        }

        unhealthy_count = sum(1 for c in checks.values() if c["status"] == "unhealthy")
        degraded_count = sum(1 for c in checks.values() if c["status"] == "degraded")

        if unhealthy_count > 0:
            overall_status = "unhealthy"
            message = f"{unhealthy_count} critical check(s) failed"
        elif degraded_count > 0:
            overall_status = "degraded"
            message = f"{degraded_count} check(s) degraded"
        else:
            overall_status = "healthy"
            message = "All systems operational"

        return HealthStatus(
            status=overall_status,
            timestamp=datetime.utcnow(),
            uptime_seconds=uptime,
            checks=checks,
            message=message,
        )

    async def get_readiness(self) -> bool:
        health = await self.get_health_status()
        return health.status != "unhealthy"

    async def get_liveness(self) -> bool:
        try:
            async with self.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                return True
        except Exception:
            return False
