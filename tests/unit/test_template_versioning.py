from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from plasmaagent.ai.templates.models import (
    RollbackReport,
    TemplateVersion,
    TemplateVersionCreate,
)
from plasmaagent.ai.templates.versioning import TemplateVersionService


class AsyncContextManager:
    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def create_mock_db():
    db = MagicMock()

    mock_cursor = MagicMock()
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchone = AsyncMock()
    mock_cursor.fetchall = AsyncMock()
    mock_cursor.rowcount = 0

    mock_conn = MagicMock()
    mock_conn.cursor = MagicMock(return_value=AsyncContextManager(mock_cursor))

    db.transaction = MagicMock(return_value=AsyncContextManager(mock_conn))
    db.connection = MagicMock(return_value=AsyncContextManager(mock_conn))

    return db, mock_cursor


@pytest.fixture
def sample_template_id():
    return uuid.uuid4()


@pytest.fixture
def sample_version_create(sample_template_id):
    return TemplateVersionCreate(
        template_id=sample_template_id,
        commands=("echo hello", "echo world"),
        pattern_name="test_pattern",
        confidence=0.85,
        change_description="Initial version",
        created_by="test_user",
    )


class TestTemplateVersionServiceInit:
    def test_init_with_database(self):
        db = MagicMock()
        service = TemplateVersionService(db)
        assert service._db is db


class TestCreateVersion:
    @pytest.mark.asyncio
    async def test_create_version_success(self, sample_version_create):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        version_id = uuid.uuid4()
        created_at = datetime.now()

        cursor.fetchone = AsyncMock(
            side_effect=[
                {"max_version": 0},
                {
                    "id": version_id,
                    "template_id": sample_version_create.template_id,
                    "version_number": 1,
                    "commands": list(sample_version_create.commands),
                    "pattern_name": sample_version_create.pattern_name,
                    "confidence": sample_version_create.confidence,
                    "change_description": sample_version_create.change_description,
                    "created_at": created_at,
                    "created_by": sample_version_create.created_by,
                },
            ]
        )

        result = await service.create_version(sample_version_create)

        assert isinstance(result, TemplateVersion)
        assert result.template_id == sample_version_create.template_id
        assert result.version_number == 1
        assert result.commands == sample_version_create.commands

    @pytest.mark.asyncio
    async def test_create_version_increments_version_number(self, sample_version_create):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        version_id = uuid.uuid4()
        created_at = datetime.now()

        cursor.fetchone = AsyncMock(
            side_effect=[
                {"max_version": 5},
                {
                    "id": version_id,
                    "template_id": sample_version_create.template_id,
                    "version_number": 6,
                    "commands": list(sample_version_create.commands),
                    "pattern_name": sample_version_create.pattern_name,
                    "confidence": sample_version_create.confidence,
                    "change_description": sample_version_create.change_description,
                    "created_at": created_at,
                    "created_by": sample_version_create.created_by,
                },
            ]
        )

        result = await service.create_version(sample_version_create)
        assert result.version_number == 6

    @pytest.mark.asyncio
    async def test_create_version_with_null_max(self, sample_version_create):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        version_id = uuid.uuid4()
        created_at = datetime.now()

        cursor.fetchone = AsyncMock(
            side_effect=[
                {"max_version": None},
                {
                    "id": version_id,
                    "template_id": sample_version_create.template_id,
                    "version_number": 1,
                    "commands": list(sample_version_create.commands),
                    "pattern_name": sample_version_create.pattern_name,
                    "confidence": sample_version_create.confidence,
                    "change_description": sample_version_create.change_description,
                    "created_at": created_at,
                    "created_by": sample_version_create.created_by,
                },
            ]
        )

        result = await service.create_version(sample_version_create)
        assert result.version_number == 1


class TestListVersions:
    @pytest.mark.asyncio
    async def test_list_versions_empty(self, sample_template_id):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        cursor.fetchall = AsyncMock(return_value=[])

        result = await service.list_versions(sample_template_id)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_versions_with_data(self, sample_template_id):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        version_id = uuid.uuid4()
        created_at = datetime.now()

        cursor.fetchall = AsyncMock(
            return_value=[
                {
                    "id": version_id,
                    "template_id": sample_template_id,
                    "version_number": 1,
                    "commands": ["echo test"],
                    "pattern_name": "test",
                    "confidence": 0.8,
                    "change_description": None,
                    "created_at": created_at,
                    "created_by": None,
                }
            ]
        )

        result = await service.list_versions(sample_template_id)
        assert len(result) == 1
        assert isinstance(result[0], TemplateVersion)

    @pytest.mark.asyncio
    async def test_list_versions_with_limit_and_offset(self, sample_template_id):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        cursor.fetchall = AsyncMock(return_value=[])

        await service.list_versions(sample_template_id, limit=10, offset=5)
        assert cursor.execute.called


