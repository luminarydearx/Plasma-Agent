import pytest
from uuid import uuid4
from plasmaagent.core.database import Database
from plasmaagent.ai.templates.ab_test_service import ABTestService
from plasmaagent.ai.templates.ab_testing import ABTestCreate

@pytest.mark.asyncio
class TestABTestServiceIntegration:
    @pytest.fixture
    async def db(self):
        database = Database()
        await database.connect()
        yield database
        await database.disconnect()

    @pytest.fixture
    async def service(self, db):
        return ABTestService(db)

    @pytest.fixture
    async def template_versions(self, db):
        template_id = uuid4()
        version_a_id = uuid4()
        version_b_id = uuid4()
        
        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO template_metrics (id, template_name, pattern)
                VALUES (%s, 'test_template', 'pattern.*')
                """,
                (template_id,)
            )
            
            await conn.execute(
                """
                INSERT INTO template_versions (id, template_id, version_number, commands, pattern_name, confidence)
                VALUES (%s, %s, 1, '["cmd1"]', 'pattern1', 0.9)
                """,
                (version_a_id, template_id)
            )
            
            await conn.execute(
                """
                INSERT INTO template_versions (id, template_id, version_number, commands, pattern_name, confidence)
                VALUES (%s, %s, 2, '["cmd2"]', 'pattern2', 0.9)
                """,
                (version_b_id, template_id)
            )
        
        yield version_a_id, version_b_id, template_id
        
        async with db.transaction() as conn:
            await conn.execute(
                "DELETE FROM ab_test_results WHERE ab_test_id IN (SELECT id FROM ab_tests WHERE version_a_id = %s OR version_b_id = %s)",
                (version_a_id, version_b_id)
            )
            await conn.execute(
                "DELETE FROM ab_tests WHERE version_a_id = %s OR version_b_id = %s",
                (version_a_id, version_b_id)
            )
            await conn.execute(
                "DELETE FROM template_versions WHERE id IN (%s, %s)",
                (version_a_id, version_b_id)
            )
            await conn.execute(
                "DELETE FROM template_metrics WHERE id = %s",
                (template_id,)
            )

    async def test_create_ab_test(self, service, template_versions):
        version_a_id, version_b_id, _ = template_versions
        
        test_data = ABTestCreate(
            template_name='test_template',
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            confidence_threshold=0.95,
            min_samples=10
        )
        
        result = await service.create_test(test_data)
        
        assert result.id > 0
        assert result.template_name == 'test_template'
        assert result.version_a_id == version_a_id
        assert result.version_b_id == version_b_id
        assert result.status == 'active'

    async def test_record_results_and_analyze(self, service, template_versions):
        version_a_id, version_b_id, _ = template_versions
        
        test_data = ABTestCreate(
            template_name='test_template',
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            confidence_threshold=0.95,
            min_samples=10
        )
        
        test = await service.create_test(test_data)
        
        for i in range(10):
            await service.record_result(test.id, version_a_id, True, 100)
            await service.record_result(test.id, version_b_id, i < 5, 150)
        
        stats_a = await service.get_version_stats(test.id, version_a_id)
        stats_b = await service.get_version_stats(test.id, version_b_id)
        
        assert stats_a.total_samples == 10
        assert stats_a.successes == 10
        assert stats_a.success_rate == 1.0
        
        assert stats_b.total_samples == 10
        assert stats_b.successes == 5
        assert stats_b.success_rate == 0.5
        
        analysis = await service.analyze_test(test.id)
        
        assert analysis is not None
        assert analysis.winner_version_id == version_a_id
        assert analysis.is_significant is True
        assert 'wins' in analysis.recommendation.lower()

    async def test_complete_test(self, service, template_versions):
        version_a_id, version_b_id, _ = template_versions
        
        test_data = ABTestCreate(
            template_name='test_template',
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            confidence_threshold=0.95,
            min_samples=10
        )
        
        test = await service.create_test(test_data)
        
        completed = await service.complete_test(test.id, version_a_id)
        
        assert completed is not None
        assert completed.status == 'completed'
        assert completed.winner_version_id == version_a_id
        assert completed.ended_at is not None

    async def test_list_active_tests(self, service, template_versions):
        version_a_id, version_b_id, _ = template_versions
        
        test_data = ABTestCreate(
            template_name='test_template',
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            confidence_threshold=0.95,
            min_samples=10
        )
        
        await service.create_test(test_data)
        await service.create_test(test_data)
        
        active_tests = await service.list_active_tests()
        
        assert len(active_tests) >= 2
        assert all(t.status == 'active' for t in active_tests)

    async def test_insufficient_data_analysis(self, service, template_versions):
        version_a_id, version_b_id, _ = template_versions
        
        test_data = ABTestCreate(
            template_name='test_template',
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            confidence_threshold=0.95,
            min_samples=100
        )
        
        test = await service.create_test(test_data)
        
        for i in range(5):
            await service.record_result(test.id, version_a_id, True, 100)
            await service.record_result(test.id, version_b_id, True, 150)
        
        analysis = await service.analyze_test(test.id)
        
        assert analysis is not None
        assert analysis.winner_version_id is None
        assert analysis.is_significant is False
        assert 'insufficient' in analysis.recommendation.lower()

    async def test_concurrent_result_recording(self, service, template_versions):
        version_a_id, version_b_id, _ = template_versions
        
        test_data = ABTestCreate(
            template_name='test_template',
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            confidence_threshold=0.95,
            min_samples=10
        )
        
        test = await service.create_test(test_data)
        
        import asyncio
        tasks = [
            service.record_result(test.id, version_a_id, True, 100)
            for _ in range(20)
        ]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 20
        
        stats = await service.get_version_stats(test.id, version_a_id)
        assert stats.total_samples == 20
