import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from plasmaagent.ai.templates.retirement_service import RetirementService
from plasmaagent.ai.templates.retirement import (
    TemplateRetirementCreate,
    TemplateRetirement,
    RetirementScanRequest,
    RetirementScanReport,
)


class TestRetirementServiceInit:
    def test_init_with_database(self):
        db = MagicMock()
        service = RetirementService(db)
        assert service._db == db


class TestRetireTemplate:
    @pytest.mark.asyncio
    async def test_retire_template_success(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchone.return_value = {
            "id": 1,
            "template_name": "old_template",
            "pattern": "pattern.*",
            "reason": "Low success rate: 30%",
            "success_rate": 0.3,
            "total_uses": 50,
            "avg_execution_time_ms": 5000.0,
            "retired_at": datetime.now(timezone.utc),
            "metadata": {"auto_retired": True},
        }

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.transaction.return_value = conn

        service = RetirementService(db)
        data = TemplateRetirementCreate(
            template_name="old_template",
            pattern="pattern.*",
            reason="Low success rate: 30%",
            success_rate=0.3,
            total_uses=50,
            avg_execution_time_ms=5000.0,
            metadata={"auto_retired": True},
        )
        result = await service.retire_template(data)

        assert isinstance(result, TemplateRetirement)
        assert result.template_name == "old_template"
        assert result.success_rate == 0.3
        assert result.total_uses == 50

    @pytest.mark.asyncio
    async def test_retire_template_empty_name_raises(self):
        db = MagicMock()
        service = RetirementService(db)
        data = TemplateRetirementCreate(
            template_name="   ",
            reason="Low success rate",
            success_rate=0.3,
            total_uses=50,
        )
        with pytest.raises(ValueError, match="template_name"):
            await service.retire_template(data)

    @pytest.mark.asyncio
    async def test_retire_template_empty_reason_raises(self):
        db = MagicMock()
        service = RetirementService(db)
        data = TemplateRetirementCreate(
            template_name="test",
            reason="   ",
            success_rate=0.3,
            total_uses=50,
        )
        with pytest.raises(ValueError, match="reason"):
            await service.retire_template(data)


class TestGetRetirement:
    @pytest.mark.asyncio
    async def test_get_retirement_found(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchone.return_value = {
            "id": 1,
            "template_name": "test",
            "pattern": "p",
            "reason": "Low success",
            "success_rate": 0.3,
            "total_uses": 10,
            "avg_execution_time_ms": 100.0,
            "retired_at": datetime.now(timezone.utc),
            "metadata": None,
        }

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn

        service = RetirementService(db)
        result = await service.get_retirement(1)

        assert isinstance(result, TemplateRetirement)
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_get_retirement_not_found(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        cursor.fetchone.return_value = None

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn

        service = RetirementService(db)
        result = await service.get_retirement(999)
        assert result is None


class TestListRetirements:
    @pytest.mark.asyncio
    async def test_list_empty(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        cursor.fetchall.return_value = []

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn

        service = RetirementService(db)
        result = await service.list_retirements()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_with_data(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchall.return_value = [
            {
                "id": 1,
                "template_name": "t1",
                "pattern": "p1",
                "reason": "Low success",
                "success_rate": 0.3,
                "total_uses": 10,
                "avg_execution_time_ms": 100.0,
                "retired_at": datetime.now(timezone.utc),
                "metadata": None,
            },
            {
                "id": 2,
                "template_name": "t2",
                "pattern": "p2",
                "reason": "Slow",
                "success_rate": 0.8,
                "total_uses": 20,
                "avg_execution_time_ms": 10000.0,
                "retired_at": datetime.now(timezone.utc),
                "metadata": None,
            },
        ]

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn

        service = RetirementService(db)
        result = await service.list_retirements()

        assert len(result) == 2
        assert all(isinstance(r, TemplateRetirement) for r in result)


class TestIsRetired:
    @pytest.mark.asyncio
    async def test_is_retired_true(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        cursor.fetchone.return_value = {"?column?": 1}

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn

        service = RetirementService(db)
        result = await service.is_retired("test")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_retired_false(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        cursor.fetchone.return_value = None

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn

        service = RetirementService(db)
        result = await service.is_retired("nonexistent")
        assert result is False


class TestFindRetirementCandidates:
    @pytest.mark.asyncio
    async def test_find_candidates_low_success(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchall.return_value = [
            {
                "template_name": "bad_template",
                "pattern": "pattern.*",
                "total_uses": 20,
                "successes": 4,
                "failures": 16,
                "avg_time_ms": 100.0,
                "success_rate": 0.2,
            }
        ]

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn

        service = RetirementService(db)
        request = RetirementScanRequest(
            success_rate_threshold=0.5,
            min_uses_threshold=10,
            scan_period_days=30,
        )
        candidates = await service.find_retirement_candidates(request)

        assert len(candidates) == 1
        assert candidates[0]["template_name"] == "bad_template"
        assert candidates[0]["success_rate"] == 0.2
        assert "Low success rate" in candidates[0]["retirement_reason"]

    @pytest.mark.asyncio
    async def test_find_candidates_slow_execution(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchall.return_value = [
            {
                "template_name": "slow_template",
                "pattern": "slow.*",
                "total_uses": 20,
                "successes": 18,
                "failures": 2,
                "avg_time_ms": 50000.0,
                "success_rate": 0.9,
            }
        ]

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn

        service = RetirementService(db)
        request = RetirementScanRequest(
            success_rate_threshold=0.5,
            min_uses_threshold=10,
            max_execution_time_ms=10000.0,
            scan_period_days=30,
        )
        candidates = await service.find_retirement_candidates(request)

        assert len(candidates) == 1
        assert candidates[0]["template_name"] == "slow_template"
        assert "Slow execution" in candidates[0]["retirement_reason"]

    @pytest.mark.asyncio
    async def test_find_candidates_none_healthy(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchall.return_value = [
            {
                "template_name": "good_template",
                "pattern": "good.*",
                "total_uses": 50,
                "successes": 48,
                "failures": 2,
                "avg_time_ms": 100.0,
                "success_rate": 0.96,
            }
        ]

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn

        service = RetirementService(db)
        request = RetirementScanRequest(
            success_rate_threshold=0.5,
            min_uses_threshold=10,
            scan_period_days=30,
        )
        candidates = await service.find_retirement_candidates(request)

        assert len(candidates) == 0


class TestScanAndRetire:
    @pytest.mark.asyncio
    async def test_scan_and_retire_success(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        scan_results = [
            {
                "template_name": "bad_template",
                "pattern": "pattern.*",
                "total_uses": 20,
                "successes": 4,
                "failures": 16,
                "avg_time_ms": 100.0,
                "success_rate": 0.2,
            }
        ]

        check_retired_result = None
        retire_result = {
            "id": 1,
            "template_name": "bad_template",
            "pattern": "pattern.*",
            "reason": "Low success rate: 20%",
            "success_rate": 0.2,
            "total_uses": 20,
            "avg_execution_time_ms": 100.0,
            "retired_at": datetime.now(timezone.utc),
            "metadata": {"auto_retired": True},
        }

        call_count = [0]

        async def fetchone_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return None
            else:
                return retire_result

        async def fetchall_side_effect():
            return scan_results

        cursor.fetchone.side_effect = fetchone_side_effect
        cursor.fetchall.side_effect = fetchall_side_effect

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn
        db.transaction.return_value = conn

        service = RetirementService(db)
        request = RetirementScanRequest(
            success_rate_threshold=0.5,
            min_uses_threshold=10,
            scan_period_days=30,
        )
        report = await service.scan_and_retire(request)

        assert isinstance(report, RetirementScanReport)
        assert report.candidates_found == 1
        assert report.retired_count == 1
        assert "bad_template" in report.retired_templates


class TestGetRetirementStats:
    @pytest.mark.asyncio
    async def test_get_stats_empty(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchone.return_value = {
            "total_retired": 0,
            "unique_templates": 0,
            "avg_success_rate_at_retirement": None,
            "first_retirement": None,
            "last_retirement": None,
        }

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn

        service = RetirementService(db)
        stats = await service.get_retirement_stats()

        assert stats["total_retired"] == 0
        assert stats["unique_templates"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        now = datetime.now(timezone.utc)
        cursor.fetchone.return_value = {
            "total_retired": 5,
            "unique_templates": 3,
            "avg_success_rate_at_retirement": 0.35,
            "first_retirement": now,
            "last_retirement": now,
        }

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn

        service = RetirementService(db)
        stats = await service.get_retirement_stats()

        assert stats["total_retired"] == 5
        assert stats["unique_templates"] == 3
        assert stats["avg_success_rate_at_retirement"] == 0.35


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_retire_with_special_chars_in_name(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchone.return_value = {
            "id": 1,
            "template_name": "template'; DROP TABLE tasks;--",
            "pattern": None,
            "reason": "Test",
            "success_rate": 0.5,
            "total_uses": 10,
            "avg_execution_time_ms": 100.0,
            "retired_at": datetime.now(timezone.utc),
            "metadata": None,
        }

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.transaction.return_value = conn

        service = RetirementService(db)
        data = TemplateRetirementCreate(
            template_name="template'; DROP TABLE tasks;--",
            reason="Test",
            success_rate=0.5,
            total_uses=10,
        )
        result = await service.retire_template(data)

        assert result.template_name == "template'; DROP TABLE tasks;--"

    @pytest.mark.asyncio
    async def test_retire_with_unicode_name(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchone.return_value = {
            "id": 1,
            "template_name": "日本語テンプレート",
            "pattern": None,
            "reason": "テスト",
            "success_rate": 0.5,
            "total_uses": 10,
            "avg_execution_time_ms": 100.0,
            "retired_at": datetime.now(timezone.utc),
            "metadata": None,
        }

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.transaction.return_value = conn

        service = RetirementService(db)
        data = TemplateRetirementCreate(
            template_name="日本語テンプレート",
            reason="テスト",
            success_rate=0.5,
            total_uses=10,
        )
        result = await service.retire_template(data)

        assert result.template_name == "日本語テンプレート"

    @pytest.mark.asyncio
    async def test_concurrent_retirements(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchone.return_value = {
            "id": 1,
            "template_name": "test",
            "pattern": None,
            "reason": "Test",
            "success_rate": 0.5,
            "total_uses": 10,
            "avg_execution_time_ms": 100.0,
            "retired_at": datetime.now(timezone.utc),
            "metadata": None,
        }

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.transaction.return_value = conn

        service = RetirementService(db)

        import asyncio

        tasks = [
            service.retire_template(
                TemplateRetirementCreate(
                    template_name=f"template_{i}",
                    reason="Test",
                    success_rate=0.5,
                    total_uses=10,
                )
            )
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(isinstance(r, TemplateRetirement) for r in results)

    def test_validation_bounds(self):
        with pytest.raises(Exception):
            TemplateRetirementCreate(
                template_name="test",
                reason="test",
                success_rate=1.5,
                total_uses=10,
            )

        with pytest.raises(Exception):
            TemplateRetirementCreate(
                template_name="test",
                reason="test",
                success_rate=-0.1,
                total_uses=10,
            )

        with pytest.raises(Exception):
            TemplateRetirementCreate(
                template_name="test",
                reason="test",
                success_rate=0.5,
                total_uses=-1,
            )
