import pytest
import time
from uuid import uuid4
from plasmaagent.core.database import Database
from plasmaagent.ai.templates.learner import TemplateLearner
from plasmaagent.ai.templates.versioning import TemplateVersionService
from plasmaagent.ai.templates.ab_test_service import ABTestService
from plasmaagent.ai.templates.retirement_service import RetirementService
from plasmaagent.ai.templates.auto_generator_service import AutoTemplateGenerator
from plasmaagent.ai.templates.ab_testing import ABTestCreate
from plasmaagent.ai.templates.retirement import (
    TemplateRetirementCreate,
    RetirementScanRequest,
)
from plasmaagent.ai.templates.auto_generator import (
    TemplateCandidateCreate,
    CandidateDetectionRequest,
)


@pytest.mark.asyncio
class TestSubPhase36EndToEnd:
    @pytest.fixture
    async def db(self):
        database = Database()
        await database.connect()
        yield database
        await database.disconnect()

    async def test_full_template_evolution_lifecycle(self, db):
        from plasmaagent.ai.templates.models import TemplateVersionCreate

        auto_gen = AutoTemplateGenerator(db)
        versioning = TemplateVersionService(db)
        ab_service = ABTestService(db)
        retirement = RetirementService(db)

        uid = uuid4().hex[:8]
        pattern_name = f"lifecycle_{uid}"
        template_name = f"lifecycle_tmpl_{uid}"
        v1_pattern = f"lifecycle_v1_{uid}"
        v2_pattern = f"lifecycle_v2_{uid}"

        task_id = uuid4()
        async with db.transaction() as conn:
            await conn.execute(
                "INSERT INTO tasks (id, name, status, payload) VALUES (%s, %s, 'COMPLETED', %s)",
                (task_id, f"lifecycle_{uid}", f'{{"commands": ["echo {uid}"]}}'),
            )

        try:
            candidate = await auto_gen.create_candidate(
                TemplateCandidateCreate(
                    pattern=pattern_name,
                    example_input="lifecycle test",
                    generated_commands=["echo lifecycle"],
                    confidence=0.85,
                    frequency=5,
                    source_task_id=task_id,
                )
            )
            assert candidate.status == "pending"

            approved = await auto_gen.approve_candidate(candidate.id, template_name)
            assert approved is not None
            assert approved.status == "approved"

            async with db.connection() as conn:
                cursor = await conn.execute(
                    "SELECT id FROM template_metrics WHERE template_name = %s",
                    (template_name,),
                )
                row = await cursor.fetchone()
                assert row is not None
                template_uuid = row["id"]

            v1 = await versioning.create_version(
                TemplateVersionCreate(
                    template_id=template_uuid,
                    commands=("echo v1",),
                    pattern_name=v1_pattern,
                    confidence=0.8,
                )
            )
            assert v1.version_number == 1

            v2 = await versioning.create_version(
                TemplateVersionCreate(
                    template_id=template_uuid,
                    commands=("echo v1", "echo v2"),
                    pattern_name=v2_pattern,
                    confidence=0.9,
                )
            )
            assert v2.version_number == 2

            ab_test = await ab_service.create_test(
                ABTestCreate(
                    template_name=template_name,
                    version_a_id=v1.id,
                    version_b_id=v2.id,
                    confidence_threshold=0.90,
                    min_samples=10,
                )
            )
            assert ab_test.status == "active"

            for i in range(10):
                await ab_service.record_result(ab_test.id, v1.id, True, 100)
                await ab_service.record_result(ab_test.id, v2.id, i < 3, 150)

            analysis = await ab_service.analyze_test(ab_test.id)
            assert analysis is not None

            await retirement.retire_template(
                TemplateRetirementCreate(
                    template_name=template_name,
                    reason="End-of-life test",
                    success_rate=0.6,
                    total_uses=10,
                )
            )
            assert await retirement.is_retired(template_name)
        finally:
            async with db.transaction() as conn:
                await conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
                await conn.execute(
                    "DELETE FROM template_candidates WHERE pattern = %s",
                    (pattern_name,),
                )
                await conn.execute(
                    "DELETE FROM template_retirements WHERE template_name = %s",
                    (template_name,),
                )
                await conn.execute(
                    "DELETE FROM ab_tests WHERE template_name = %s",
                    (template_name,),
                )
                await conn.execute(
                    "DELETE FROM template_versions WHERE template_id = %s",
                    (template_uuid,),
                )
                await conn.execute(
                    "DELETE FROM template_metrics WHERE template_name = %s",
                    (template_name,),
                )


