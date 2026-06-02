"""Pytest fixtures for tests."""

import pytest
import pytest_asyncio

from plasmaagent.core.config import get_settings
from plasmaagent.core.database import Database, get_database


@pytest.fixture(scope="session")
def settings():
    """Get application settings."""
    return get_settings()


@pytest_asyncio.fixture(scope="session")
async def database():
    """Get database instance."""
    db = get_database()
    await db.connect()
    yield db
    await db.disconnect()


@pytest_asyncio.fixture
async def db_connection(database: Database):
    """Get a database connection for testing."""
    async with database.connection() as conn:
        yield conn


@pytest_asyncio.fixture
async def db_transaction(database: Database):
    """Get a database transaction for testing (auto-rollback)."""
    async with database.connection() as conn:
        async with conn.transaction() as trans:
            yield conn
            # Rollback after test
            await trans.rollback()
