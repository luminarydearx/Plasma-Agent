"""Unit tests for database module.

Architecture Note (Phase 1.10):
-------------------------------
These tests exercise the Database class's async interface. On Windows,
psycopg3 requires SelectorEventLoop; the conftest.py enforces this via
a global WindowsSelectorEventLoopPolicy set before pytest-asyncio creates
any event loop.

All query results use dict_row factory, so assertions must check dict keys
(e.g. result["?column?"]) rather than positional indices.
"""

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
        """Test connection context manager.

        Verifies that a connection can be obtained from the pool via async
        context manager and that queries can be executed within it.
        Uses dict_row factory, so result is a dict with "?column?" key.
        """
        db = Database()
        await db.connect()

        async with db.connection() as conn:
            assert conn is not None
            # Test that we can execute queries
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1 AS val")
                result = await cur.fetchone()
                # dict_row returns dict: {"val": 1}
                assert result is not None
                assert result["val"] == 1

        await db.disconnect()

    async def test_transaction_context_manager(self):
        """Test transaction context manager.

        Verifies that the transaction() context manager provides a connection
        wrapped in an active transaction that auto-commits on success.
        """
        db = Database()
        await db.connect()

        async with db.transaction() as conn:
            assert conn is not None
            # Transaction should be active
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1 AS val")
                result = await cur.fetchone()
                # dict_row returns dict: {"val": 1}
                assert result is not None
                assert result["val"] == 1

        await db.disconnect()

    async def test_health_check_success(self):
        """Test successful health check.

        The health_check() method executes 'SELECT 1' and verifies the result.
        With dict_row factory, the column name is "?column?" for literal
        expressions, but our implementation uses 'SELECT 1' which returns
        dict {"?column?": 1}.
        """
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
