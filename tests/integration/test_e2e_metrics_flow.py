from decimal import Decimal

import pytest

from plasmaagent.core.database import get_database
from plasmaagent.services.task_generator import TaskGeneratorService
from plasmaagent.services.template_metrics_service import TemplateMetricsService


@pytest.fixture
async def services():
    db = get_database()
    await db.connect()
    generator = TaskGeneratorService(db)
    metrics = TemplateMetricsService(db)
    yield generator, metrics
    await db.disconnect()


class TestEndToEndMetricsFlow:
    async def test_generate_records_metrics(self, services):
        generator, metrics_service = services

        response = await generator.generate_from_natural_language(
            "backup database postgresql plasmaagent"
        )

        assert len(response.tasks) == 1
        task = response.tasks[0]
        assert task.template_used == "backup_database"

        metric = await metrics_service.get_by_name("backup_database")
        assert metric is not None
        assert metric.usage_count >= 1
        assert metric.avg_confidence >= Decimal("0.90")

    async def test_multiple_generations_accumulate(self, services):
        generator, metrics_service = services

        for _ in range(3):
            await generator.generate_from_natural_language(
                "cleanup old files in C:\\Temp"
            )

        metric = await metrics_service.get_by_name("cleanup_files")
        assert metric is not None
        assert metric.usage_count >= 3

    async def test_all_patterns_record_metrics(self, services):
        generator, metrics_service = services

        test_cases = [
            ("backup database postgresql", "backup_database"),
            ("cleanup old files", "cleanup_files"),
            ("check disk space", "disk_monitoring"),
            ("git commit changes", "git_operations"),
            ("show system info", "system_info"),
        ]

        for input_text, expected_template in test_cases:
            response = await generator.generate_from_natural_language(input_text)
            assert len(response.tasks) >= 1, f"No task generated for: {input_text}"
            
            task = response.tasks[0]
            assert task.template_used == expected_template

        for _, template_name in test_cases:
            metric = await metrics_service.get_by_name(template_name)
            assert metric is not None, f"Metrics not recorded for: {template_name}"
            assert metric.usage_count >= 1

    async def test_no_match_does_not_crash(self, services):
        generator, metrics_service = services

        response = await generator.generate_from_natural_language(
            "completely random gibberish xyz abc 123"
        )

        assert len(response.tasks) == 0

        stats = await metrics_service.get_aggregate_stats()
        assert stats["total_templates"] >= 0

    async def test_concurrent_generations(self, services):
        import asyncio

        generator, metrics_service = services

        async def generate():
            return await generator.generate_from_natural_language(
                "backup mysql database testdb"
            )

        tasks = [generate() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        for result in results:
            assert len(result.tasks) >= 1

        metric = await metrics_service.get_by_name("backup_database")
        assert metric is not None
        assert metric.usage_count >= 5
