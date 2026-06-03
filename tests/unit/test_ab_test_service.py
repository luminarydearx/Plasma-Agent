import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
from plasmaagent.ai.templates.ab_test_service import ABTestService
from plasmaagent.ai.templates.ab_testing import (
    ABTestCreate, ABTest, ABTestResult, ABTestStats, ABTestAnalysis
)

class TestABTestServiceInit:
    def test_init_with_database(self):
        db = MagicMock()
        service = ABTestService(db)
        assert service._db == db

class TestCreateTest:
    @pytest.mark.asyncio
    async def test_create_test_success(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        
        version_a_id = uuid4()
        version_b_id = uuid4()
        
        cursor.fetchone.return_value = {
            'id': 1,
            'template_name': 'test_template',
            'version_a_id': version_a_id,
            'version_b_id': version_b_id,
            'status': 'active',
            'started_at': datetime.now(timezone.utc),
            'ended_at': None,
            'winner_version_id': None,
            'confidence_threshold': 0.95,
            'min_samples': 100
        }
        
        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.transaction.return_value = conn
        
        service = ABTestService(db)
        test_data = ABTestCreate(
            template_name='test_template',
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            confidence_threshold=0.95,
            min_samples=100
        )
        
        result = await service.create_test(test_data)
        
        assert isinstance(result, ABTest)
        assert result.template_name == 'test_template'
        assert result.version_a_id == version_a_id
        assert result.version_b_id == version_b_id
        assert result.status == 'active'

class TestRecordResult:
    @pytest.mark.asyncio
    async def test_record_result_success(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        
        version_id = uuid4()
        
        cursor.fetchone.return_value = {
            'id': 1,
            'ab_test_id': 1,
            'version_id': version_id,
            'success': True,
            'execution_time_ms': 150,
            'created_at': datetime.now(timezone.utc)
        }
        
        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.transaction.return_value = conn
        
        service = ABTestService(db)
        result = await service.record_result(
            ab_test_id=1,
            version_id=version_id,
            success=True,
            execution_time_ms=150
        )
        
        assert isinstance(result, ABTestResult)
        assert result.success is True
        assert result.execution_time_ms == 150

class TestGetTest:
    @pytest.mark.asyncio
    async def test_get_test_found(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        
        version_a_id = uuid4()
        version_b_id = uuid4()
        
        cursor.fetchone.return_value = {
            'id': 1,
            'template_name': 'test_template',
            'version_a_id': version_a_id,
            'version_b_id': version_b_id,
            'status': 'active',
            'started_at': datetime.now(timezone.utc),
            'ended_at': None,
            'winner_version_id': None,
            'confidence_threshold': 0.95,
            'min_samples': 100
        }
        
        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn
        
        service = ABTestService(db)
        result = await service.get_test(1)
        
        assert isinstance(result, ABTest)
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_get_test_not_found(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        
        cursor.fetchone.return_value = None
        
        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn
        
        service = ABTestService(db)
        result = await service.get_test(999)
        
        assert result is None

class TestListActiveTests:
    @pytest.mark.asyncio
    async def test_list_active_tests_empty(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        
        cursor.fetchall.return_value = []
        
        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn
        
        service = ABTestService(db)
        result = await service.list_active_tests()
        
        assert result == []

    @pytest.mark.asyncio
    async def test_list_active_tests_with_data(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        
        version_a_id = uuid4()
        version_b_id = uuid4()
        version_c_id = uuid4()
        version_d_id = uuid4()
        
        cursor.fetchall.return_value = [
            {
                'id': 1,
                'template_name': 'test1',
                'version_a_id': version_a_id,
                'version_b_id': version_b_id,
                'status': 'active',
                'started_at': datetime.now(timezone.utc),
                'ended_at': None,
                'winner_version_id': None,
                'confidence_threshold': 0.95,
                'min_samples': 100
            },
            {
                'id': 2,
                'template_name': 'test2',
                'version_a_id': version_c_id,
                'version_b_id': version_d_id,
                'status': 'active',
                'started_at': datetime.now(timezone.utc),
                'ended_at': None,
                'winner_version_id': None,
                'confidence_threshold': 0.95,
                'min_samples': 100
            }
        ]
        
        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn
        
        service = ABTestService(db)
        result = await service.list_active_tests()
        
        assert len(result) == 2
        assert all(isinstance(t, ABTest) for t in result)

class TestGetVersionStats:
    @pytest.mark.asyncio
    async def test_get_version_stats_empty(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        
        version_id = uuid4()
        
        cursor.fetchone.return_value = {
            'total_samples': 0,
            'successes': 0,
            'failures': 0,
            'avg_execution_time_ms': None
        }
        
        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn
        
        service = ABTestService(db)
        result = await service.get_version_stats(1, version_id)
        
        assert isinstance(result, ABTestStats)
        assert result.total_samples == 0
        assert result.success_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_version_stats_with_data(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        
        version_id = uuid4()
        
        cursor.fetchone.return_value = {
            'total_samples': 100,
            'successes': 80,
            'failures': 20,
            'avg_execution_time_ms': 150.5
        }
        
        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn
        
        service = ABTestService(db)
        result = await service.get_version_stats(1, version_id)
        
        assert result.total_samples == 100
        assert result.successes == 80
        assert result.failures == 20
        assert result.success_rate == 0.8
        assert result.avg_execution_time_ms == 150.5

class TestAnalyzeTest:
    @pytest.mark.asyncio
    async def test_analyze_test_not_found(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        
        cursor.fetchone.return_value = None
        
        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn
        
        service = ABTestService(db)
        result = await service.analyze_test(999)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_test_insufficient_data(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        
        version_a_id = uuid4()
        version_b_id = uuid4()
        
        test_row = {
            'id': 1,
            'template_name': 'test_template',
            'version_a_id': version_a_id,
            'version_b_id': version_b_id,
            'status': 'active',
            'started_at': datetime.now(timezone.utc),
            'ended_at': None,
            'winner_version_id': None,
            'confidence_threshold': 0.95,
            'min_samples': 100
        }
        
        stats_row = {
            'total_samples': 10,
            'successes': 8,
            'failures': 2,
            'avg_execution_time_ms': 150.0
        }
        
        cursor.fetchone.side_effect = [test_row, stats_row, stats_row]
        
        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn
        
        service = ABTestService(db)
        result = await service.analyze_test(1)
        
        assert isinstance(result, ABTestAnalysis)
        assert result.winner_version_id is None
        assert result.recommendation == "Insufficient data"

class TestCompleteTest:
    @pytest.mark.asyncio
    async def test_complete_test_success(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        
        version_a_id = uuid4()
        version_b_id = uuid4()
        
        cursor.fetchone.return_value = {
            'id': 1,
            'template_name': 'test_template',
            'version_a_id': version_a_id,
            'version_b_id': version_b_id,
            'status': 'completed',
            'started_at': datetime.now(timezone.utc),
            'ended_at': datetime.now(timezone.utc),
            'winner_version_id': version_a_id,
            'confidence_threshold': 0.95,
            'min_samples': 100
        }
        
        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.transaction.return_value = conn
        
        service = ABTestService(db)
        result = await service.complete_test(1, version_a_id)
        
        assert isinstance(result, ABTest)
        assert result.status == 'completed'
        assert result.winner_version_id == version_a_id

    @pytest.mark.asyncio
    async def test_complete_test_not_found(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        
        cursor.fetchone.return_value = None
        
        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.transaction.return_value = conn
        
        service = ABTestService(db)
        result = await service.complete_test(999, uuid4())
        
        assert result is None

class TestStatisticalMethods:
    def test_calculate_confidence_interval_zero_samples(self):
        db = MagicMock()
        service = ABTestService(db)
        result = service._calculate_confidence_interval(0, 0)
        assert result == 0.0

    def test_calculate_confidence_interval_with_data(self):
        db = MagicMock()
        service = ABTestService(db)
        result = service._calculate_confidence_interval(80, 100)
        assert 0.0 < result < 0.2

    def test_calculate_z_score_zero_samples(self):
        db = MagicMock()
        service = ABTestService(db)
        result = service._calculate_z_score(0, 0, 0, 0)
        assert result == 0.0

    def test_calculate_z_score_with_data(self):
        db = MagicMock()
        service = ABTestService(db)
        result = service._calculate_z_score(80, 100, 60, 100)
        assert result > 0.0

    def test_z_to_confidence_high(self):
        db = MagicMock()
        service = ABTestService(db)
        assert service._z_to_confidence(3.5) == 0.999
        assert service._z_to_confidence(2.6) == 0.99
        assert service._z_to_confidence(2.0) == 0.95

    def test_z_to_confidence_low(self):
        db = MagicMock()
        service = ABTestService(db)
        result = service._z_to_confidence(0.5)
        assert 0.50 <= result < 0.80

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_concurrent_result_recording(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        
        version_id = uuid4()
        
        cursor.fetchone.return_value = {
            'id': 1,
            'ab_test_id': 1,
            'version_id': version_id,
            'success': True,
            'execution_time_ms': 150,
            'created_at': datetime.now(timezone.utc)
        }
        
        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.transaction.return_value = conn
        
        service = ABTestService(db)
        
        import asyncio
        tasks = [
            service.record_result(1, version_id, True, 150)
            for _ in range(10)
        ]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
        assert all(isinstance(r, ABTestResult) for r in results)

    def test_statistical_edge_cases(self):
        db = MagicMock()
        service = ABTestService(db)
        
        assert service._calculate_z_score(50, 100, 50, 100) == 0.0
        
        assert service._calculate_confidence_interval(100, 100) >= 0.0
        assert service._calculate_confidence_interval(0, 100) >= 0.0
        assert service._calculate_confidence_interval(50, 100) > 0.0
