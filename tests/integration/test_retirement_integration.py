import pytest
from plasmaagent.core.database import Database
from plasmaagent.ai.templates.retirement_service import RetirementService
from plasmaagent.ai.templates.retirement import (
    TemplateRetirementCreate,
    RetirementScanRequest,
)


@pytest.mark.asyncio
class TestRetirementServiceIntegration:
    @pytest.fixture
    async def db(self):
        database = Database()
        await database.connect()
        yield database
        await database.disconnect()

    @pytest.fixture
    async def service(self, db):
        return RetirementService(db)

    @pytest.fixture
    async def seed_metrics(self, db):
        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO template_metrics 
                    (template_name, pattern, usage_count, success_count, failure_count,
                     total_generation_time_ms)
                VALUES 
                    ('bad_template', 'bad.*', 5, 1, 4, 500),
                    ('good_template', 'good.*', 5, 5, 0, 500)
                """
            )
        yield
        async with db.transaction() as conn:
            await conn.execute(
                "DELETE FROM template_retirements WHERE template_name IN ('bad_template', 'good_template')"
            )
            await conn.execute(
                "DELETE FROM template_metrics WHERE template_name IN ('bad_template', 'good_template')"
            )

    async def test_retire_template_persisted(self, service):
        data = TemplateRetirementCreate(
            template_name="integration_test_template",
            pattern="test.*",
            reason="Integration test",
            success_rate=0.3,
            total_uses=20,
            avg_execution_time_ms=500.0,
            metadata={"test": True},
        )
        result = await service.retire_template(data)

        assert result.id > 0
        assert result.template_name == "integration_test_template"

        fetched = await service.get_retirement(result.id)
        assert fetched is not None
        assert fetched.template_name == "integration_test_template"
        assert fetched.metadata == {"test": True}

    async def test_is_retired_after_retirement(self, service):
        data = TemplateRetirementCreate(
            template_name="retired_check_template",
            reason="Check retirement status",
            success_rate=0.2,
            total_uses=15,
        )
        await service.retire_template(data)

        assert await service.is_retired("retired_check_template") is True
        assert await service.is_retired("nonexistent_template") is False

    async def test_list_retirements_ordered(self, service):
        for i in range(3):
            await service.retire_template(
                TemplateRetirementCreate(
                    template_name=f"list_test_{i}",
                    reason=f"List test {i}",
                    success_rate=0.1 * (i + 1),
                    total_uses=10 + i,
                )
            )

        result = await service.list_retirements(limit=3)
        assert len(result) == 3
        assert result[0].retired_at >= result[1].retired_at

    async def test_find_candidates_with_real_metrics(self, service, seed_metrics):
        request = RetirementScanRequest(
            success_rate_threshold=0.5,
            min_uses_threshold=5,
            scan_period_days=1,
        )
        candidates = await service.find_retirement_candidates(request)

        assert any(c["template_name"] == "bad_template" for c in candidates)
        assert not any(c["template_name"] == "good_template" for c in candidates)

    async def test_scan_and_retire_end_to_end(self, service, seed_metrics):
        request = RetirementScanRequest(
            success_rate_threshold=0.5,
            min_uses_threshold=5,
            scan_period_days=1,
        )
        report = await service.scan_and_retire(request)

        assert report.candidates_found >= 1
        assert report.retired_count >= 1
        assert "bad_template" in report.retired_templates
        assert "good_template" not in report.retired_templates
        assert report.scan_duration_ms >= 0

    async def test_scan_does_not_double_retire(self, service, seed_metrics):
        request = RetirementScanRequest(
            success_rate_threshold=0.5,
            min_uses_threshold=5,
            scan_period_days=1,
        )

        report1 = await service.scan_and_retire(request)
        report2 = await service.scan_and_retire(request)

        assert report1.retired_count >= 1
        assert report2.retired_count == 0
        assert report2.skipped_count >= 1

    async def test_retirement_stats_aggregation(self, service):
        for i in range(3):
            await service.retire_template(
                TemplateRetirementCreate(
                    template_name=f"stats_template_{i}",
                    reason="Stats test",
                    success_rate=0.1 * (i + 1),
                    total_uses=10,
                )
            )

        stats = await service.get_retirement_stats()

        assert stats["total_retired"] >= 3
        assert stats["unique_templates"] >= 3
        assert stats["avg_success_rate_at_retirement"] > 0
        assert stats["first_retirement"] is not None
        assert stats["last_retirement"] is not None

    async def test_security_sql_injection_safe(self, service):
        data = TemplateRetirementCreate(
            template_name="'; DROP TABLE template_retirements;--",
            reason="Injection test",
            success_rate=0.5,
            total_uses=10,
        )
        result = await service.retire_template(data)

        assert result.template_name == "'; DROP TABLE template_retirements;--"

        verify = await service.list_retirements(limit=100)
        names = [r.template_name for r in verify]
        assert "'; DROP TABLE template_retirements;--" in names

    async def test_performance_bulk_retirements(self, service):
        import time

        start = time.perf_counter()
        for i in range(20):
            await service.retire_template(
                TemplateRetirementCreate(
                    template_name=f"perf_test_{i}",
                    reason="Performance test",
                    success_rate=0.3,
                    total_uses=10,
                )
            )
        duration = time.perf_counter() - start

        assert duration < 10.0

        stats = await service.get_retirement_stats()
        assert stats["total_retired"] >= 20
