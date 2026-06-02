"""Database connection and pool management using psycopg3."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from plasmaagent.core.config import get_settings
from plasmaagent.core.exceptions import ConnectionError, DatabaseError


class Database:
    """Database connection manager."""

    def __init__(self) -> None:
        """Initialize database manager."""
        self._pool: Optional[AsyncConnectionPool] = None
        self._settings = get_settings()

    async def connect(self) -> None:
        """Create connection pool."""
        if self._pool is not None:
            return

        try:
            # Convert URL format for psycopg3 (remove +psycopg if present)
            conninfo = self._settings.database_url.replace(
                "postgresql+psycopg://", "postgresql://"
            )

            self._pool = AsyncConnectionPool(
                conninfo=conninfo,
                min_size=2,
                max_size=self._settings.database_pool_size,
                timeout=self._settings.database_pool_timeout,
                kwargs={"row_factory": dict_row, "autocommit": False},
            )

            # Wait for pool to be ready
            await self._pool.wait()

        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {e}") from e

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[psycopg.AsyncConnection, None]:
        """Get a connection from the pool.

        Yields:
            AsyncConnection: Database connection

        Raises:
            ConnectionError: If pool is not initialized
        """
        if self._pool is None:
            await self.connect()

        if self._pool is None:
            raise ConnectionError("Database pool not initialized")

        async with self._pool.connection() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[psycopg.AsyncConnection, None]:
        """Get a connection with automatic transaction management.

        Yields:
            AsyncConnection: Database connection with transaction

        Example:
            async with db.transaction() as conn:
                await conn.execute("INSERT INTO tasks ...")
                # Transaction commits automatically if no exception
                # Rolls back if exception occurs
        """
        async with self.connection() as conn:
            async with conn.transaction():
                yield conn

    async def health_check(self) -> bool:
        """Check database connectivity.

        Returns:
            bool: True if database is healthy

        Raises:
            DatabaseError: If health check fails
        """
        try:
            async with self.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    result = await cur.fetchone()
                    return result is not None and result[0] == 1
        except Exception as e:
            raise DatabaseError(f"Health check failed: {e}") from e


# Global database instance
_db: Optional[Database] = None


def get_database() -> Database:
    """Get global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db


async def init_db() -> None:
    """Initialize database connection."""
    db = get_database()
    await db.connect()


async def close_db() -> None:
    """Close database connection."""
    db = get_database()
    await db.disconnect()
