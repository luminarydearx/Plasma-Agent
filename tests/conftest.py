"""Pytest configuration and shared fixtures.

Architecture Note (Phase 1.10 - Database Async Stability Fix):
===============================================================
psycopg3 async backend requires SelectorEventLoop on Windows, but Python 3.13
on Windows defaults to ProactorEventLoop. pytest-asyncio creates its own event
loops using the current global policy, so we MUST set the policy BEFORE
pytest-asyncio is imported and BEFORE any event loop is created.

This conftest.py is loaded by pytest before test collection, making it the
correct place to enforce the policy at the architecture level — not a
per-test patch.

Fix Strategy:
  1. Set WindowsSelectorEventLoopPolicy globally at import time of conftest.py
     (before pytest-asyncio loads and creates any event loops).
  2. The same policy is used by the CLI's run_async() in asyncio_compat.py,
     ensuring CLI and pytest share identical event loop semantics.
"""

import asyncio
import sys

# ============================================================
# ARCHITECTURE-LEVEL FIX: Set event loop policy BEFORE any
# asyncio import happens in test modules. This ensures all
# event loops created by pytest-asyncio use SelectorEventLoop
# on Windows (required by psycopg3 async).
#
# IMPORTANT: This must be the FIRST thing in this file, before
# any pytest/pytest-asyncio imports.
# ============================================================
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


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
    """Get database instance (session-scoped, shared across all tests)."""
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
