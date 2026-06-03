import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from plasmaagent.core.database import Database, get_database
from plasmaagent.models.template_metrics import (
    TemplateMetrics,
    TemplateMetricsCreate,
    TemplateMetricsUpdate,
)
from plasmaagent.services.template_metrics_service import TemplateMetricsService


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[Database, None]:
    database = get_database()
    await database.connect()
    try:
        yield database
    finally:
        async with database.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM template_metrics")
            await conn.commit()
        await database.disconnect()


@pytest_asyncio.fixture
async def service(db: Database) -> TemplateMetricsService:
    return TemplateMetricsService(database=db)


@pytest.fixture
def sample_create() -> TemplateMetricsCreate:
    return TemplateMetricsCreate(
        template_name="backup_database",
        pattern="backup postgresql",
        usage_count=0,
        success_count=0,
        failure_count=0,
        avg_confidence=Decimal("0.9500"),
        total_generation_time_ms=0,
        last_used_at=None,
    )


class TestCreateMetric:
    @pytest.mark.asyncio
    async def test_create_metric_success(
        self,
        service: TemplateMetricsService,
        sample_create: TemplateMetricsCreate,
    ) -> None:
        result = await service.create_metric(sample_create)

        assert isinstance(result, TemplateMetrics)
        assert result.template_name == "backup_database"
        assert result.pattern == "backup postgresql"
        assert result.usage_count == 0
        assert result.avg_confidence == Decimal("0.9500")
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_create_metric_duplicate_raises(
        self,
        service: TemplateMetricsService,
        sample_create: TemplateMetricsCreate,
    ) -> None:
        await service.create_metric(sample_create)

        with pytest.raises(Exception):
            await service.create_metric(sample_create)

    @pytest.mark.asyncio
    async def test_create_metric_different_pattern_ok(
        self,
        service: TemplateMetricsService,
        sample_create: TemplateMetricsCreate,
    ) -> None:
        await service.create_metric(sample_create)

        different_pattern = TemplateMetricsCreate(
            template_name="backup_database",
            pattern="backup mysql",
            usage_count=0,
            success_count=0,
            failure_count=0,
            avg_confidence=Decimal("0.9000"),
            total_generation_time_ms=0,
            last_used_at=None,
        )
        result = await service.create_metric(different_pattern)
        assert result.pattern == "backup mysql"

    @pytest.mark.asyncio
    async def test_create_metric_long_template_name_raises(
        self,
        service: TemplateMetricsService,
    ) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TemplateMetricsCreate(
                template_name="x" * 300,
                pattern="some pattern",
            )

    @pytest.mark.asyncio
    async def test_create_metric_long_pattern_raises(
        self,
        service: TemplateMetricsService,
    ) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TemplateMetricsCreate(
                template_name="tmpl",
                pattern="x" * 600,
            )

    @pytest.mark.asyncio
    async def test_create_metric_negative_usage_count_raises(
        self,
        service: TemplateMetricsService,
    ) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TemplateMetricsCreate(
                template_name="tmpl",
                pattern="pat",
                usage_count=-1,
            )

    @pytest.mark.asyncio
    async def test_create_metric_confidence_out_of_range_raises(
        self,
        service: TemplateMetricsService,
    ) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TemplateMetricsCreate(
                template_name="tmpl",
                pattern="pat",
                avg_confidence=Decimal("1.50"),
            )


