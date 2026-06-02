import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from plasmaagent.core.database import Database
from plasmaagent.services.execution_service import ExecutionService
from uuid import uuid4


async def test_empty_commands():
    print("\n[TEST 1] Empty commands list")
    db = Database()
    await db.connect()
    
    service = ExecutionService(db)
    task_id = uuid4()
    
    async with db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO tasks (id, name, status, payload)
                   VALUES (%s, %s, 'PENDING', %s)""",
                (task_id, "Empty Commands Test", {"commands": []}),
            )
    
    try:
        await service.execute_task(task_id)
        print("  FAIL: Should raise ValueError for empty commands")
        return False
    except ValueError as e:
        if "no commands" in str(e).lower():
            print("  PASS: Correctly raised ValueError")
            return True
        else:
            print(f"  FAIL: Wrong error message: {e}")
            return False
    except Exception as e:
        print(f"  FAIL: Wrong exception type: {type(e).__name__}: {e}")
        return False
    finally:
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        await db.disconnect()


async def test_basic_execution():
    print("\n[TEST 2] Basic command execution")
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
                    print("  PASS: Basic execution works")
                    return True
                else:
                    status = row["status"] if row else "NULL"
                    exit_code = row["exit_code"] if row else "NULL"
                    print(f"  FAIL: status={status}, exit_code={exit_code}")
                    return False
    except Exception as e:
        print(f"  FAIL: Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM execution_logs WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM task_steps WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        await db.disconnect()


async def test_failure_handling():
    print("\n[TEST 3] Failure handling")
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
                    print("  PASS: Failure handling works")
                    return True
                else:
                    status = row["status"] if row else "NULL"
                    exit_code = row["exit_code"] if row else "NULL"
                    print(f"  FAIL: status={status}, exit_code={exit_code}")
                    return False
    except Exception as e:
        print(f"  FAIL: Exception: {type(e).__name__}: {e}")
        return False
    finally:
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM execution_logs WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM task_steps WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        await db.disconnect()


async def test_multiline_output():
    print("\n[TEST 4] Multiline output capture")
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
                    print(f"  PASS: Captured {row['cnt']} log lines")
                    return True
                else:
                    print(f"  FAIL: Only captured {row['cnt'] if row else 0} lines")
                    return False
    except Exception as e:
        print(f"  FAIL: Exception: {type(e).__name__}: {e}")
        return False
    finally:
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM execution_logs WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM task_steps WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        await db.disconnect()


async def main():
    print("=" * 70)
    print("PHASE 2 AUTONOMOUS TESTING")
    print("=" * 70)
    
    results = []
    
    results.append(await test_empty_commands())
    results.append(await test_basic_execution())
    results.append(await test_failure_handling())
    results.append(await test_multiline_output())
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\nALL TESTS PASSED")
        return 0
    else:
        print(f"\n{total - passed} TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
