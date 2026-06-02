import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from plasmaagent.core.database import Database
from plasmaagent.services.execution_service import ExecutionService
from plasmaagent.models.task import TaskPayload
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
        print("  ✗ FAIL: Should raise ValueError for empty commands")
        return False
    except ValueError as e:
        if "no commands" in str(e).lower():
            print("  ✓ PASS: Correctly raised ValueError")
            return True
        else:
            print(f"  ✗ FAIL: Wrong error message: {e}")
            return False
    except Exception as e:
        print(f"  ✗ FAIL: Wrong exception type: {type(e).__name__}: {e}")
        return False
    finally:
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        await db.disconnect()


async def test_timeout():
    print("\n[TEST 2] Command timeout")
    db = Database()
    await db.connect()
    
    service = ExecutionService(db)
    task_id = uuid4()
    
    async with db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO tasks (id, name, status, payload)
                   VALUES (%s, %s, 'PENDING', %s)""",
                (task_id, "Timeout Test", {"commands": ["timeout /t 10 /nobreak"], "timeout": 2}),
            )
    
    try:
        start = time.time()
        task = await service.execute_task(task_id)
        duration = time.time() - start
        
        if duration < 5:
            print(f"  ✓ PASS: Timeout triggered in {duration:.1f}s")
            
            async with db.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT status FROM task_steps WHERE task_id = %s",
                        (task_id,)
                    )
                    row = await cur.fetchone()
                    if row and row["status"] == "FAILED":
                        print("  ✓ PASS: Step marked as FAILED")
                        return True
                    else:
                        print(f"  ✗ FAIL: Step status is {row['status'] if row else 'NULL'}")
                        return False
        else:
            print(f"  ✗ FAIL: Timeout did not trigger (took {duration:.1f}s)")
            return False
    except Exception as e:
        print(f"  ✗ FAIL: Exception: {type(e).__name__}: {e}")
        return False
    finally:
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM execution_logs WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM task_steps WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        await db.disconnect()


async def test_stderr_capture():
    print("\n[TEST 3] Stderr capture")
    db = Database()
    await db.connect()
    
    service = ExecutionService(db)
    task_id = uuid4()
    
    async with db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO tasks (id, name, status, payload)
                   VALUES (%s, %s, 'PENDING', %s)""",
                (task_id, "Stderr Test", {"commands": ["echo error message >&2"]}),
            )
    
    try:
        task = await service.execute_task(task_id)
        
        async with db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT stderr FROM task_steps WHERE task_id = %s",
                    (task_id,)
                )
                row = await cur.fetchone()
                if row and row["stderr"] and "error message" in row["stderr"]:
                    print("  ✓ PASS: Stderr captured correctly")
                    return True
                else:
                    print(f"  ✗ FAIL: Stderr not captured: {row['stderr'] if row else 'NULL'}")
                    return False
    except Exception as e:
        print(f"  ✗ FAIL: Exception: {type(e).__name__}: {e}")
        return False
    finally:
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM execution_logs WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM task_steps WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        await db.disconnect()


