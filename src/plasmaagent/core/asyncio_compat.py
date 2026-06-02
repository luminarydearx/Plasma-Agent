"""Asyncio compatibility utilities for Windows/Unix."""

import asyncio
import selectors
import sys
from typing import Awaitable, TypeVar

T = TypeVar("T")


def run_async(coro: Awaitable[T]) -> T:
    """Run async coroutine with compatible event loop.

    On Windows, psycopg3 requires SelectorEventLoop instead of the default
    ProactorEventLoop. This utility ensures the correct event loop is used.

    Args:
        coro: Coroutine to run

    Returns:
        Result of the coroutine

    Example:
        async def main():
            await db.connect()
            ...

        run_async(main())
    """
    if sys.platform == "win32":
        # Windows: Use SelectorEventLoop for psycopg3 compatibility
        selector = selectors.SelectSelector()
        loop = asyncio.SelectorEventLoop(selector)
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            try:
                # Clean up pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            finally:
                loop.close()
    else:
        # Unix: Use default asyncio.run()
        return asyncio.run(coro)
