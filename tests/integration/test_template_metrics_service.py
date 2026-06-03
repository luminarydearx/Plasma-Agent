import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest

from plasmaagent.core.database import get_database
from plasmaagent.models.template_metrics import (
    TemplateMetricsCreate,
    TemplateMetricsUpdate,
)
from plasmaagent.services.template_metrics_service import TemplateMetricsService


@pytest.fixture
async def metrics_service():
    db = get_database()
    await db.connect()
    service = TemplateMetricsService(db)
    yield service
    await db.disconnect()


@pytest.fixture
async def cleanup_metrics(metrics_service):
    created_names = []
    yield created_names
    for name in created_names:
        await metrics_service.delete_by_name(name)


class TestTemplateMetricsServiceCreate:
    async def test_create_metric_success(self, metrics_service, cleanup_metrics):
        template_name = f"test_backup_{uuid4().hex[:8]}"
        cleanup_metrics.append(template_name)

        data = TemplateMetricsCreate(
            template_name=template_name,
            pattern="backup.*postgresql",
            usage_count=0,
            success_count=0,
            failure_count=0,
            avg_confidence=Decimal("0.95"),
            total_generation_time_ms=0,
        )

        result = await metrics_service.create_metric(data)

        assert result.template_name == template_name
        assert result.pattern == "backup.*postgresql"
        assert result.usage_count == 0
        assert result.avg_confidence == Decimal("0.95")
        assert result.id is not None
        assert result.created_at is not None

    async def test_create_metric_duplicate_name_fails(self, metrics_service, cleanup_metrics):
        template_name = f"test_dup_{uuid4().hex[:8]}"
        cleanup_metrics.append(template_name)

        data = TemplateMetricsCreate(
            template_name=template_name,
            pattern="test.*pattern",
        )

        await metrics_service.create_metric(data)

        with pytest.raises(Exception):
            await metrics_service.create_metric(data)

    async def test_create_metric_invalid_confidence(self, metrics_service):
        with pytest.raises(Exception):
            TemplateMetricsCreate(
                template_name="test_invalid",
                pattern="test",
                avg_confidence=Decimal("1.50"),
            )

    async def test_create_metric_negative_count(self, metrics_service):
        with pytest.raises(Exception):
            TemplateMetricsCreate(
                template_name="test_negative",
                pattern="test",
                usage_count=-1,
            )


class TestTemplateMetricsServiceGet:
    async def test_get_by_name_exists(self, metrics_service, cleanup_metrics):
        template_name = f"test_get_{uuid4().hex[:8]}"
        cleanup_metrics.append(template_name)

        data = TemplateMetricsCreate(
            template_name=template_name,
            pattern="test.*pattern",
        )
        created = await metrics_service.create_metric(data)

        result = await metrics_service.get_by_name(template_name)

        assert result is not None
        assert result.id == created.id
        assert result.template_name == template_name

    async def test_get_by_name_not_exists(self, metrics_service):
        result = await metrics_service.get_by_name("nonexistent_template_xyz")
        assert result is None

    async def test_get_by_id_exists(self, metrics_service, cleanup_metrics):
        template_name = f"test_get_id_{uuid4().hex[:8]}"
        cleanup_metrics.append(template_name)

        data = TemplateMetricsCreate(
            template_name=template_name,
            pattern="test.*pattern",
        )
        created = await metrics_service.create_metric(data)

        result = await metrics_service.get_by_id(created.id)

        assert result is not None
        assert result.template_name == template_name

    async def test_get_by_id_not_exists(self, metrics_service):
        fake_id = uuid4()
        result = await metrics_service.get_by_id(fake_id)
        assert result is None


