import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta
from plasmaagent.observability.health import HealthStatus, HealthChecker


class TestHealthStatus:
    def test_valid_healthy_status(self):
        status = HealthStatus(
            status="healthy",
            timestamp=datetime.utcnow(),
            uptime_seconds=3600.0,
            message="All systems operational"
        )
        assert status.status == "healthy"
        assert status.uptime_seconds == 3600.0
        assert status.version == "1.0.0"
        assert status.checks == {}

    def test_valid_degraded_status(self):
        status = HealthStatus(
            status="degraded",
            timestamp=datetime.utcnow(),
            uptime_seconds=1800.0,
            message="Some services degraded"
        )
        assert status.status == "degraded"

    def test_valid_unhealthy_status(self):
        status = HealthStatus(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            uptime_seconds=100.0,
            message="Critical failure"
        )
        assert status.status == "unhealthy"

    def test_invalid_status(self):
        with pytest.raises(Exception):
            HealthStatus(
                status="invalid",
                timestamp=datetime.utcnow(),
                uptime_seconds=100.0
            )

    def test_negative_uptime(self):
        with pytest.raises(Exception):
            HealthStatus(
                status="healthy",
                timestamp=datetime.utcnow(),
                uptime_seconds=-100.0
            )

    def test_with_checks(self):
        status = HealthStatus(
            status="healthy",
            timestamp=datetime.utcnow(),
            uptime_seconds=3600.0,
            checks={
                "database": {"status": "healthy", "message": "OK"},
                "cache": {"status": "healthy", "message": "OK"}
            }
        )
        assert len(status.checks) == 2
        assert status.checks["database"]["status"] == "healthy"


class TestHealthChecker:
    @pytest.fixture
    def mock_db_pool(self):
        pool = MagicMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        return pool, conn

    @pytest.fixture
    def checker(self, mock_db_pool):
        pool, conn = mock_db_pool
        start_time = datetime.utcnow() - timedelta(hours=1)
        return HealthChecker(pool, start_time)

    @pytest.mark.asyncio
    async def test_check_database_healthy(self, checker, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchval = AsyncMock(return_value=1)

        result = await checker.check_database()
        assert result["status"] == "healthy"
        assert "OK" in result["message"]

    @pytest.mark.asyncio
    async def test_check_database_unhealthy(self, checker, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchval = AsyncMock(return_value=0)

        result = await checker.check_database()
        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_check_database_error(self, checker, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchval = AsyncMock(side_effect=Exception("Connection failed"))

        result = await checker.check_database()
        assert result["status"] == "unhealthy"
        assert "Connection failed" in result["message"]

    @pytest.mark.asyncio
    async def test_check_task_queue_healthy(self, checker, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchval = AsyncMock(side_effect=[5, 2])

        result = await checker.check_task_queue()
        assert result["status"] == "healthy"
        assert result["pending_tasks"] == 5
        assert result["running_tasks"] == 2

    @pytest.mark.asyncio
    async def test_check_task_queue_error(self, checker, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchval = AsyncMock(side_effect=Exception("Query failed"))

        result = await checker.check_task_queue()
        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_check_scheduler_healthy(self, checker, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchval = AsyncMock(return_value=10)

        result = await checker.check_scheduler()
        assert result["status"] == "healthy"
        assert result["active_schedules"] == 10

    @pytest.mark.asyncio
    async def test_check_scheduler_degraded(self, checker, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchval = AsyncMock(side_effect=Exception("Scheduler error"))

        result = await checker.check_scheduler()
        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_get_health_status_all_healthy(self, checker, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchval = AsyncMock(side_effect=[1, 5, 2, 10])

        status = await checker.get_health_status()
        assert status.status == "healthy"
        assert "All systems operational" in status.message
        assert len(status.checks) == 3

    @pytest.mark.asyncio
    async def test_get_health_status_with_unhealthy(self, checker, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchval = AsyncMock(side_effect=[
            0,
            5, 2,
            10
        ])

        status = await checker.get_health_status()
        assert status.status == "unhealthy"
        assert "critical" in status.message.lower()

    @pytest.mark.asyncio
    async def test_get_health_status_with_degraded(self, checker, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchval = AsyncMock(side_effect=[
            1,
            5, 2,
            Exception("Scheduler error")
        ])

        status = await checker.get_health_status()
        assert status.status == "degraded"
        assert "degraded" in status.message.lower()

    @pytest.mark.asyncio
    async def test_get_readiness_healthy(self, checker, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchval = AsyncMock(side_effect=[1, 5, 2, 10])

        ready = await checker.get_readiness()
        assert ready is True

    @pytest.mark.asyncio
    async def test_get_readiness_unhealthy(self, checker, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchval = AsyncMock(side_effect=[0, 5, 2, 10])

        ready = await checker.get_readiness()
        assert ready is False

    @pytest.mark.asyncio
    async def test_get_liveness_healthy(self, checker, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchval = AsyncMock(return_value=1)

        alive = await checker.get_liveness()
        assert alive is True

    @pytest.mark.asyncio
    async def test_get_liveness_unhealthy(self, checker, mock_db_pool):
        _, conn = mock_db_pool
        conn.fetchval = AsyncMock(side_effect=Exception("DB down"))

        alive = await checker.get_liveness()
        assert alive is False

    @pytest.mark.asyncio
    async def test_uptime_calculation(self, checker):
        _, conn = mock_db_pool = (MagicMock(), AsyncMock())
        conn.fetchval = AsyncMock(side_effect=[1, 0, 0, 0])

        status = await checker.get_health_status()
        assert status.uptime_seconds > 3500
