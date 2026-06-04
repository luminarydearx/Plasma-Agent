import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from plasmaagent.security.auth_service import AuthService, AuthenticationError
from plasmaagent.security.models import UserCreate, UserLogin, UserRole


class TestAuthService:
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        conn = AsyncMock()
        db.connection = MagicMock()
        db.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
        db.connection.return_value.__aexit__ = AsyncMock()
        return db, conn

    @pytest.fixture
    def auth_service(self, mock_db):
        db, _ = mock_db
        return AuthService(db)

    def test_hash_password(self, auth_service):
        password = "SecurePass123!"
        hashed = auth_service._hash_password(password)
        assert hashed != password
        assert len(hashed) > 20

    def test_verify_password_correct(self, auth_service):
        password = "SecurePass123!"
        hashed = auth_service._hash_password(password)
        assert auth_service._verify_password(password, hashed) is True

    def test_verify_password_wrong(self, auth_service):
        password = "SecurePass123!"
        hashed = auth_service._hash_password(password)
        assert auth_service._verify_password("WrongPass", hashed) is False

    def test_generate_session_token(self, auth_service):
        token1 = auth_service._generate_session_token()
        token2 = auth_service._generate_session_token()
        assert token1 != token2
        assert len(token1) > 50

    @pytest.mark.asyncio
    async def test_create_user_success(self, auth_service, mock_db):
        _, conn = mock_db
        conn.fetchval = AsyncMock(side_effect=[None, None])
        conn.execute = AsyncMock()

        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
            role=UserRole.USER,
        )

        user = await auth_service.create_user(user_data)

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == UserRole.USER
        assert user.is_active is True
        assert user.password_hash != "SecurePass123!"

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, auth_service, mock_db):
        _, conn = mock_db
        from uuid import uuid4
        
        existing_id = uuid4()
        
        async def fetchval_side_effect(query, *args):
            if "username" in query.lower():
                return existing_id
            return None
        
        conn.fetchval = AsyncMock(side_effect=fetchval_side_effect)

        user_data = UserCreate(
            username="existing",
            password="SecurePass123!",
        )

        with pytest.raises(ValueError, match="already exists"):
            await auth_service.create_user(user_data)

    @pytest.mark.asyncio
    async def test_authenticate_success(self, auth_service, mock_db):
        _, conn = mock_db
        from uuid import uuid4
        
        user_id = uuid4()
        password = "SecurePass123!"
        password_hash = auth_service._hash_password(password)
        
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
        user = await auth_service.authenticate(login_data)

        assert user.username == "testuser"
        assert user.id == user_id

    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self, auth_service, mock_db):
        _, conn = mock_db
        from uuid import uuid4
        
        correct_password = "CorrectPass123!"
        password_hash = auth_service._hash_password(correct_password)
        
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
            await auth_service.authenticate(login_data)

    @pytest.mark.asyncio
    async def test_authenticate_disabled_account(self, auth_service, mock_db):
        _, conn = mock_db
        from uuid import uuid4
        
        password = "SecurePass123!"
        password_hash = auth_service._hash_password(password)
        
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

        login_data = UserLogin(username="testuser", password=password)

        with pytest.raises(AuthenticationError, match="disabled"):
            await auth_service.authenticate(login_data)

    @pytest.mark.asyncio
    async def test_create_session(self, auth_service, mock_db):
        _, conn = mock_db
        from uuid import uuid4
        
        conn.execute = AsyncMock()
        user_id = uuid4()

        session = await auth_service.create_session(
            user_id=user_id,
            ip_address="127.0.0.1",
            user_agent="TestAgent",
        )

        assert session.user_id == user_id
        assert session.ip_address == "127.0.0.1"
        assert session.user_agent == "TestAgent"
        assert session.is_active is True
        assert session.expires_at > datetime.utcnow()

    @pytest.mark.asyncio
    async def test_validate_session_success(self, auth_service, mock_db):
        _, conn = mock_db
        from uuid import uuid4
        
        user_id = uuid4()
        password_hash = auth_service._hash_password("pass")
        
        conn.fetchrow = AsyncMock(
            return_value={
                "user_id": user_id,
                "expires_at": datetime.utcnow() + timedelta(hours=1),
                "is_active": True,
                "username": "testuser",
                "email": None,
                "password_hash": password_hash,
                "role": UserRole.USER,
                "user_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
            }
        )

        user = await auth_service.validate_session("valid_token")

        assert user is not None
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_validate_session_expired(self, auth_service, mock_db):
        _, conn = mock_db
        from uuid import uuid4
        
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

        user = await auth_service.validate_session("expired_token")
        assert user is None

    @pytest.mark.asyncio
    async def test_revoke_session(self, auth_service, mock_db):
        _, conn = mock_db
        conn.execute = AsyncMock(return_value="UPDATE 1")

        result = await auth_service.revoke_session("token")
        assert result is True
