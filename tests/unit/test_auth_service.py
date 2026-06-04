import pytest
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from plasmaagent.security.auth_service import AuthService, AuthenticationError
from plasmaagent.security.models import UserCreate, UserLogin, UserRole


def make_mock_db():
    conn = AsyncMock()
    db = MagicMock()

    @asynccontextmanager
    async def connection_cm():
        yield conn

    db.connection = MagicMock(side_effect=lambda: connection_cm())
    return db, conn


class TestAuthService:
    def test_hash_password(self):
        db, _ = make_mock_db()
        svc = AuthService(db)
        password = "SecurePass123!"
        hashed = svc._hash_password(password)
        assert hashed != password
        assert len(hashed) > 20
        assert hashed.startswith("$2")

    def test_verify_password_correct(self):
        db, _ = make_mock_db()
        svc = AuthService(db)
        hashed = svc._hash_password("SecurePass123!")
        assert svc._verify_password("SecurePass123!", hashed) is True

    def test_verify_password_wrong(self):
        db, _ = make_mock_db()
        svc = AuthService(db)
        hashed = svc._hash_password("SecurePass123!")
        assert svc._verify_password("WrongPass", hashed) is False

    def test_verify_password_invalid_hash(self):
        db, _ = make_mock_db()
        svc = AuthService(db)
        assert svc._verify_password("any", "not-a-hash") is False

    def test_generate_session_token(self):
        db, _ = make_mock_db()
        svc = AuthService(db)
        tokens = {svc._generate_session_token() for _ in range(100)}
        assert len(tokens) == 100
        assert all(len(t) > 50 for t in tokens)

    @pytest.mark.asyncio
    async def test_create_user_success(self):
        db, conn = make_mock_db()
        conn.fetchval = AsyncMock(side_effect=[None, None])
        conn.execute = AsyncMock()
        svc = AuthService(db)

        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
            role=UserRole.USER,
        )
        user = await svc.create_user(user_data)

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == UserRole.USER
        assert user.is_active is True
        assert user.password_hash != "SecurePass123!"
        assert conn.execute.await_count == 1

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self):
        db, conn = make_mock_db()
        existing_id = uuid4()
        conn.fetchval = AsyncMock(return_value=existing_id)
        svc = AuthService(db)

        user_data = UserCreate(username="existing", password="SecurePass123!")
        with pytest.raises(ValueError, match="already exists"):
            await svc.create_user(user_data)

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self):
        db, conn = make_mock_db()
        conn.fetchval = AsyncMock(side_effect=[None, uuid4()])
        svc = AuthService(db)

        user_data = UserCreate(
            username="new",
            email="dup@example.com",
            password="SecurePass123!",
        )
        with pytest.raises(ValueError, match="already registered"):
            await svc.create_user(user_data)

    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        db, conn = make_mock_db()
        svc = AuthService(db)
        user_id = uuid4()
        password = "CorrectPass123!"
        password_hash = svc._hash_password(password)

        conn.fetchrow = AsyncMock(
            return_value={
                "id": user_id,
                "username": "testuser",
                "email": "test@example.com",
                "password_hash": password_hash,
                "role": UserRole.USER,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
            }
        )
        conn.execute = AsyncMock()

        login_data = UserLogin(username="testuser", password=password)
        user = await svc.authenticate(login_data)

        assert user.username == "testuser"
        assert user.id == user_id
        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self):
        db, conn = make_mock_db()
        conn.fetchrow = AsyncMock(return_value=None)
        svc = AuthService(db)

        login_data = UserLogin(username="nobody", password="whatever")
        with pytest.raises(AuthenticationError, match="Invalid"):
            await svc.authenticate(login_data)

    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self):
        db, conn = make_mock_db()
        svc = AuthService(db)
        password_hash = svc._hash_password("CorrectPass123!")

        conn.fetchrow = AsyncMock(
            return_value={
                "id": uuid4(),
                "username": "testuser",
                "email": None,
                "password_hash": password_hash,
                "role": UserRole.USER,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
            }
        )

        login_data = UserLogin(username="testuser", password="WrongPassword123!")
        with pytest.raises(AuthenticationError, match="Invalid"):
            await svc.authenticate(login_data)

    @pytest.mark.asyncio
    async def test_authenticate_disabled_account(self):
        db, conn = make_mock_db()
        svc = AuthService(db)
        password_hash = svc._hash_password("SecurePass123!")

        conn.fetchrow = AsyncMock(
            return_value={
                "id": uuid4(),
                "username": "testuser",
                "email": None,
                "password_hash": password_hash,
                "role": UserRole.USER,
                "is_active": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
            }
        )

        login_data = UserLogin(username="testuser", password="SecurePass123!")
        with pytest.raises(AuthenticationError, match="disabled"):
            await svc.authenticate(login_data)

    @pytest.mark.asyncio
    async def test_create_session(self):
        db, conn = make_mock_db()
        conn.execute = AsyncMock()
        svc = AuthService(db)
        user_id = uuid4()

        session = await svc.create_session(
            user_id=user_id,
            ip_address="127.0.0.1",
            user_agent="TestAgent",
        )

        assert session.user_id == user_id
        assert session.ip_address == "127.0.0.1"
        assert session.user_agent == "TestAgent"
        assert session.is_active is True
        assert session.expires_at > datetime.utcnow()
        assert len(session.token) > 50

    @pytest.mark.asyncio
    async def test_validate_session_success(self):
        db, conn = make_mock_db()
        svc = AuthService(db)
        user_id = uuid4()

        conn.fetchrow = AsyncMock(
            return_value={
                "user_id": user_id,
                "expires_at": datetime.utcnow() + timedelta(hours=1),
                "is_active": True,
                "username": "testuser",
                "email": None,
                "password_hash": "hash",
                "role": UserRole.USER,
                "user_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
            }
        )

        user = await svc.validate_session("valid_token")
        assert user is not None
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_validate_session_expired(self):
        db, conn = make_mock_db()
        conn.fetchrow = AsyncMock(
            return_value={
                "user_id": uuid4(),
                "expires_at": datetime.utcnow() - timedelta(hours=1),
                "is_active": True,
                "username": "testuser",
                "email": None,
                "password_hash": "hash",
                "role": UserRole.USER,
                "user_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
            }
        )
        svc = AuthService(db)
        assert await svc.validate_session("expired") is None

    @pytest.mark.asyncio
    async def test_validate_session_inactive(self):
        db, conn = make_mock_db()
        conn.fetchrow = AsyncMock(
            return_value={
                "user_id": uuid4(),
                "expires_at": datetime.utcnow() + timedelta(hours=1),
                "is_active": False,
                "username": "testuser",
                "email": None,
                "password_hash": "hash",
                "role": UserRole.USER,
                "user_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
            }
        )
        svc = AuthService(db)
        assert await svc.validate_session("inactive") is None

    @pytest.mark.asyncio
    async def test_validate_session_not_found(self):
        db, conn = make_mock_db()
        conn.fetchrow = AsyncMock(return_value=None)
        svc = AuthService(db)
        assert await svc.validate_session("missing") is None

    @pytest.mark.asyncio
    async def test_revoke_session(self):
        db, conn = make_mock_db()
        conn.execute = AsyncMock(return_value="UPDATE 1")
        svc = AuthService(db)
        assert await svc.revoke_session("token") is True

    @pytest.mark.asyncio
    async def test_revoke_session_not_found(self):
        db, conn = make_mock_db()
        conn.execute = AsyncMock(return_value="UPDATE 0")
        svc = AuthService(db)
        assert await svc.revoke_session("missing") is False

    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self):
        db, conn = make_mock_db()
        user_id = uuid4()
        conn.fetchrow = AsyncMock(
            return_value={
                "id": user_id,
                "username": "test",
                "email": None,
                "password_hash": "hash",
                "role": UserRole.USER,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
            }
        )
        svc = AuthService(db)
        user = await svc.get_user_by_id(user_id)
        assert user is not None
        assert user.id == user_id

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self):
        db, conn = make_mock_db()
        conn.fetchrow = AsyncMock(return_value=None)
        svc = AuthService(db)
        assert await svc.get_user_by_id(uuid4()) is None

    @pytest.mark.asyncio
    async def test_change_password_success(self):
        db, conn = make_mock_db()
        svc = AuthService(db)
        user_id = uuid4()
        old_pass = "OldPass123!"
        old_hash = svc._hash_password(old_pass)

        conn.fetchrow = AsyncMock(
            return_value={
                "id": user_id,
                "username": "test",
                "email": None,
                "password_hash": old_hash,
                "role": UserRole.USER,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
            }
        )
        conn.execute = AsyncMock()

        result = await svc.change_password(user_id, old_pass, "NewPass456!")
        assert result is True
        assert conn.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_change_password_wrong_old(self):
        db, conn = make_mock_db()
        svc = AuthService(db)
        user_id = uuid4()
        old_hash = svc._hash_password("RealOld")

        conn.fetchrow = AsyncMock(
            return_value={
                "id": user_id,
                "username": "test",
                "email": None,
                "password_hash": old_hash,
                "role": UserRole.USER,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
            }
        )

        with pytest.raises(AuthenticationError, match="incorrect"):
            await svc.change_password(user_id, "WrongOld", "NewPass")
