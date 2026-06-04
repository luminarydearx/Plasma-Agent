from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4
import secrets
import bcrypt
from plasmaagent.core.database import Database
from plasmaagent.security.models import (
    User,
    UserCreate,
    UserUpdate,
    UserLogin,
    UserSession,
    UserRole,
)


class AuthenticationError(Exception):
    pass


class AuthorizationError(Exception):
    pass


class AuthService:
    def __init__(self, db: Database):
        self.db = db
        self.session_duration_hours = 24

    def _hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def _verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("utf-8")
            )
        except Exception:
            return False

    def _generate_session_token(self) -> str:
        return secrets.token_urlsafe(64)

    async def create_user(self, user_data: UserCreate) -> User:
        async with self.db.connection() as conn:
            existing = await conn.fetchval(
                "SELECT id FROM users WHERE username = $1", user_data.username
            )
            if existing:
                raise ValueError(f"Username '{user_data.username}' already exists")

            if user_data.email:
                existing_email = await conn.fetchval(
                    "SELECT id FROM users WHERE email = $1", user_data.email
                )
                if existing_email:
                    raise ValueError(f"Email '{user_data.email}' already registered")

            user_id = UUID(str(uuid4()))
            password_hash = self._hash_password(user_data.password)
            now = datetime.utcnow()

            await conn.execute(
                """
                INSERT INTO users (id, username, email, password_hash, role, is_active, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                user_id,
                user_data.username,
                user_data.email,
                password_hash,
                user_data.role,
                user_data.is_active,
                now,
                now,
            )

            return User(
                id=user_id,
                username=user_data.username,
                email=user_data.email,
                password_hash=password_hash,
                role=user_data.role,
                is_active=user_data.is_active,
                created_at=now,
                updated_at=now,
            )

    async def authenticate(self, login_data: UserLogin) -> User:
        async with self.db.connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, username, email, password_hash, role, is_active, 
                       created_at, updated_at, last_login
                FROM users WHERE username = $1
                """,
                login_data.username,
            )

            if not row:
                raise AuthenticationError("Invalid username or password")

            if not row["is_active"]:
                raise AuthenticationError("Account is disabled")

            if not self._verify_password(login_data.password, row["password_hash"]):
                raise AuthenticationError("Invalid username or password")

            await conn.execute(
                "UPDATE users SET last_login = $1 WHERE id = $2",
                datetime.utcnow(),
                row["id"],
            )

            return User(**dict(row))

    async def create_session(
        self,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserSession:
        token = self._generate_session_token()
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=self.session_duration_hours)
        session_id = UUID(str(uuid4()))

        async with self.db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO user_sessions (id, user_id, token, created_at, expires_at, 
                                          ip_address, user_agent, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                session_id,
                user_id,
                token,
                now,
                expires_at,
                ip_address,
                user_agent,
                True,
            )

        return UserSession(
            id=session_id,
            user_id=user_id,
            token=token,
            created_at=now,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True,
        )

    async def validate_session(self, token: str) -> Optional[User]:
        async with self.db.connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT s.user_id, s.expires_at, s.is_active,
                       u.username, u.email, u.password_hash, u.role, 
                       u.is_active as user_active, u.created_at, u.updated_at, u.last_login
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = $1
                """,
                token,
            )

            if not row:
                return None

            if not row["is_active"]:
                return None

            if not row["user_active"]:
                return None

            if row["expires_at"] < datetime.utcnow():
                return None

            return User(
                id=row["user_id"],
                username=row["username"],
                email=row["email"],
                password_hash=row["password_hash"],
                role=row["role"],
                is_active=row["user_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_login=row["last_login"],
            )

    async def revoke_session(self, token: str) -> bool:
        async with self.db.connection() as conn:
            result = await conn.execute(
                "UPDATE user_sessions SET is_active = FALSE WHERE token = $1", token
            )
            return result == "UPDATE 1"

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        async with self.db.connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, username, email, password_hash, role, is_active,
                       created_at, updated_at, last_login
                FROM users WHERE id = $1
                """,
                user_id,
            )
            return User(**dict(row)) if row else None

    async def update_user(self, user_id: UUID, update_data: UserUpdate) -> Optional[User]:
        async with self.db.connection() as conn:
            updates = []
            values = []
            param_count = 1

            if update_data.email is not None:
                updates.append(f"email = ${param_count}")
                values.append(update_data.email)
                param_count += 1

            if update_data.role is not None:
                updates.append(f"role = ${param_count}")
                values.append(update_data.role)
                param_count += 1

            if update_data.is_active is not None:
                updates.append(f"is_active = ${param_count}")
                values.append(update_data.is_active)
                param_count += 1

            if not updates:
                return await self.get_user_by_id(user_id)

            updates.append(f"updated_at = ${param_count}")
            values.append(datetime.utcnow())
            param_count += 1

            values.append(user_id)

            query = f"""
                UPDATE users 
                SET {', '.join(updates)}
                WHERE id = ${param_count}
            """

            await conn.execute(query, *values)
            return await self.get_user_by_id(user_id)

    async def change_password(
        self, user_id: UUID, old_password: str, new_password: str
    ) -> bool:
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        if not self._verify_password(old_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")

        new_hash = self._hash_password(new_password)

        async with self.db.connection() as conn:
            await conn.execute(
                "UPDATE users SET password_hash = $1, updated_at = $2 WHERE id = $3",
                new_hash,
                datetime.utcnow(),
                user_id,
            )

            await conn.execute(
                "UPDATE user_sessions SET is_active = FALSE WHERE user_id = $1",
                user_id,
            )

        return True


