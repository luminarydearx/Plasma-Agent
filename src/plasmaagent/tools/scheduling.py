"""Scheduling tools for PlasmaAgent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    data: Any = None


async def cron_schedule(task_name: str, cron_expression: str, commands: list[str]) -> ToolResult:
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.scheduling.service import SchedulingService

        db = get_database()
        await db.connect()
        try:
            task_id = uuid4()
            payload = json.dumps({"commands": commands})
            async with db.transaction() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO tasks (id, name, status, payload, created_at, updated_at) "
                        "VALUES (%s, %s, 'PENDING', %s, NOW(), NOW())",
                        (task_id, task_name, payload),
                    )
            service = SchedulingService(db)
            result = await service.enable_schedule(
                task_id=task_id,
                cron_expression=cron_expression,
            )
            if result is None:
                return ToolResult(False, f"Failed to schedule task '{task_name}'")
            next_run = result.next_run_at
            return ToolResult(
                True,
                f"Scheduled '{task_name}' with cron '{cron_expression}'. Next run: {next_run}",
                {"task_id": str(task_id), "next_run": str(next_run)},
            )
        finally:
            await db.disconnect()
    except Exception as e:
        return ToolResult(False, f"Failed to schedule: {e}")


async def schedule_once(task_name: str, run_at: str, commands: list[str]) -> ToolResult:
    try:
        from plasmaagent.core.database import get_database

        db = get_database()
        await db.connect()
        try:
            run_time = datetime.fromisoformat(run_at.replace("Z", "+00:00"))
            task_id = uuid4()
            payload = json.dumps({"commands": commands, "type": "one_time"})
            async with db.transaction() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO tasks (id, name, status, payload, created_at, updated_at) "
                        "VALUES (%s, %s, 'PENDING', %s, NOW(), NOW())",
                        (task_id, task_name, payload),
                    )
                    await cur.execute(
                        "INSERT INTO schedules (id, task_id, schedule_type, run_at, status, created_at) "
                        "VALUES (%s, %s, 'ONETIME', %s, 'ACTIVE', NOW())",
                        (uuid4(), task_id, run_time),
                    )
            return ToolResult(
                True,
                f"One-time task '{task_name}' scheduled for {run_time.isoformat()}",
                {"task_id": str(task_id), "run_at": run_time.isoformat()},
            )
        finally:
            await db.disconnect()
    except ValueError as e:
        return ToolResult(False, f"Invalid datetime format: {e}. Use ISO format: YYYY-MM-DDTHH:MM:SS")
    except Exception as e:
        return ToolResult(False, f"Failed to schedule: {e}")
