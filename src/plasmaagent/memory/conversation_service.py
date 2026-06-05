import psycopg
from uuid import UUID, uuid4
from datetime import datetime, timezone
from plasmaagent.memory.models import ConversationSession, ConversationMessage


class ConversationNotFoundError(Exception):
    def __init__(self, session_id: UUID):
        super().__init__(f"Conversation session {session_id} not found")
        self.session_id = session_id


class ConversationService:
    def __init__(self, conn: psycopg.AsyncConnection):
        self._conn = conn

    async def create_session(self, user_id: UUID, title: str | None = None) -> ConversationSession:
        session_id = uuid4()
        now = datetime.now(timezone.utc)

        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO conversation_sessions (id, user_id, title, message_count, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (session_id, user_id, title, 0, now, now)
            )

        return ConversationSession(
            id=session_id,
            user_id=user_id,
            title=title,
            message_count=0,
            created_at=now,
            updated_at=now
        )

    async def get_session(self, session_id: UUID) -> ConversationSession:
        async with self._conn.cursor() as cur:
            await cur.execute(
                "SELECT id, user_id, title, message_count, created_at, updated_at FROM conversation_sessions WHERE id = %s",
                (session_id,)
            )
            row = await cur.fetchone()

        if not row:
            raise ConversationNotFoundError(session_id)

        return ConversationSession(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            message_count=row["message_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    async def list_sessions(self, user_id: UUID, limit: int = 50) -> list[ConversationSession]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")

        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, user_id, title, message_count, created_at, updated_at
                FROM conversation_sessions
                WHERE user_id = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (user_id, limit)
            )
            rows = await cur.fetchall()

        return [
            ConversationSession(
                id=row["id"],
                user_id=row["user_id"],
                title=row["title"],
                message_count=row["message_count"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
            for row in rows
        ]

    async def delete_session(self, session_id: UUID) -> None:
        async with self._conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM conversation_sessions WHERE id = %s",
                (session_id,)
            )
            if cur.rowcount == 0:
                raise ConversationNotFoundError(session_id)

    async def add_message(
        self,
        session_id: UUID,
        user_id: UUID,
        role: str,
        content: str
    ) -> ConversationMessage:
        message_id = uuid4()
        now = datetime.now(timezone.utc)

        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO conversation_messages (id, session_id, user_id, role, content, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (message_id, session_id, user_id, role, content, now)
            )

            await cur.execute(
                """
                UPDATE conversation_sessions
                SET message_count = message_count + 1, updated_at = %s
                WHERE id = %s
                """,
                (now, session_id)
            )

        return ConversationMessage(
            id=message_id,
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            created_at=now
        )

    async def get_messages(self, session_id: UUID, limit: int = 100) -> list[ConversationMessage]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")

        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, user_id, session_id, role, content, created_at
                FROM conversation_messages
                WHERE session_id = %s
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (session_id, limit)
            )
            rows = await cur.fetchall()

        return [
            ConversationMessage(
                id=row["id"],
                user_id=row["user_id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"]
            )
            for row in rows
        ]

    async def get_context(self, session_id: UUID, max_messages: int = 10) -> list[ConversationMessage]:
        if max_messages < 1 or max_messages > 100:
            raise ValueError("max_messages must be between 1 and 100")

        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, user_id, session_id, role, content, created_at
                FROM conversation_messages
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (session_id, max_messages)
            )
            rows = await cur.fetchall()

        messages = [
            ConversationMessage(
                id=row["id"],
                user_id=row["user_id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"]
            )
            for row in rows
        ]

        return list(reversed(messages))
