import asyncio
import sys

if sys.platform == "win32":
    import selectors
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from plasmaagent.core.database import Database


async def verify_migration():
    db = Database()
    await db.connect()
    
    try:
        async with db.connection() as conn:
            async with conn.cursor() as cursor:
                print("=== Checking template_metrics table ===")
                
                await cursor.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'template_metrics'
                    ORDER BY ordinal_position
                """)
                
                rows = await cursor.fetchall()
                
                if not rows:
                    print("Table template_metrics NOT FOUND")
                    return False
                
                print(f"Table found with {len(rows)} columns:")
                print(f"{'Column':<30} {'Type':<25} {'Nullable':<10} {'Default'}")
                print("-" * 100)
                
                for row in rows:
                    col_name = row["column_name"]
                    data_type = row["data_type"]
                    nullable = row["is_nullable"]
                    default = row["column_default"] or "NULL"
                    print(f"{col_name:<30} {data_type:<25} {nullable:<10} {default}")
                
                print("\n=== Checking indexes ===")
                await cursor.execute("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = 'template_metrics'
                """)
                
                indexes = await cursor.fetchall()
                print(f"Found {len(indexes)} indexes:")
                for row in indexes:
                    print(f"  - {row['indexname']}")
                
                print("\n=== Testing insert/read operations ===")
                test_id = "11111111-1111-1111-1111-111111111111"
                
                await cursor.execute("""
                    INSERT INTO template_metrics 
                    (id, template_name, pattern, usage_count, success_count, failure_count, avg_confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (test_id, "test_template", "test pattern", 5, 3, 2, 0.85))
                
                await cursor.execute("""
                    SELECT template_name, usage_count, success_count, failure_count, avg_confidence
                    FROM template_metrics WHERE id = %s
                """, (test_id,))
                
                result = await cursor.fetchone()
                if result:
                    print(f"Insert/Select working:")
                    print(f"   template_name: {result['template_name']}")
                    print(f"   usage_count: {result['usage_count']}")
                    print(f"   success_count: {result['success_count']}")
                    print(f"   failure_count: {result['failure_count']}")
                    print(f"   avg_confidence: {result['avg_confidence']}")
                    
                    await cursor.execute("DELETE FROM template_metrics WHERE id = %s", (test_id,))
                    print("Cleanup: test record deleted")
                else:
                    print("Insert failed")
                    return False
                
                await conn.commit()
                
                print("\nMigration 003 verification: ALL PASSED")
                return True
    
    finally:
        await db.disconnect()


if __name__ == "__main__":
    result = asyncio.run(verify_migration())
    sys.exit(0 if result else 1)
