import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from plasmaagent.security.audit_service import AuditService, AuditLogEntry, AuditLogQuery, AuditAction


class TestAuditService:
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        conn = AsyncMock()
        db.connection = MagicMock()
        db.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
        db.connection.return_value.__aexit__ = AsyncMock()
        return db, conn

    @pytest.fixture
    def audit_service(self, mock_db):
        db, _ = mock_db
        return AuditService(db)

    @pytest.mark.asyncio
    async def test_log_basic(self, audit_service, mock_db):
        _, conn = mock_db
        conn.execute = AsyncMock()

        entry = await audit_service.log(
            action=AuditAction.LOGIN,
            user_id=uuid4(),
            username="testuser",
            success=True,
        )

        assert entry.action == AuditAction.LOGIN
        assert entry.username == "testuser"
        assert entry.success is True
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_with_details(self, audit_service, mock_db):
        _, conn = mock_db
        conn.execute = AsyncMock()

        details = {"task_name": "backup_db", "duration_ms": 1500}
        entry = await audit_service.log(
            action=AuditAction.EXECUTE_TASK,
            user_id=uuid4(),
            resource_type="task",
            resource_id=uuid4(),
            details=details,
        )

        assert entry.details == details
        assert entry.resource_type == "task"

    @pytest.mark.asyncio
    async def test_log_failure(self, audit_service, mock_db):
        _, conn = mock_db
        conn.execute = AsyncMock()

        entry = await audit_service.log(
            action=AuditAction.ACCESS_DENIED,
            user_id=uuid4(),
            resource_type="config",
            success=False,
            error_message="Permission denied",
        )

        assert entry.success is False
        assert entry.error_message == "Permission denied"

    @pytest.mark.asyncio
    async def test_query_no_filters(self, audit_service, mock_db):
        _, conn = mock_db
        
        user_id = uuid4()
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": uuid4(),
                    "timestamp": datetime.utcnow(),
                    "user_id": user_id,
                    "username": "testuser",
                    "action": "login",
                    "resource_type": None,
                    "resource_id": None,
                    "details": "{}",
                    "ip_address": "127.0.0.1",
                    "user_agent": "Test",
                    "success": True,
                    "error_message": None,
                }
            ]
        )

        query = AuditLogQuery()
        entries = await audit_service.query(query)

        assert len(entries) == 1
        assert entries[0].username == "testuser"

    @pytest.mark.asyncio
    async def test_query_with_user_filter(self, audit_service, mock_db):
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[])

        user_id = uuid4()
        query = AuditLogQuery(user_id=user_id, action="login")
        entries = await audit_service.query(query)

        assert len(entries) == 0
        conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_with_time_range(self, audit_service, mock_db):
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[])

        query = AuditLogQuery(
            start_time=datetime.utcnow() - timedelta(days=1),
            end_time=datetime.utcnow(),
        )
        entries = await audit_service.query(query)

        assert isinstance(entries, list)

    @pytest.mark.asyncio
    async def test_get_user_activity(self, audit_service, mock_db):
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[])

        user_id = uuid4()
        entries = await audit_service.get_user_activity(user_id, limit=50)

        assert isinstance(entries, list)

    @pytest.mark.asyncio
    async def test_get_resource_history(self, audit_service, mock_db):
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[])

        resource_id = uuid4()
        entries = await audit_service.get_resource_history("task", resource_id)

        assert isinstance(entries, list)

    @pytest.mark.asyncio
    async def test_get_failed_actions(self, audit_service, mock_db):
        _, conn = mock_db
        conn.fetch = AsyncMock(return_value=[])

        entries = await audit_service.get_failed_actions(limit=10)

        assert isinstance(entries, list)


class TestAuditLogEntry:
    def test_create_entry(self):
        entry = AuditLogEntry(
            action=AuditAction.CREATE_TASK,
            user_id=uuid4(),
            username="admin",
            resource_type="task",
            resource_id=uuid4(),
        )

        assert entry.action == AuditAction.CREATE_TASK
        assert entry.username == "admin"
        assert entry.success is True

    def test_entry_frozen(self):
        entry = AuditLogEntry(action="test")

        with pytest.raises(Exception):
            entry.action = "modified"


class TestAuditLogQuery:
    def test_default_values(self):
        query = AuditLogQuery()

        assert query.limit == 100
        assert query.offset == 0
        assert query.user_id is None

    def test_custom_values(self):
        user_id = uuid4()
        query = AuditLogQuery(
            user_id=user_id,
            action="login",
            limit=50,
            offset=10,
        )

        assert query.user_id == user_id
        assert query.action == "login"
        assert query.limit == 50

    def test_invalid_limit(self):
        with pytest.raises(Exception):
            AuditLogQuery(limit=0)

        with pytest.raises(Exception):
            AuditLogQuery(limit=20000)
