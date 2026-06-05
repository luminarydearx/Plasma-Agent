import asyncio
from sqlalchemy import text
from plasmaagent.core.database import get_database
from plasmaagent.core.schema import init_schema


async def test():
    db = get_database()
    await db.connect()
    
    async with db.connection() as conn:
        await init_schema(conn)
    
    health = await db.health_check()
    print(f"✅ Database initialized: {health}")
    
    async with db.connection() as conn:
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [row[0] for row in result.fetchall()]
        print(f"✅ Tables created: {len(tables)}")
        for table in sorted(tables):
            print(f"  - {table}")
    
    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(test())