class TestTemplateMetricsServiceRecordUsage:
    async def test_record_usage_creates_new_metric(self, metrics_service, cleanup_metrics):
        template_name = f"test_record_{uuid4().hex[:8]}"
        cleanup_metrics.append(template_name)

        result = await metrics_service.record_usage(
            template_name=template_name,
            pattern="backup.*postgresql",
            confidence=Decimal("0.95"),
            generation_time_ms=50,
            success=True,
        )

        assert result.template_name == template_name
        assert result.usage_count == 1
        assert result.success_count == 1
        assert result.failure_count == 0
        assert result.avg_confidence == Decimal("0.95")
        assert result.total_generation_time_ms == 50

    async def test_record_usage_increments_existing(self, metrics_service, cleanup_metrics):
        template_name = f"test_increment_{uuid4().hex[:8]}"
        cleanup_metrics.append(template_name)

        await metrics_service.record_usage(
            template_name=template_name,
            pattern="backup.*postgresql",
            confidence=Decimal("0.95"),
            generation_time_ms=50,
            success=True,
        )

        result = await metrics_service.record_usage(
            template_name=template_name,
            pattern="backup.*postgresql",
            confidence=Decimal("0.85"),
            generation_time_ms=70,
            success=True,
        )

        assert result.usage_count == 2
        assert result.success_count == 2
        assert result.failure_count == 0
        assert result.avg_confidence == Decimal("0.90")
        assert result.total_generation_time_ms == 120

    async def test_record_usage_tracks_failures(self, metrics_service, cleanup_metrics):
        template_name = f"test_failure_{uuid4().hex[:8]}"
        cleanup_metrics.append(template_name)

        await metrics_service.record_usage(
            template_name=template_name,
            pattern="test.*pattern",
            confidence=Decimal("0.95"),
            generation_time_ms=50,
            success=True,
        )

        result = await metrics_service.record_usage(
            template_name=template_name,
            pattern="test.*pattern",
            confidence=Decimal("0.50"),
            generation_time_ms=100,
            success=False,
        )

        assert result.usage_count == 2
        assert result.success_count == 1
        assert result.failure_count == 1

    async def test_record_usage_concurrent(self, metrics_service, cleanup_metrics):
        template_name = f"test_concurrent_{uuid4().hex[:8]}"
        cleanup_metrics.append(template_name)

        async def record_success():
            return await metrics_service.record_usage(
                template_name=template_name,
                pattern="test.*concurrent",
                confidence=Decimal("0.90"),
                generation_time_ms=50,
                success=True,
            )

        tasks = [record_success() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        final = await metrics_service.get_by_name(template_name)
        assert final is not None
        assert final.usage_count == 10
        assert final.success_count == 10


class TestTemplateMetricsServiceUpdate:
    async def test_update_metric_success(self, metrics_service, cleanup_metrics):
        template_name = f"test_update_{uuid4().hex[:8]}"
        cleanup_metrics.append(template_name)

        data = TemplateMetricsCreate(
            template_name=template_name,
            pattern="test.*pattern",
        )
        created = await metrics_service.create_metric(data)

        update = TemplateMetricsUpdate(usage_count=100)
        result = await metrics_service.update_metric(created.id, update)

        assert result is not None
        assert result.usage_count == 100

    async def test_update_metric_empty_update(self, metrics_service, cleanup_metrics):
        template_name = f"test_empty_update_{uuid4().hex[:8]}"
        cleanup_metrics.append(template_name)

        data = TemplateMetricsCreate(
            template_name=template_name,
            pattern="test.*pattern",
            usage_count=50,
        )
        created = await metrics_service.create_metric(data)

        update = TemplateMetricsUpdate()
        result = await metrics_service.update_metric(created.id, update)

        assert result is not None
        assert result.usage_count == 50

    async def test_update_metric_not_exists(self, metrics_service):
        fake_id = uuid4()
        update = TemplateMetricsUpdate(usage_count=100)
        result = await metrics_service.update_metric(fake_id, update)
        assert result is None


class TestTemplateMetricsServiceList:
    async def test_list_all_empty(self, metrics_service, cleanup_metrics):
        results = await metrics_service.list_all(limit=10, offset=0)
        assert isinstance(results, list)

    async def test_list_all_with_data(self, metrics_service, cleanup_metrics):
        for i in range(3):
            template_name = f"test_list_{i}_{uuid4().hex[:8]}"
            cleanup_metrics.append(template_name)
            data = TemplateMetricsCreate(
                template_name=template_name,
                pattern=f"test.*pattern_{i}",
            )
            await metrics_service.create_metric(data)

        results = await metrics_service.list_all(limit=10, offset=0)
        assert len(results) >= 3

    async def test_list_all_pagination(self, metrics_service, cleanup_metrics):
        for i in range(5):
            template_name = f"test_page_{i}_{uuid4().hex[:8]}"
            cleanup_metrics.append(template_name)
            data = TemplateMetricsCreate(
                template_name=template_name,
                pattern=f"test.*page_{i}",
            )
            await metrics_service.create_metric(data)

        page1 = await metrics_service.list_all(limit=2, offset=0)
        page2 = await metrics_service.list_all(limit=2, offset=2)

        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id != page2[0].id


class TestTemplateMetricsServiceAnalytics:
    async def test_get_top_by_usage(self, metrics_service, cleanup_metrics):
        for i in range(5):
            template_name = f"test_top_usage_{i}_{uuid4().hex[:8]}"
            cleanup_metrics.append(template_name)
            for _ in range(i + 1):
                await metrics_service.record_usage(
                    template_name=template_name,
                    pattern=f"test.*top_{i}",
                    confidence=Decimal("0.90"),
                    generation_time_ms=50,
                    success=True,
                )

        results = await metrics_service.get_top_by_usage(limit=3)
        assert len(results) <= 3
        if len(results) >= 2:
            assert results[0].usage_count >= results[1].usage_count

    async def test_get_top_by_success_rate(self, metrics_service, cleanup_metrics):
        template_name = f"test_success_rate_{uuid4().hex[:8]}"
        cleanup_metrics.append(template_name)

        for _ in range(8):
            await metrics_service.record_usage(
                template_name=template_name,
                pattern="test.*success",
                confidence=Decimal("0.90"),
                generation_time_ms=50,
                success=True,
            )
        for _ in range(2):
            await metrics_service.record_usage(
                template_name=template_name,
                pattern="test.*success",
                confidence=Decimal("0.50"),
                generation_time_ms=100,
                success=False,
            )

        results = await metrics_service.get_top_by_success_rate(limit=10)
        found = [r for r in results if r.template_name == template_name]
        if found:
            assert found[0].success_count == 8
            assert found[0].failure_count == 2

    async def test_get_low_performing(self, metrics_service, cleanup_metrics):
        template_name = f"test_low_perf_{uuid4().hex[:8]}"
        cleanup_metrics.append(template_name)

        for _ in range(2):
            await metrics_service.record_usage(
                template_name=template_name,
                pattern="test.*low",
                confidence=Decimal("0.50"),
                generation_time_ms=100,
                success=True,
            )
        for _ in range(8):
            await metrics_service.record_usage(
                template_name=template_name,
                pattern="test.*low",
                confidence=Decimal("0.30"),
                generation_time_ms=200,
                success=False,
            )

        results = await metrics_service.get_low_performing(
            min_usage=5,
            max_success_rate=0.5,
        )
        found = [r for r in results if r.template_name == template_name]
        assert len(found) == 1
        assert found[0].success_count == 2
        assert found[0].failure_count == 8


class TestTemplateMetricsServiceDelete:
    async def test_delete_metric_by_id(self, metrics_service, cleanup_metrics):
        template_name = f"test_delete_id_{uuid4().hex[:8]}"

        data = TemplateMetricsCreate(
            template_name=template_name,
            pattern="test.*delete",
        )
        created = await metrics_service.create_metric(data)

        result = await metrics_service.delete_metric(created.id)
        assert result is True

        deleted = await metrics_service.get_by_id(created.id)
        assert deleted is None

    async def test_delete_metric_not_exists(self, metrics_service):
        fake_id = uuid4()
        result = await metrics_service.delete_metric(fake_id)
        assert result == 0

    async def test_delete_by_name(self, metrics_service):
        template_name = f"test_delete_name_{uuid4().hex[:8]}"

        data = TemplateMetricsCreate(
            template_name=template_name,
            pattern="test.*delete",
        )
        await metrics_service.create_metric(data)

        result = await metrics_service.delete_by_name(template_name)
        assert result >= 1

        deleted = await metrics_service.get_by_name(template_name)
        assert deleted is None

    async def test_delete_by_name_not_exists(self, metrics_service):
        result = await metrics_service.delete_by_name("nonexistent_xyz")
        assert result == 0


class TestTemplateMetricsServiceAggregate:
    async def test_get_aggregate_stats_empty(self, metrics_service):
        stats = await metrics_service.get_aggregate_stats()
        assert "total_templates" in stats
        assert "total_usage" in stats
        assert "total_success" in stats
        assert "total_failure" in stats
        assert "global_avg_confidence" in stats
        assert "avg_generation_time_ms" in stats

    async def test_get_aggregate_stats_with_data(self, metrics_service, cleanup_metrics):
        for i in range(3):
            template_name = f"test_agg_{i}_{uuid4().hex[:8]}"
            cleanup_metrics.append(template_name)
            await metrics_service.record_usage(
                template_name=template_name,
                pattern=f"test.*agg_{i}",
                confidence=Decimal("0.90"),
                generation_time_ms=50,
                success=True,
            )

        stats = await metrics_service.get_aggregate_stats()
        assert stats["total_templates"] >= 3
        assert stats["total_usage"] >= 3
        assert stats["total_success"] >= 3
