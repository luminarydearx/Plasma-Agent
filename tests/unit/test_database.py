"""Unit tests for database module."""

import pytest

from plasmaagent.core.database import Database, get_database
from plasmaagent.core.exceptions import ConnectionError


@pytest.mark.asyncio
class TestDatabase:
    """Test database connection manager."""

    async def test_connect_success(self):
        """Test successful database connection."""
        db = Database()
        await db.connect()
        assert db._pool is not None
        await db.disconnect()

    async def test_disconnect(self):
        """Test database disconnection."""
        db = Database()
        await db.connect()
        assert db._pool is not None
        await db.disconnect()
        assert db._pool is None

    async def test_connection_context_manager(self):
        """Test connection context manager."""
        db = Database()
        await db.connect()

        async with db.connection() as conn:
            assert conn is not None
            # Test that we can execute queries
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                result = await cur.fetchone()
                assert result == [1]

        await db.disconnect()

    async def test_transaction_context_manager(self):
        """Test transaction context manager."""
        db = Database()
        await db.connect()

        async with db.transaction() as conn:
            assert conn is not None
            # Transaction should be active
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                result = await cur.fetchone()
                assert result == [1]

        await db.disconnect()

    async def test_health_check_success(self):
        """Test successful health check."""
        db = Database()
        await db.connect()
        is_healthy = await db.health_check()
        assert is_healthy is True
        await db.disconnect()

    async def test_get_database_singleton(self):
        """Test that get_database returns singleton."""
        db1 = get_database()
        db2 = get_database()
        assert db1 is db2