class TestGetById:
    @pytest.mark.asyncio
    async def test_get_existing(
        self,
        service: TemplateMetricsService,
        sample_create: TemplateMetricsCreate,
    ) -> None:
        created = await service.create_metric(sample_create)
        fetched = await service.get_by_id(created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.template_name == "backup_database"

    @pytest.mark.asyncio
    async def test_get_nonexistent(
        self,
        service: TemplateMetricsService,
    ) -> None:
        result = await service.get_by_id(uuid.uuid4())
        assert result is None


class TestGetByName:
    @pytest.mark.asyncio
    async def test_get_by_name_existing(
        self,
        service: TemplateMetricsService,
        sample_create: TemplateMetricsCreate,
    ) -> None:
        await service.create_metric(sample_create)
        result = await service.get_by_name("backup_database")

        assert result is not None
        assert result.template_name == "backup_database"

    @pytest.mark.asyncio
    async def test_get_by_name_nonexistent(
        self,
        service: TemplateMetricsService,
    ) -> None:
        result = await service.get_by_name("does_not_exist")
        assert result is None


class TestGetByNameAndPattern:
    @pytest.mark.asyncio
    async def test_get_exact_match(
        self,
        service: TemplateMetricsService,
        sample_create: TemplateMetricsCreate,
    ) -> None:
        await service.create_metric(sample_create)
        result = await service.get_by_name_and_pattern(
            "backup_database", "backup postgresql"
        )

        assert result is not None
        assert result.pattern == "backup postgresql"

    @pytest.mark.asyncio
    async def test_get_wrong_pattern_returns_none(
        self,
        service: TemplateMetricsService,
        sample_create: TemplateMetricsCreate,
    ) -> None:
        await service.create_metric(sample_create)
        result = await service.get_by_name_and_pattern(
            "backup_database", "wrong pattern"
        )
        assert result is None


class TestRecordUsage:
    @pytest.mark.asyncio
    async def test_record_usage_creates_new(
        self,
        service: TemplateMetricsService,
    ) -> None:
        result = await service.record_usage(
            template_name="new_template",
            pattern="new pattern",
            confidence=Decimal("0.8500"),
            generation_time_ms=50,
            success=True,
        )

        assert result.usage_count == 1
        assert result.success_count == 1
        assert result.failure_count == 0
        assert result.avg_confidence == Decimal("0.8500")
        assert result.total_generation_time_ms == 50
        assert result.last_used_at is not None

    @pytest.mark.asyncio
    async def test_record_usage_increments_existing(
        self,
        service: TemplateMetricsService,
    ) -> None:
        await service.record_usage(
            "tmpl", "pat", Decimal("0.8000"), 100, True
        )
        result = await service.record_usage(
            "tmpl", "pat", Decimal("0.9000"), 150, True
        )

        assert result.usage_count == 2
        assert result.success_count == 2
        assert result.total_generation_time_ms == 250
        expected_avg = (Decimal("0.8000") + Decimal("0.9000")) / 2
        assert abs(result.avg_confidence - expected_avg) < Decimal("0.0001")

    @pytest.mark.asyncio
    async def test_record_usage_failure_increments_failure(
        self,
        service: TemplateMetricsService,
    ) -> None:
        await service.record_usage("tmpl", "pat", Decimal("0.5"), 100, True)
        result = await service.record_usage("tmpl", "pat", Decimal("0.3"), 100, False)

        assert result.usage_count == 2
        assert result.success_count == 1
        assert result.failure_count == 1

    @pytest.mark.asyncio
    async def test_record_usage_different_patterns_separate(
        self,
        service: TemplateMetricsService,
    ) -> None:
        await service.record_usage("tmpl", "pattern A", Decimal("0.9"), 100, True)
        await service.record_usage("tmpl", "pattern B", Decimal("0.7"), 100, False)

        a = await service.get_by_name_and_pattern("tmpl", "pattern A")
        b = await service.get_by_name_and_pattern("tmpl", "pattern B")

        assert a is not None and b is not None
        assert a.usage_count == 1
        assert b.usage_count == 1
        assert a.success_count == 1
        assert b.failure_count == 1

    @pytest.mark.asyncio
    async def test_record_usage_updates_last_used_at(
        self,
        service: TemplateMetricsService,
    ) -> None:
        before = datetime.now(timezone.utc)
        result = await service.record_usage(
            "tmpl", "pat", Decimal("0.5"), 100, True
        )
        assert result.last_used_at is not None
        assert result.last_used_at >= before

    @pytest.mark.asyncio
    async def test_record_usage_many_times(
        self,
        service: TemplateMetricsService,
    ) -> None:
        for i in range(20):
            await service.record_usage(
                "tmpl", "pat", Decimal("0.9"), 100, i % 2 == 0
            )

        result = await service.get_by_name_and_pattern("tmpl", "pat")
        assert result is not None
        assert result.usage_count == 20
        assert result.success_count == 10
        assert result.failure_count == 10


class TestUpdateMetric:
    @pytest.mark.asyncio
    async def test_update_single_field(
        self,
        service: TemplateMetricsService,
        sample_create: TemplateMetricsCreate,
    ) -> None:
        created = await service.create_metric(sample_create)
        update = TemplateMetricsUpdate(usage_count=42)

        result = await service.update_metric(created.id, update)

        assert result is not None
        assert result.usage_count == 42
        assert result.success_count == 0

    @pytest.mark.asyncio
    async def test_update_multiple_fields(
        self,
        service: TemplateMetricsService,
        sample_create: TemplateMetricsCreate,
    ) -> None:
        created = await service.create_metric(sample_create)
        update = TemplateMetricsUpdate(
            usage_count=10,
            success_count=8,
            failure_count=2,
        )
        result = await service.update_metric(created.id, update)

        assert result is not None
        assert result.usage_count == 10
        assert result.success_count == 8
        assert result.failure_count == 2

    @pytest.mark.asyncio
    async def test_update_empty_returns_current(
        self,
        service: TemplateMetricsService,
        sample_create: TemplateMetricsCreate,
    ) -> None:
        created = await service.create_metric(sample_create)
        result = await service.update_metric(created.id, TemplateMetricsUpdate())

        assert result is not None
        assert result.id == created.id

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(
        self,
        service: TemplateMetricsService,
    ) -> None:
        update = TemplateMetricsUpdate(usage_count=10)
        result = await service.update_metric(uuid.uuid4(), update)
        assert result is None


class TestListAll:
    @pytest.mark.asyncio
    async def test_list_empty(
        self,
        service: TemplateMetricsService,
    ) -> None:
        result = await service.list_all()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_multiple(
        self,
        service: TemplateMetricsService,
    ) -> None:
        await service.record_usage("t1", "p1", Decimal("0.9"), 100, True)
        await service.record_usage("t2", "p2", Decimal("0.8"), 100, True)

        result = await service.list_all()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_with_limit(
        self,
        service: TemplateMetricsService,
    ) -> None:
        for i in range(5):
            await service.record_usage(f"t{i}", f"p{i}", Decimal("0.9"), 100, True)

        result = await service.list_all(limit=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_with_offset(
        self,
        service: TemplateMetricsService,
    ) -> None:
        for i in range(5):
            await service.record_usage(f"t{i}", f"p{i}", Decimal("0.9"), 100, True)

        result = await service.list_all(limit=10, offset=2)
        assert len(result) == 3


class TestTopMetrics:
    @pytest.mark.asyncio
    async def test_get_top_by_usage(
        self,
        service: TemplateMetricsService,
    ) -> None:
        await service.record_usage("low", "p", Decimal("0.9"), 100, True)
        for _ in range(5):
            await service.record_usage("high", "p", Decimal("0.9"), 100, True)

        result = await service.get_top_by_usage(limit=1)
        assert len(result) == 1
        assert result[0].template_name == "high"

    @pytest.mark.asyncio
    async def test_get_top_by_usage_empty(
        self,
        service: TemplateMetricsService,
    ) -> None:
        result = await service.get_top_by_usage()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_top_by_success_rate(
        self,
        service: TemplateMetricsService,
    ) -> None:
        for _ in range(5):
            await service.record_usage("all_success", "p", Decimal("0.9"), 100, True)
        for _ in range(5):
            await service.record_usage("all_fail", "p", Decimal("0.1"), 100, False)

        result = await service.get_top_by_success_rate(limit=1)
        assert len(result) == 1
        assert result[0].template_name == "all_success"

    @pytest.mark.asyncio
    async def test_get_low_performing(
        self,
        service: TemplateMetricsService,
    ) -> None:
        for _ in range(5):
            await service.record_usage("bad", "p", Decimal("0.2"), 100, False)

        result = await service.get_low_performing(min_usage=3, max_success_rate=0.5)
        assert len(result) == 1
        assert result[0].template_name == "bad"

    @pytest.mark.asyncio
    async def test_get_low_performing_none_match(
        self,
        service: TemplateMetricsService,
    ) -> None:
        for _ in range(5):
            await service.record_usage("good", "p", Decimal("0.9"), 100, True)

        result = await service.get_low_performing(min_usage=3, max_success_rate=0.5)
        assert len(result) == 0


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_by_id(
        self,
        service: TemplateMetricsService,
        sample_create: TemplateMetricsCreate,
    ) -> None:
        created = await service.create_metric(sample_create)
        deleted = await service.delete_metric(created.id)

        assert deleted is True
        assert await service.get_by_id(created.id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(
        self,
        service: TemplateMetricsService,
    ) -> None:
        result = await service.delete_metric(uuid.uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_by_name(
        self,
        service: TemplateMetricsService,
    ) -> None:
        await service.record_usage("tmpl", "p1", Decimal("0.9"), 100, True)
        await service.record_usage("tmpl", "p2", Decimal("0.9"), 100, True)

        count = await service.delete_by_name("tmpl")
        assert count == 2

    @pytest.mark.asyncio
    async def test_delete_by_name_nonexistent(
        self,
        service: TemplateMetricsService,
    ) -> None:
        count = await service.delete_by_name("does_not_exist")
        assert count == 0

    @pytest.mark.asyncio
    async def test_delete_by_name_and_pattern(
        self,
        service: TemplateMetricsService,
    ) -> None:
        await service.record_usage("tmpl", "p1", Decimal("0.9"), 100, True)
        await service.record_usage("tmpl", "p2", Decimal("0.9"), 100, True)

        deleted = await service.delete_by_name_and_pattern("tmpl", "p1")
        assert deleted is True

        remaining = await service.list_all()
        assert len(remaining) == 1
        assert remaining[0].pattern == "p2"

    @pytest.mark.asyncio
    async def test_delete_by_name_and_pattern_nonexistent(
        self,
        service: TemplateMetricsService,
    ) -> None:
        result = await service.delete_by_name_and_pattern("x", "y")
        assert result is False


class TestAggregateStats:
    @pytest.mark.asyncio
    async def test_stats_empty(
        self,
        service: TemplateMetricsService,
    ) -> None:
        stats = await service.get_aggregate_stats()

        assert stats["total_templates"] == 0
        assert stats["total_usage"] == 0
        assert stats["global_avg_confidence"] == Decimal("0.0000")

    @pytest.mark.asyncio
    async def test_stats_with_data(
        self,
        service: TemplateMetricsService,
    ) -> None:
        await service.record_usage("t1", "p1", Decimal("0.9"), 100, True)
        await service.record_usage("t2", "p2", Decimal("0.8"), 200, False)

        stats = await service.get_aggregate_stats()

        assert stats["total_templates"] == 2
        assert stats["total_usage"] == 2
        assert stats["total_success"] == 1
        assert stats["total_failure"] == 1
        assert stats["avg_generation_time_ms"] == 150.0

    @pytest.mark.asyncio
    async def test_stats_large_dataset(
        self,
        service: TemplateMetricsService,
    ) -> None:
        for i in range(100):
            await service.record_usage(
                f"t{i}", f"p{i}", Decimal("0.8"), 50, i % 3 != 0
            )

        stats = await service.get_aggregate_stats()
        assert stats["total_templates"] == 100
        assert stats["total_usage"] == 100


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_sql_injection_in_template_name(
        self,
        service: TemplateMetricsService,
    ) -> None:
        malicious = "'; DROP TABLE template_metrics; --"
        result = await service.record_usage(
            malicious, "pattern", Decimal("0.5"), 100, True
        )
        assert result.template_name == malicious

        stats = await service.get_aggregate_stats()
        assert stats["total_templates"] >= 1

    @pytest.mark.asyncio
    async def test_sql_injection_in_pattern(
        self,
        service: TemplateMetricsService,
    ) -> None:
        malicious_pattern = "pattern'; DROP TABLE tasks; --"
        result = await service.record_usage(
            "tmpl", malicious_pattern, Decimal("0.5"), 100, True
        )
        assert result.pattern == malicious_pattern

    @pytest.mark.asyncio
    async def test_unicode_template_name(
        self,
        service: TemplateMetricsService,
    ) -> None:
        result = await service.record_usage(
            "テンプレート", "パターン", Decimal("0.5"), 100, True
        )
        assert result.template_name == "テンプレート"

    @pytest.mark.asyncio
    async def test_emoji_in_pattern(
        self,
        service: TemplateMetricsService,
    ) -> None:
        result = await service.record_usage(
            "tmpl", "🚀 backup 🗄️", Decimal("0.5"), 100, True
        )
        assert result.pattern == "🚀 backup 🗄️"

    @pytest.mark.asyncio
    async def test_very_long_pattern(
        self,
        service: TemplateMetricsService,
    ) -> None:
        long_pattern = "a" * 499
        result = await service.record_usage(
            "tmpl", long_pattern, Decimal("0.5"), 100, True
        )
        assert result.pattern == long_pattern

    @pytest.mark.asyncio
    async def test_zero_confidence(
        self,
        service: TemplateMetricsService,
    ) -> None:
        result = await service.record_usage(
            "tmpl", "pat", Decimal("0.0000"), 100, True
        )
        assert result.avg_confidence == Decimal("0.0000")

    @pytest.mark.asyncio
    async def test_max_confidence(
        self,
        service: TemplateMetricsService,
    ) -> None:
        result = await service.record_usage(
            "tmpl", "pat", Decimal("1.0000"), 100, True
        )
        assert result.avg_confidence == Decimal("1.0000")

    @pytest.mark.asyncio
    async def test_negative_generation_time_rejected(
        self,
        service: TemplateMetricsService,
    ) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TemplateMetricsCreate(
                template_name="tmpl",
                pattern="pat",
                total_generation_time_ms=-1,
            )

    @pytest.mark.asyncio
    async def test_concurrent_record_usage(
        self,
        service: TemplateMetricsService,
    ) -> None:
        import asyncio

        tasks = [
            service.record_usage("tmpl", "pat", Decimal("0.9"), 100, True)
            for _ in range(10)
        ]
        await asyncio.gather(*tasks)

        result = await service.get_by_name_and_pattern("tmpl", "pat")
        assert result is not None
        assert result.usage_count == 10
        assert result.success_count == 10

    @pytest.mark.asyncio
    async def test_whitespace_template_name(
        self,
        service: TemplateMetricsService,
    ) -> None:
        result = await service.record_usage(
            "   ", "pat", Decimal("0.5"), 100, True
        )
        assert result.template_name == "   "

    @pytest.mark.asyncio
    async def test_newline_in_pattern(
        self,
        service: TemplateMetricsService,
    ) -> None:
        result = await service.record_usage(
            "tmpl", "line1\nline2", Decimal("0.5"), 100, True
        )
        assert result.pattern == "line1\nline2"