async def test_special_characters():
    print("\n[TEST 4] Special characters in commands")
    db = Database()
    await db.connect()
    
    service = ExecutionService(db)
    task_id = uuid4()
    
    commands = [
        'echo "Hello & World"',
        "echo 'Test | Pipe'",
        "echo $env:USERPROFILE",
    ]
    
    async with db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO tasks (id, name, status, payload)
                   VALUES (%s, %s, 'PENDING', %s)""",
                (task_id, "Special Chars Test", {"commands": commands}),
            )
    
    try:
        task = await service.execute_task(task_id)
        
        async with db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT COUNT(*) as cnt FROM task_steps WHERE task_id = %s AND status = 'COMPLETED'",
                    (task_id,)
                )
                row = await cur.fetchone()
                if row and row["cnt"] == 3:
                    print("  ✓ PASS: All special character commands succeeded")
                    return True
                else:
                    print(f"  ✗ FAIL: Only {row['cnt'] if row else 0}/3 commands succeeded")
                    return False
    except Exception as e:
        print(f"  ✗ FAIL: Exception: {type(e).__name__}: {e}")
        return False
    finally:
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM execution_logs WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM task_steps WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        await db.disconnect()


async def test_concurrent_execution():
    print("\n[TEST 5] Concurrent task execution")
    db = Database()
    await db.connect()
    
    service = ExecutionService(db)
    task_ids = [uuid4() for _ in range(3)]
    
    for i, task_id in enumerate(task_ids):
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """INSERT INTO tasks (id, name, status, payload)
                       VALUES (%s, %s, 'PENDING', %s)""",
                    (task_id, f"Concurrent Test {i}", {"commands": ["timeout /t 1 /nobreak"]}),
                )
    
    try:
        tasks = await asyncio.gather(*[
            service.execute_task(tid) for tid in task_ids
        ])
        
        async with db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT status FROM tasks WHERE id = ANY(%s)",
                    (task_ids,)
                )
                rows = await cur.fetchall()
                
                completed = sum(1 for row in rows if row["status"] == "COMPLETED")
                if completed == 3:
                    print("  ✓ PASS: All concurrent tasks completed")
                    return True
                else:
                    print(f"  ✗ FAIL: Only {completed}/3 tasks completed")
                    return False
    except Exception as e:
        print(f"  ✗ FAIL: Exception: {type(e).__name__}: {e}")
        return False
    finally:
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM execution_logs WHERE task_id = ANY(%s)", (task_ids,))
                await cur.execute("DELETE FROM task_steps WHERE task_id = ANY(%s)", (task_ids,))
                await cur.execute("DELETE FROM tasks WHERE id = ANY(%s)", (task_ids,))
        await db.disconnect()


async def test_large_output():
    print("\n[TEST 6] Large output handling")
    db = Database()
    await db.connect()
    
    service = ExecutionService(db)
    task_id = uuid4()
    
    large_command = "for /L %i in (1,1,1000) do @echo Line %i"
    
    async with db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO tasks (id, name, status, payload)
                   VALUES (%s, %s, 'PENDING', %s)""",
                (task_id, "Large Output Test", {"commands": [large_command]}),
            )
    
    try:
        task = await service.execute_task(task_id)
        
        async with db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT COUNT(*) as cnt FROM execution_logs WHERE task_id = %s",
                    (task_id,)
                )
                row = await cur.fetchone()
                if row and row["cnt"] >= 1000:
                    print(f"  ✓ PASS: Captured {row['cnt']} log lines")
                    return True
                else:
                    print(f"  ✗ FAIL: Only captured {row['cnt'] if row else 0} lines")
                    return False
    except Exception as e:
        print(f"  ✗ FAIL: Exception: {type(e).__name__}: {e}")
        return False
    finally:
        async with db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM execution_logs WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM task_steps WHERE task_id = %s", (task_id,))
                await cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        await db.disconnect()


async def test_invalid_command():
    print("\n[TEST 7] Invalid command handling")
    db = Database()
    await db.connect()
    
    service = ExecutionService(db)
    task_id = uuid4()
    
    async with db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO tasks (id, name, status, payload)
                   VALUES (%s, %s, 'PENDING', %s)""",
                (task_id, "Invalid Command Test", {"commands": ["nonexistent_command_12345"]}),
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
                if row and row["status"] == "FAILED" and row["exit_code"] != 0:
                    print("  ✓ PASS: Invalid command marked as FAILED")
                    return True
                else:
                    print(f"  ✗ FAIL: Status={row['status'] if row else 'NULL'}, exit_code={row['exit_code'] if row else 'NULL'}")
                    return False
    except Exception as e:
        print(f"  ✗ FAIL: Exception: {type(e).__name__}: {e}")
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
    print("PHASE 2 COMPREHENSIVE AUTONOMOUS TESTING")
    print("=" * 70)
    
    tests = [
        test_empty_commands,
        test_timeout,
        test_stderr_capture,
        test_special_characters,
        test_concurrent_execution,
        test_large_output,
        test_invalid_command,
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"  ✗ FAIL: Unexpected exception: {type(e).__name__}: {e}")
            results.append(False)
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED - Phase 2 is stable")
        return 0
    else:
        print(f"\n✗ {total - passed} TESTS FAILED - Phase 2 needs fixes")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
