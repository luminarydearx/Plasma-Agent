from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from plasmaagent.core.config import get_settings
from plasmaagent.core.exceptions import ConnectionError, DatabaseError


class Database:
    def __init__(self) -> None:
        self._pool: Optional[AsyncConnectionPool] = None
        self._settings = get_settings()

    async def connect(self) -> None:
        if self._pool is not None:
            return

        try:
            conninfo = self._settings.database_url.replace(
                "postgresql+psycopg://", "postgresql://"
            )
            self._pool = AsyncConnectionPool(
                conninfo=conninfo,
                min_size=2,
                max_size=self._settings.database_pool_size,
                timeout=self._settings.database_pool_timeout,
                open=False,
                kwargs={"row_factory": dict_row, "autocommit": False},
            )
            await self._pool.open()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {e}") from e

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[psycopg.AsyncConnection, None]:
        if self._pool is None:
            await self.connect()
        if self._pool is None:
            raise ConnectionError("Database pool not initialized")
        async with self._pool.connection() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[psycopg.AsyncConnection, None]:
        async with self.connection() as conn:
            async with conn.transaction():
                yield conn

    async def health_check(self) -> bool:
        try:
            async with self.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    result = await cur.fetchone()
                    return result is not None and result["?column?"] == 1
        except Exception as e:
            raise DatabaseError(f"Health check failed: {e}") from e


_db: Optional[Database] = None


def get_database() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


async def init_db() -> None:
    db = get_database()
    await db.connect()


async def close_db() -> None:
    db = get_database()
    await db.disconnect()
