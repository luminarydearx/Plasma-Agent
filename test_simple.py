import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from plasmaagent.core.asyncio_compat import run_async
from plasmaagent.core.database import Database
from plasmaagent.services.execution_service import ExecutionService
from uuid import uuid4


async def test_simple():
    print("[TEST] Simple execution test", flush=True)
    
    db = Database()
    print("  Connecting to database...", flush=True)
    await db.connect()
    print("  Connected", flush=True)
    
    service = ExecutionService(db)
    task_id = uuid4()
    print(f"  Task ID: {task_id}", flush=True)
    
    print("  Inserting task...", flush=True)
    async with db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO tasks (id, name, status, payload)
                   VALUES (%s, %s, 'PENDING', %s)""",
                (task_id, "Simple Test", {"commands": ["echo hello"]}),
            )
    print("  Task inserted", flush=True)
    
    print("  Executing task...", flush=True)
    task = await service.execute_task(task_id)
    print(f"  Task status: {task.status}", flush=True)
    
    print("  Checking step...", flush=True)
    async with db.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT status, exit_code FROM task_steps WHERE task_id = %s",
                (task_id,)
            )
            row = await cur.fetchone()
            if row:
                print(f"  Step: status={row['status']}, exit_code={row['exit_code']}", flush=True)
            else:
                print("  Step: NOT FOUND", flush=True)
    
    print("  Cleanup...", flush=True)
    async with db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM execution_logs WHERE task_id = %s", (task_id,))
            await cur.execute("DELETE FROM task_steps WHERE task_id = %s", (task_id,))
            await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    
    print("  Disconnecting...", flush=True)
    await db.disconnect()
    print("  Done", flush=True)
    
    return 0


if __name__ == "__main__":
    exit_code = run_async(test_simple())
    sys.exit(exit_code)
