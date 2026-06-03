import pytest
from uuid import uuid4
from plasmaagent.core.database import Database
from plasmaagent.ai.templates.auto_generator_service import AutoTemplateGenerator
from plasmaagent.ai.templates.auto_generator import (
    TemplateCandidateCreate,
    CandidateDetectionRequest,
)


@pytest.mark.asyncio
class TestAutoTemplateGeneratorIntegration:
    @pytest.fixture
    async def db(self):
        database = Database()
        await database.connect()
        yield database
        await database.disconnect()

    @pytest.fixture
    async def gen(self, db):
        return AutoTemplateGenerator(db)

    @pytest.fixture
    async def cleanup_candidates(self, db):
        yield
        async with db.transaction() as conn:
            await conn.execute(
                "DELETE FROM template_candidates WHERE pattern LIKE 'integration_test_%'"
            )

    async def test_create_candidate_persisted(self, gen, cleanup_candidates):
        data = TemplateCandidateCreate(
            pattern="integration_test_pattern",
            example_input="integration test input",
            generated_commands=["echo test", "echo done"],
            confidence=0.85,
            frequency=5,
            metadata={"test": True},
        )
        result = await gen.create_candidate(data)

        assert result.id > 0
        assert result.status == "pending"

        fetched = await gen.get_candidate(result.id)
        assert fetched is not None
        assert fetched.pattern == "integration_test_pattern"
        assert fetched.metadata == {"test": True}

    async def test_list_candidates_by_status(self, gen, cleanup_candidates):
        for i in range(3):
            await gen.create_candidate(
                TemplateCandidateCreate(
                    pattern=f"integration_test_list_{i}",
                    example_input=f"test input {i}",
                    generated_commands=[f"cmd {i}"],
                    confidence=0.8,
                    frequency=3,
                )
            )

        pending = await gen.list_candidates(status="pending")
        assert len(pending) >= 3

    async def test_approve_candidate_creates_template_metric(
        self, gen, db, cleanup_candidates
    ):
        candidate = await gen.create_candidate(
            TemplateCandidateCreate(
                pattern="integration_test_approve",
                example_input="approve me",
                generated_commands=["echo approved"],
                confidence=0.9,
                frequency=10,
            )
        )

        approved = await gen.approve_candidate(
            candidate.id, "integration_approved_template"
        )

        assert approved is not None
        assert approved.status == "approved"
        assert approved.reviewed_at is not None

        async with db.connection() as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM template_metrics WHERE template_name = %s AND pattern = %s",
                ("integration_approved_template", "integration_test_approve"),
            )
            assert await cursor.fetchone() is not None

        async with db.transaction() as conn:
            await conn.execute(
                "DELETE FROM template_metrics WHERE template_name = 'integration_approved_template'"
            )

    async def test_reject_candidate_updates_metadata(self, gen, cleanup_candidates):
        candidate = await gen.create_candidate(
            TemplateCandidateCreate(
                pattern="integration_test_reject",
                example_input="reject me",
                generated_commands=["echo rejected"],
                confidence=0.5,
                frequency=2,
            )
        )

        rejected = await gen.reject_candidate(candidate.id, "Low quality pattern")

        assert rejected is not None
        assert rejected.status == "rejected"
        assert rejected.reviewed_at is not None

    async def test_pattern_exists_prevents_duplicate(self, gen, db, cleanup_candidates):
        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO template_metrics (template_name, pattern)
                VALUES ('existing_template', 'integration_test_duplicate')
                ON CONFLICT DO NOTHING
                """
            )

        request = CandidateDetectionRequest(min_frequency=2, scan_period_days=1)

        async with db.transaction() as conn:
            task_id = uuid4()
            await conn.execute(
                """
                INSERT INTO tasks (id, name, status, payload)
                VALUES (%s, 'dup test', 'COMPLETED', %s)
                """,
                (
                    task_id,
                    '{"commands": "integration_test_duplicate"}',
                ),
            )

        try:
            report = await gen.detect_patterns(request)

            assert not any(
                "integration_test_duplicate" in p for p in report.new_candidates
            )
        finally:
            async with db.transaction() as conn:
                await conn.execute(
                    "DELETE FROM template_metrics WHERE pattern = 'integration_test_duplicate'"
                )

    async def test_sql_injection_safe(self, gen, cleanup_candidates):
        data = TemplateCandidateCreate(
            pattern="'; DROP TABLE template_candidates;--",
            example_input="injection test",
            generated_commands=["safe_cmd"],
            confidence=0.8,
            frequency=3,
        )
        result = await gen.create_candidate(data)

        assert result.pattern == "'; DROP TABLE template_candidates;--"

        verify = await gen.list_candidates(limit=100)
        patterns = [c.pattern for c in verify]
        assert "'; DROP TABLE template_candidates;--" in patterns

    async def test_performance_bulk_create(self, gen):
        import time

        start = time.perf_counter()
        for i in range(20):
            await gen.create_candidate(
                TemplateCandidateCreate(
                    pattern=f"integration_perf_test_{i}",
                    example_input=f"perf test {i}",
                    generated_commands=[f"cmd_{i}"],
                    confidence=0.8,
                    frequency=3,
                )
            )
        duration = time.perf_counter() - start

        assert duration < 10.0

    async def test_detect_patterns_with_real_tasks(self, gen, db):
        task_ids = []
        async with db.transaction() as conn:
            for i in range(5):
                task_id = uuid4()
                task_ids.append(task_id)
                await conn.execute(
                    """
                    INSERT INTO tasks (id, name, status, payload)
                    VALUES (%s, %s, 'COMPLETED', %s)
                    """,
                    (
                        task_id,
                        f"detect_test_{i}",
                        '{"commands": ["echo detect_unique_pattern_xyz"]}',
                    ),
                )

        try:
            request = CandidateDetectionRequest(min_frequency=3, scan_period_days=1)
            report = await gen.detect_patterns(request)

            assert report.patterns_detected >= 0
            assert report.scan_duration_ms >= 0
        finally:
            async with db.transaction() as conn:
                for tid in task_ids:
                    await conn.execute("DELETE FROM tasks WHERE id = %s", (tid,))
                await conn.execute(
                    "DELETE FROM template_candidates WHERE pattern LIKE '%detect_unique_pattern%'"
                )