class TestGetVersion:
    @pytest.mark.asyncio
    async def test_get_version_not_found(self):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        version_id = uuid.uuid4()
        cursor.fetchone = AsyncMock(return_value=None)

        result = await service.get_version(version_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_version_found(self):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        version_id = uuid.uuid4()
        template_id = uuid.uuid4()
        created_at = datetime.now()

        cursor.fetchone = AsyncMock(
            return_value={
                "id": version_id,
                "template_id": template_id,
                "version_number": 1,
                "commands": ["echo test"],
                "pattern_name": "test",
                "confidence": 0.8,
                "change_description": None,
                "created_at": created_at,
                "created_by": None,
            }
        )

        result = await service.get_version(version_id)
        assert isinstance(result, TemplateVersion)
        assert result.id == version_id


class TestGetLatestVersion:
    @pytest.mark.asyncio
    async def test_get_latest_version_not_found(self, sample_template_id):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        cursor.fetchone = AsyncMock(return_value=None)

        result = await service.get_latest_version(sample_template_id)
        assert result is None


class TestGetVersionByNumber:
    @pytest.mark.asyncio
    async def test_get_version_by_number_not_found(self, sample_template_id):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        cursor.fetchone = AsyncMock(return_value=None)

        result = await service.get_version_by_number(sample_template_id, 999)
        assert result is None


class TestRollback:
    @pytest.mark.asyncio
    async def test_rollback_version_not_found(self, sample_template_id):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        cursor.fetchone = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Version 999 not found"):
            await service.rollback(sample_template_id, 999)


class TestCountVersions:
    @pytest.mark.asyncio
    async def test_count_versions_empty(self, sample_template_id):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        cursor.fetchone = AsyncMock(return_value={"count": 0})

        result = await service.count_versions(sample_template_id)
        assert result == 0

    @pytest.mark.asyncio
    async def test_count_versions_with_data(self, sample_template_id):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        cursor.fetchone = AsyncMock(return_value={"count": 5})

        result = await service.count_versions(sample_template_id)
        assert result == 5


class TestDeleteVersion:
    @pytest.mark.asyncio
    async def test_delete_version_not_found(self):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        version_id = uuid.uuid4()
        cursor.rowcount = 0

        result = await service.delete_version(version_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_version_success(self):
        db, cursor = create_mock_db()
        service = TemplateVersionService(db)

        version_id = uuid.uuid4()
        cursor.rowcount = 1

        result = await service.delete_version(version_id)
        assert result is True


class TestRowToModel:
    def test_row_to_model_with_list_commands(self):
        db = MagicMock()
        service = TemplateVersionService(db)

        version_id = uuid.uuid4()
        template_id = uuid.uuid4()
        created_at = datetime.now()

        row = {
            "id": version_id,
            "template_id": template_id,
            "version_number": 1,
            "commands": ["echo test"],
            "pattern_name": "test",
            "confidence": 0.8,
            "change_description": None,
            "created_at": created_at,
            "created_by": None,
        }

        result = service._row_to_model(row)
        assert isinstance(result, TemplateVersion)
        assert result.commands == ("echo test",)

    def test_row_to_model_with_tuple_commands(self):
        db = MagicMock()
        service = TemplateVersionService(db)

        version_id = uuid.uuid4()
        template_id = uuid.uuid4()
        created_at = datetime.now()

        row = {
            "id": version_id,
            "template_id": template_id,
            "version_number": 1,
            "commands": ("echo test",),
            "pattern_name": "test",
            "confidence": 0.8,
            "change_description": None,
            "created_at": created_at,
            "created_by": None,
        }

        result = service._row_to_model(row)
        assert isinstance(result, TemplateVersion)
        assert result.commands == ("echo test",)

    def test_row_to_model_with_all_fields(self):
        db = MagicMock()
        service = TemplateVersionService(db)

        version_id = uuid.uuid4()
        template_id = uuid.uuid4()
        created_at = datetime.now()

        row = {
            "id": version_id,
            "template_id": template_id,
            "version_number": 5,
            "commands": ["cmd1", "cmd2", "cmd3"],
            "pattern_name": "complex_pattern",
            "confidence": 0.95,
            "change_description": "Updated commands",
            "created_at": created_at,
            "created_by": "admin",
        }

        result = service._row_to_model(row)
        assert result.version_number == 5
        assert len(result.commands) == 3
        assert result.change_description == "Updated commands"
        assert result.created_by == "admin"
