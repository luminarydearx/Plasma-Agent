from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from plasmaagent.core.config import get_settings
from plasmaagent.core.exceptions import ConnectionError, DatabaseError


class Database:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self._engine: Optional[AsyncEngine] = None
        self._session_maker: Optional[async_sessionmaker[AsyncSession]] = None
        self._settings = get_settings()
        self._db_path = db_path or self._settings.database_path

    async def connect(self) -> None:
        if self._engine is not None:
            return

        try:
            if self._db_path.startswith("sqlite"):
                db_url = self._db_path
            else:
                db_path = Path(self._db_path).expanduser().resolve()
                db_path.parent.mkdir(parents=True, exist_ok=True)
                db_url = f"sqlite+aiosqlite:///{db_path}"

            self._engine = create_async_engine(
                db_url,
                echo=False,
                future=True,
            )
            self._session_maker = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {e}") from e

    async def disconnect(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_maker = None

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[AsyncConnection, None]:
        if self._engine is None:
            await self.connect()
        if self._engine is None:
            raise ConnectionError("Database engine not initialized")
        async with self._engine.connect() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncConnection, None]:
        async with self.connection() as conn:
            async with conn.begin():
                yield conn

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        if self._session_maker is None:
            await self.connect()
        if self._session_maker is None:
            raise ConnectionError("Session maker not initialized")
        async with self._session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def health_check(self) -> bool:
        try:
            async with self.connection() as conn:
                result = await conn.execute(text("SELECT 1"))
                row = result.fetchone()
                return row is not None and row[0] == 1
        except Exception as e:
            raise DatabaseError(f"Health check failed: {e}") from e

    async def execute(self, sql: str, params: Optional[dict] = None) -> None:
        async with self.transaction() as conn:
            await conn.execute(text(sql), params or {})

    async def fetch_all(self, sql: str, params: Optional[dict] = None) -> list[dict]:
        async with self.connection() as conn:
            result = await conn.execute(text(sql), params or {})
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]

    async def fetch_one(self, sql: str, params: Optional[dict] = None) -> Optional[dict]:
        async with self.connection() as conn:
            result = await conn.execute(text(sql), params or {})
            row = result.fetchone()
            return dict(row._mapping) if row else None


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
