from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from plasmaagent.core.schema import ConversationSession, ConversationMessage


class ConversationNotFoundError(Exception):
    def __init__(self, session_id: UUID):
        super().__init__(f"Conversation session {session_id} not found")
        self.session_id = session_id


class ConversationService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_session(self, user_id: UUID, title: str | None = None) -> ConversationSession:
        session_id = uuid4()
        now = datetime.now(timezone.utc)

        conv_session = ConversationSession(
            id=session_id,
            user_id=user_id,
            title=title,
            message_count=0,
            created_at=now,
            updated_at=now
        )
        self._session.add(conv_session)
        await self._session.commit()

        return conv_session

    async def get_session(self, session_id: UUID) -> ConversationSession:
        stmt = select(ConversationSession).where(ConversationSession.id == session_id)
        result = await self._session.execute(stmt)
        conv_session = result.scalar_one_or_none()

        if not conv_session:
            raise ConversationNotFoundError(session_id)

        return conv_session

    async def list_sessions(self, user_id: UUID, limit: int = 50) -> list[ConversationSession]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")

        stmt = (
            select(ConversationSession)
            .where(ConversationSession.user_id == user_id)
            .order_by(ConversationSession.updated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_session(self, session_id: UUID) -> None:
        stmt = delete(ConversationSession).where(ConversationSession.id == session_id)
        result = await self._session.execute(stmt)
        await self._session.commit()
        
        if result.rowcount == 0:
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

        message = ConversationMessage(
            id=message_id,
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
            created_at=now
        )
        self._session.add(message)

        stmt = select(ConversationSession).where(ConversationSession.id == session_id)
        result = await self._session.execute(stmt)
        conv_session = result.scalar_one_or_none()
        
        if conv_session:
            conv_session.message_count += 1
            conv_session.updated_at = now

        await self._session.commit()
        return message

    async def get_messages(self, session_id: UUID, limit: int = 100) -> list[ConversationMessage]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")

        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_context(self, session_id: UUID, max_messages: int = 10) -> list[ConversationMessage]:
        if max_messages < 1 or max_messages > 100:
            raise ValueError("max_messages must be between 1 and 100")

        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(max_messages)
        )
        result = await self._session.execute(stmt)
        messages = list(result.scalars().all())

        return list(reversed(messages))
