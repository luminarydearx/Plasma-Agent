from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from plasmaagent.ai.templates.models import (
    RollbackReport,
    TemplateVersion,
    TemplateVersionCreate,
)
from plasmaagent.ai.templates.versioning import TemplateVersionService
from plasmaagent.core.database import Database


@pytest.fixture
async def db():
    database = Database()
    await database.connect()
    yield database
    await database.disconnect()


@pytest.fixture
async def service(db):
    return TemplateVersionService(db)


@pytest.fixture
async def template_id(db):
    template_id = uuid.uuid4()
    async with db.transaction() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO template_metrics
                    (id, template_name, pattern, usage_count, success_count,
                     failure_count, avg_confidence, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (template_id, "test_template", "test_pattern", 0, 0, 0, 0.0),
            )
    return template_id


@pytest.fixture(autouse=True)
async def cleanup_versions(db, template_id):
    yield
    async with db.transaction() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM template_versions WHERE template_id = %s",
                (template_id,),
            )
            await cursor.execute(
                "DELETE FROM template_metrics WHERE id = %s",
                (template_id,),
            )


class TestTemplateVersionServiceIntegration:
    @pytest.mark.asyncio
    async def test_create_version(self, service, template_id):
        data = TemplateVersionCreate(
            template_id=template_id,
            commands=("echo hello", "echo world"),
            pattern_name="test_pattern",
            confidence=0.85,
            change_description="Initial version",
            created_by="test_user",
        )

        result = await service.create_version(data)

        assert isinstance(result, TemplateVersion)
        assert result.template_id == template_id
        assert result.version_number == 1
        assert result.commands == ("echo hello", "echo world")
        assert result.pattern_name == "test_pattern"
        assert result.confidence == 0.85
        assert result.change_description == "Initial version"
        assert result.created_by == "test_user"

    @pytest.mark.asyncio
    async def test_create_multiple_versions(self, service, template_id):
        for i in range(3):
            data = TemplateVersionCreate(
                template_id=template_id,
                commands=(f"echo version {i}",),
                pattern_name=f"pattern_v{i}",
                confidence=0.8 + (i * 0.05),
                change_description=f"Version {i}",
            )
            await service.create_version(data)

        versions = await service.list_versions(template_id)
        assert len(versions) == 3
        assert versions[0].version_number == 3
        assert versions[1].version_number == 2
        assert versions[2].version_number == 1

    @pytest.mark.asyncio
    async def test_list_versions_empty(self, service, template_id):
        result = await service.list_versions(template_id)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_versions_with_limit(self, service, template_id):
        for i in range(5):
            data = TemplateVersionCreate(
                template_id=template_id,
                commands=(f"echo {i}",),
                pattern_name=f"pattern_{i}",
                confidence=0.8,
            )
            await service.create_version(data)

        result = await service.list_versions(template_id, limit=3)
        assert len(result) == 3
        assert result[0].version_number == 5

    @pytest.mark.asyncio
    async def test_list_versions_with_offset(self, service, template_id):
        for i in range(5):
            data = TemplateVersionCreate(
                template_id=template_id,
                commands=(f"echo {i}",),
                pattern_name=f"pattern_{i}",
                confidence=0.8,
            )
            await service.create_version(data)

        result = await service.list_versions(template_id, limit=10, offset=2)
        assert len(result) == 3
        assert result[0].version_number == 3

    @pytest.mark.asyncio
    async def test_get_version(self, service, template_id):
        data = TemplateVersionCreate(
            template_id=template_id,
            commands=("echo test",),
            pattern_name="test",
            confidence=0.9,
        )
        created = await service.create_version(data)

        result = await service.get_version(created.id)
        assert result is not None
        assert result.id == created.id
        assert result.version_number == 1

    @pytest.mark.asyncio
    async def test_get_version_not_found(self, service):
        fake_id = uuid.uuid4()
        result = await service.get_version(fake_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_version(self, service, template_id):
        for i in range(3):
            data = TemplateVersionCreate(
                template_id=template_id,
                commands=(f"echo {i}",),
                pattern_name=f"pattern_{i}",
                confidence=0.8,
            )
            await service.create_version(data)

        result = await service.get_latest_version(template_id)
        assert result is not None
        assert result.version_number == 3

    @pytest.mark.asyncio
    async def test_get_latest_version_empty(self, service, template_id):
        result = await service.get_latest_version(template_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_version_by_number(self, service, template_id):
        data = TemplateVersionCreate(
            template_id=template_id,
            commands=("echo test",),
            pattern_name="test",
            confidence=0.9,
        )
        await service.create_version(data)

        result = await service.get_version_by_number(template_id, 1)
        assert result is not None
        assert result.version_number == 1

    @pytest.mark.asyncio
    async def test_get_version_by_number_not_found(self, service, template_id):
        result = await service.get_version_by_number(template_id, 999)
        assert result is None

    @pytest.mark.asyncio
    async def test_rollback(self, service, template_id):
        for i in range(3):
            data = TemplateVersionCreate(
                template_id=template_id,
                commands=(f"echo version {i}",),
                pattern_name=f"pattern_v{i}",
                confidence=0.8 + (i * 0.05),
            )
            await service.create_version(data)

        report = await service.rollback(template_id, 1, created_by="admin")

        assert isinstance(report, RollbackReport)
        assert report.template_id == template_id
        assert report.from_version == 3
        assert report.to_version == 1
        assert report.new_version_number == 4
        assert report.success is True

        latest = await service.get_latest_version(template_id)
        assert latest.version_number == 4
        assert latest.commands == ("echo version 0",)

    @pytest.mark.asyncio
    async def test_rollback_version_not_found(self, service, template_id):
        with pytest.raises(ValueError, match="Version 999 not found"):
            await service.rollback(template_id, 999)

    @pytest.mark.asyncio
    async def test_count_versions(self, service, template_id):
        count = await service.count_versions(template_id)
        assert count == 0

        for i in range(3):
            data = TemplateVersionCreate(
                template_id=template_id,
                commands=(f"echo {i}",),
                pattern_name=f"pattern_{i}",
                confidence=0.8,
            )
            await service.create_version(data)

        count = await service.count_versions(template_id)
        assert count == 3

    @pytest.mark.asyncio
    async def test_delete_version(self, service, template_id):
        data = TemplateVersionCreate(
            template_id=template_id,
            commands=("echo test",),
            pattern_name="test",
            confidence=0.9,
        )
        created = await service.create_version(data)

        result = await service.delete_version(created.id)
        assert result is True

        fetched = await service.get_version(created.id)
        assert fetched is None

    @pytest.mark.asyncio
    async def test_delete_version_not_found(self, service):
        fake_id = uuid.uuid4()
        result = await service.delete_version(fake_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_concurrent_version_creation(self, service, template_id):
        import asyncio

        async def create_version(i):
            data = TemplateVersionCreate(
                template_id=template_id,
                commands=(f"echo {i}",),
                pattern_name=f"pattern_{i}",
                confidence=0.8,
            )
            return await service.create_version(data)

        results = await asyncio.gather(*[create_version(i) for i in range(5)])

        assert len(results) == 5
        version_numbers = sorted([r.version_number for r in results])
        assert version_numbers == [1, 2, 3, 4, 5]