@pytest.mark.asyncio
class TestSubPhase36Stress:
    @pytest.fixture
    async def db(self):
        database = Database()
        await database.connect()
        yield database
        await database.disconnect()

    async def test_stress_100_candidates(self, db):
        auto_gen = AutoTemplateGenerator(db)

        start = time.perf_counter()
        for i in range(100):
            await auto_gen.create_candidate(
                TemplateCandidateCreate(
                    pattern=f"stress_pattern_{i:04d}",
                    example_input=f"stress test {i}",
                    generated_commands=[f"echo stress_{i}"],
                    confidence=0.7,
                    frequency=3,
                )
            )
        elapsed = time.perf_counter() - start
        assert elapsed < 30.0

        candidates = await auto_gen.list_candidates(limit=100)
        assert len(candidates) >= 100

        async with db.transaction() as conn:
            await conn.execute(
                "DELETE FROM template_candidates WHERE pattern LIKE 'stress_pattern_%'"
            )

    async def test_stress_100_retirements(self, db):
        retirement = RetirementService(db)

        start = time.perf_counter()
        for i in range(100):
            await retirement.retire_template(
                TemplateRetirementCreate(
                    template_name=f"stress_retire_{i:04d}",
                    reason="Stress test",
                    success_rate=0.3,
                    total_uses=5,
                )
            )
        elapsed = time.perf_counter() - start
        assert elapsed < 30.0

        retirements = await retirement.list_retirements(limit=100)
        assert len(retirements) >= 100

        async with db.transaction() as conn:
            await conn.execute(
                "DELETE FROM template_retirements WHERE template_name LIKE 'stress_retire_%'"
            )


@pytest.mark.asyncio
class TestSubPhase36Security:
    @pytest.fixture
    async def db(self):
        database = Database()
        await database.connect()
        yield database
        await database.disconnect()

    async def test_cross_table_sql_injection_safe(self, db):
        auto_gen = AutoTemplateGenerator(db)
        retirement = RetirementService(db)

        injection = f"inj_{uuid4().hex[:12]}'; DROP TABLE template_candidates;--"

        candidate = await auto_gen.create_candidate(
            TemplateCandidateCreate(
                pattern=injection,
                example_input="injection test",
                generated_commands=["safe_cmd"],
                confidence=0.8,
                frequency=3,
            )
        )
        assert candidate.pattern == injection

        retired = await retirement.retire_template(
            TemplateRetirementCreate(
                template_name=injection,
                reason="Security test",
                success_rate=0.5,
                total_uses=10,
            )
        )
        assert retired.template_name == injection

        async with db.connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) AS cnt FROM template_candidates WHERE pattern = %s",
                (injection,),
            )
            row = await cursor.fetchone()
            assert row["cnt"] == 1

            cursor = await conn.execute(
                "SELECT COUNT(*) AS cnt FROM template_retirements WHERE template_name = %s",
                (injection,),
            )
            row = await cursor.fetchone()
            assert row["cnt"] == 1

            cursor = await conn.execute(
                "SELECT COUNT(*) AS cnt FROM information_schema.tables WHERE table_name = 'template_candidates'"
            )
            row = await cursor.fetchone()
            assert row["cnt"] == 1

        async with db.transaction() as conn:
            await conn.execute(
                "DELETE FROM template_candidates WHERE pattern = %s", (injection,)
            )
            await conn.execute(
                "DELETE FROM template_retirements WHERE template_name = %s",
                (injection,),
            )

    async def test_xss_in_pattern_safe(self, db):
        auto_gen = AutoTemplateGenerator(db)

        xss = '<script>alert("xss")</script>'
        candidate = await auto_gen.create_candidate(
            TemplateCandidateCreate(
                pattern=xss,
                example_input="xss test",
                generated_commands=["safe_cmd"],
                confidence=0.8,
                frequency=3,
            )
        )
        assert candidate.pattern == xss

        async with db.transaction() as conn:
            await conn.execute(
                "DELETE FROM template_candidates WHERE pattern = %s", (xss,)
            )

    async def test_isolation_between_services(self, db):
        auto_gen = AutoTemplateGenerator(db)
        retirement = RetirementService(db)

        shared_pattern = f"isolation_test_pattern_{uuid4().hex[:8]}"

        created_candidate = await auto_gen.create_candidate(
            TemplateCandidateCreate(
                pattern=shared_pattern,
                example_input="isolation test",
                generated_commands=["echo isolated"],
                confidence=0.9,
                frequency=10,
            )
        )
        assert created_candidate is not None

        retired = await retirement.retire_template(
            TemplateRetirementCreate(
                template_name=shared_pattern,
                reason="Isolation test",
                success_rate=0.4,
                total_uses=8,
            )
        )
        assert retired is not None

        candidates = await auto_gen.list_candidates(limit=500)
        candidate_patterns = [c.pattern for c in candidates]
        assert shared_pattern in candidate_patterns

        async with db.transaction() as conn:
            await conn.execute(
                "DELETE FROM template_candidates WHERE pattern = %s",
                (shared_pattern,),
            )
            await conn.execute(
                "DELETE FROM template_retirements WHERE template_name = %s",
                (shared_pattern,),
            )


