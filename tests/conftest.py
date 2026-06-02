"""Pytest configuration and shared fixtures.

Architecture Note (Phase 1.10 - Database Async Stability Fix):
===============================================================
psycopg3 async backend requires SelectorEventLoop on Windows, but Python 3.13
on Windows defaults to ProactorEventLoop. pytest-asyncio 1.4.0 uses the
`pytest_asyncio_loop_factories` hook to determine which event loop factory
to use when creating event loops for tests and fixtures.

Root Cause Analysis:
-------------------
1. pytest-asyncio 1.4.0 uses the `pytest_asyncio_loop_factories` hook to
   create event loops for tests and fixtures.
2. Setting WindowsSelectorEventLoopPolicy at module import time is NOT enough
   because pytest-asyncio creates NEW event loops for each test/fixture using
   the factory returned by the hook.
3. The `event_loop` fixture (which we previously tried to override) is NOT
   used by pytest-asyncio 1.4.0 when `asyncio_default_test_loop_scope` is set.
4. The `event_loop_policy` fixture is deprecated in 1.4.0.

Fix Strategy (Architecture-Level):
----------------------------------
1. Implement `pytest_asyncio_loop_factories` hook to return a factory that
   creates SelectorEventLoop on Windows.
2. This makes pytest-asyncio create ALL event loops using this factory.
3. This ensures every test, fixture, and async operation uses SelectorEventLoop
   (required by psycopg3 async).
4. The same policy is used by the CLI's run_async() in asyncio_compat.py,
   ensuring CLI and pytest share identical event loop semantics.

References:
- pytest-asyncio docs: https://pytest-asyncio.readthedocs.io/en/v1.4.0/how-to-guides/custom_loop_factory.html
- psycopg async docs: https://www.psycopg.org/psycopg3/docs/advanced/async.html
"""

import asyncio
import sys
import selectors

import pytest
import pytest_asyncio

from plasmaagent.core.config import get_settings
from plasmaagent.core.database import Database, get_database


# ============================================================
# ARCHITECTURE-LEVEL FIX: Custom event loop factory
# 
# pytest-asyncio 1.4.0 uses this hook to determine which event
# loop factory to use when creating event loops for tests and fixtures.
# On Windows, we MUST return a factory that creates SelectorEventLoop
# because psycopg3 async is NOT compatible with ProactorEventLoop.
#
# This is the CORRECT fix for pytest-asyncio 1.4.0, not overriding
# the event_loop fixture (which is not used) or event_loop_policy
# fixture (which is deprecated).
# ============================================================
def _create_selector_event_loop():
    """Create a SelectorEventLoop (required by psycopg3 on Windows)."""
    selector = selectors.SelectSelector()
    return asyncio.SelectorEventLoop(selector)


def pytest_asyncio_loop_factories(config, item):
    """Return event loop factories for pytest-asyncio.
    
    On Windows, returns a factory that creates SelectorEventLoop because
    psycopg3 async is not compatible with ProactorEventLoop (the Windows default).
    
    On other platforms, returns a factory that creates the default event loop.
    
    This hook is called by pytest-asyncio for EVERY event loop it creates
    (for tests, fixtures, etc.), ensuring consistent SelectorEventLoop usage
    on Windows throughout the test suite.
    
    Args:
        config: The pytest config object.
        item: The pytest item (test, fixture, etc.).
    
    Returns:
        A mapping from factory names to factory callables.
    """
    if sys.platform == "win32":
        return {
            "psycopg_compatible": _create_selector_event_loop,
        }
    return {
        "default": asyncio.new_event_loop,
    }


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
