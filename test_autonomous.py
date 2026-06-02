import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from plasmaagent.core.asyncio_compat import run_async
from plasmaagent.core.database import Database
from plasmaagent.services.execution_service import ExecutionService
from uuid import uuid4


def log(msg: str) -> None:
    print(msg, flush=True)


async def test_empty_commands():
    log("\n[TEST 1] Empty commands list")
    db = Database()
    await db.connect()
    log("  Database connected")
    
    service = ExecutionService(db)
    task_id = uuid4()
    log(f"  Task ID: {task_id}")
    
    async with db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO tasks (id, name, status, payload)
                   VALUES (%s, %s, 'PENDING', %s)""",
                (task_id, "Empty Commands Test", {"commands": []}),
            )
    log("  Task inserted")
    
    try:
        log("  Calling execute_task...")
        await service.execute_task(task_id)
        log("  FAIL: Should raise ValueError for empty commands")
        return False
    except ValueError as e:
        log(f"  Caught ValueError: {e}")
        if "no commands" in str(e).lower():
            log("  PASS: Correctly raised ValueError")
            return True
        else:
            log(f"  FAIL: Wrong error message: {e}")
            return False
    except Exception as e:
        log(f"  FAIL: Wrong exception type: {type(e).__name__}: {e}")
        import traceback
        log(traceback.format_exc())
        return False
    finally:
        log("  Cleanup...")
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        await db.disconnect()
        log("  Cleanup done")


async def test_basic_execution():
    log("\n[TEST 2] Basic command execution")
    db = Database()
    await db.connect()
    
    service = ExecutionService(db)
    task_id = uuid4()
    
    async with db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO tasks (id, name, status, payload)
                   VALUES (%s, %s, 'PENDING', %s)""",
                (task_id, "Basic Test", {"commands": ["echo hello"]}),
            )
    
    try:
        task = await service.execute_task(task_id)
        
        async with db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT status, exit_code FROM task_steps WHERE task_id = %s",
                    (task_id,)
                )
                row = await cur.fetchone()
                
                if row and row["status"] == "COMPLETED" and row["exit_code"] == 0:
                    log("  PASS: Basic execution works")
                    return True
                else:
                    status = row["status"] if row else "NULL"
                    exit_code = row["exit_code"] if row else "NULL"
                    log(f"  FAIL: status={status}, exit_code={exit_code}")
                    return False
    except Exception as e:
        log(f"  FAIL: Exception: {type(e).__name__}: {e}")
        import traceback
        log(traceback.format_exc())
        return False
    finally:
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM execution_logs WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM task_steps WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        await db.disconnect()


async def test_failure_handling():
    log("\n[TEST 3] Failure handling")
    db = Database()
    await db.connect()
    
    service = ExecutionService(db)
    task_id = uuid4()
    
    async with db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO tasks (id, name, status, payload)
                   VALUES (%s, %s, 'PENDING', %s)""",
                (task_id, "Failure Test", {"commands": ["exit 1"]}),
            )
    
    try:
        task = await service.execute_task(task_id)
        
        async with db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT status, exit_code FROM task_steps WHERE task_id = %s",
                    (task_id,)
                )
                row = await cur.fetchone()
                
                if row and row["status"] == "FAILED" and row["exit_code"] == 1:
                    log("  PASS: Failure handling works")
                    return True
                else:
                    status = row["status"] if row else "NULL"
                    exit_code = row["exit_code"] if row else "NULL"
                    log(f"  FAIL: status={status}, exit_code={exit_code}")
                    return False
    except Exception as e:
        log(f"  FAIL: Exception: {type(e).__name__}: {e}")
        return False
    finally:
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM execution_logs WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM task_steps WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        await db.disconnect()


async def test_multiline_output():
    log("\n[TEST 4] Multiline output capture")
    db = Database()
    await db.connect()
    
    service = ExecutionService(db)
    task_id = uuid4()
    
    async with db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO tasks (id, name, status, payload)
                   VALUES (%s, %s, 'PENDING', %s)""",
                (task_id, "Multiline Test", {"commands": ["echo line1 && echo line2 && echo line3"]}),
            )
    
    try:
        task = await service.execute_task(task_id)
        
        async with db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT COUNT(*) as cnt FROM execution_logs WHERE task_id = %s AND log_level = 'STDOUT'",
                    (task_id,)
                )
                row = await cur.fetchone()
                
                if row and row["cnt"] >= 3:
                    log(f"  PASS: Captured {row['cnt']} log lines")
                    return True
                else:
                    log(f"  FAIL: Only captured {row['cnt'] if row else 0} lines")
                    return False
    except Exception as e:
        log(f"  FAIL: Exception: {type(e).__name__}: {e}")
        return False
    finally:
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM execution_logs WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM task_steps WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        await db.disconnect()


async def main():
    log("=" * 70)
    log("PHASE 2 AUTONOMOUS TESTING")
    log("=" * 70)
    
    results = []
    
    log("\nStarting TEST 1...")
    results.append(await test_empty_commands())
    
    log("\nStarting TEST 2...")
    results.append(await test_basic_execution())
    
    log("\nStarting TEST 3...")
    results.append(await test_failure_handling())
    
    log("\nStarting TEST 4...")
    results.append(await test_multiline_output())
    
    log("\n" + "=" * 70)
    log("SUMMARY")
    log("=" * 70)
    passed = sum(results)
    total = len(results)
    log(f"Passed: {passed}/{total}")
    
    if passed == total:
        log("\nALL TESTS PASSED")
        return 0
    else:
        log(f"\n{total - passed} TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = run_async(main())
    sys.exit(exit_code)