@pytest.mark.asyncio
class TestSubPhase36Performance:
    @pytest.fixture
    async def db(self):
        database = Database()
        await database.connect()
        yield database
        await database.disconnect()

    async def test_list_candidates_performance(self, db):
        auto_gen = AutoTemplateGenerator(db)

        for i in range(50):
            await auto_gen.create_candidate(
                TemplateCandidateCreate(
                    pattern=f"perf_candidate_{i:04d}_{uuid4().hex[:6]}",
                    example_input=f"perf test {i}",
                    generated_commands=[f"echo perf_{i}"],
                    confidence=0.75,
                    frequency=5,
                )
            )

        start = time.perf_counter()
        candidates = await auto_gen.list_candidates(limit=50)
        elapsed = time.perf_counter() - start

        assert len(candidates) >= 50
        assert elapsed < 2.0

        async with db.transaction() as conn:
            await conn.execute(
                "DELETE FROM template_candidates WHERE pattern LIKE 'perf_candidate_%'"
            )

    async def test_retirement_scan_performance(self, db):
        retirement = RetirementService(db)

        for i in range(30):
            await retirement.retire_template(
                TemplateRetirementCreate(
                    template_name=f"perf_retire_{i:04d}_{uuid4().hex[:6]}",
                    reason="Performance test",
                    success_rate=0.2,
                    total_uses=3,
                )
            )

        start = time.perf_counter()
        request = RetirementScanRequest(success_rate_threshold=0.5, min_uses=2)
        scan_result = await retirement.scan_and_retire(request)
        elapsed = time.perf_counter() - start

        assert scan_result is not None
        assert elapsed < 5.0

        async with db.transaction() as conn:
            await conn.execute(
                "DELETE FROM template_retirements WHERE template_name LIKE 'perf_retire_%'"
            )


@pytest.mark.asyncio
class TestSubPhase36CrossPhaseRegression:
    @pytest.fixture
    async def db(self):
        database = Database()
        await database.connect()
        yield database
        await database.disconnect()

    async def test_phase1_tasks_still_work(self, db):
        task_id = uuid4()
        async with db.transaction() as conn:
            await conn.execute(
                "INSERT INTO tasks (id, name, status) VALUES (%s, %s, 'PENDING')",
                (task_id, f"phase1_regression_{uuid4().hex[:8]}"),
            )
            cursor = await conn.execute(
                "SELECT status FROM tasks WHERE id = %s", (task_id,)
            )
            row = await cursor.fetchone()
            assert row["status"] == "PENDING"
            await conn.execute(
                "UPDATE tasks SET status = 'RUNNING' WHERE id = %s", (task_id,)
            )
            await conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,))

    async def test_phase2_execution_still_works(self, db):
        task_id = uuid4()
        async with db.transaction() as conn:
            await conn.execute(
                "INSERT INTO tasks (id, name, status, payload) VALUES (%s, %s, 'PENDING', %s)",
                (
                    task_id,
                    f"phase2_regression_{uuid4().hex[:8]}",
                    '{"commands": ["echo test"]}',
                ),
            )
            await conn.execute(
                """
                INSERT INTO task_steps (id, task_id, step_order, command, status)
                VALUES (%s, %s, 1, 'echo test', 'COMPLETED')
                """,
                (uuid4(), task_id),
            )
            await conn.execute("DELETE FROM task_steps WHERE task_id = %s", (task_id,))
            await conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,))

    async def test_phase3_4_metrics_still_work(self, db):
        async with db.connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) AS cnt FROM template_metrics"
            )
            row = await cursor.fetchone()
            assert row["cnt"] >= 0

    async def test_phase3_5_decomposer_still_works(self, db):
        from plasmaagent.ai.decomposer import TaskDecomposer

        decomposer = TaskDecomposer()
        result = decomposer.decompose("backup database then send notification")
        assert len(result.sub_tasks) >= 2

