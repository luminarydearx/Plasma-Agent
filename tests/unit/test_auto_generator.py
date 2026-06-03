import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
from plasmaagent.ai.templates.auto_generator_service import AutoTemplateGenerator
from plasmaagent.ai.templates.auto_generator import (
    TemplateCandidateCreate,
    TemplateCandidate,
    CandidateDetectionRequest,
    CandidateDetectionReport,
)


class TestAutoTemplateGeneratorInit:
    def test_init_with_database(self):
        db = MagicMock()
        gen = AutoTemplateGenerator(db)
        assert gen._db == db


class TestCreateCandidate:
    @pytest.mark.asyncio
    async def test_create_candidate_success(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchone.return_value = {
            "id": 1,
            "pattern": "backup database.*",
            "example_input": "backup database postgresql",
            "generated_commands": ["pg_dump", "verify"],
            "confidence": 0.85,
            "frequency": 5,
            "status": "pending",
            "source_task_id": uuid4(),
            "metadata": {"auto_detected": True},
            "created_at": datetime.now(timezone.utc),
            "reviewed_at": None,
        }

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.transaction.return_value = conn

        gen = AutoTemplateGenerator(db)
        data = TemplateCandidateCreate(
            pattern="backup database.*",
            example_input="backup database postgresql",
            generated_commands=["pg_dump", "verify"],
            confidence=0.85,
            frequency=5,
        )
        result = await gen.create_candidate(data)

        assert isinstance(result, TemplateCandidate)
        assert result.pattern == "backup database.*"
        assert result.status == "pending"

    @pytest.mark.asyncio
    async def test_create_candidate_empty_pattern_raises(self):
        db = MagicMock()
        gen = AutoTemplateGenerator(db)
        data = TemplateCandidateCreate(
            pattern="   ",
            example_input="test",
            generated_commands=["cmd"],
            confidence=0.8,
            frequency=3,
        )
        with pytest.raises(ValueError, match="pattern"):
            await gen.create_candidate(data)

    @pytest.mark.asyncio
    async def test_create_candidate_empty_input_raises(self):
        db = MagicMock()
        gen = AutoTemplateGenerator(db)
        data = TemplateCandidateCreate(
            pattern="test.*",
            example_input="   ",
            generated_commands=["cmd"],
            confidence=0.8,
            frequency=3,
        )
        with pytest.raises(ValueError, match="example_input"):
            await gen.create_candidate(data)

    @pytest.mark.asyncio
    async def test_create_candidate_empty_commands_raises(self):
        db = MagicMock()
        gen = AutoTemplateGenerator(db)
        data = TemplateCandidateCreate(
            pattern="test.*",
            example_input="test input",
            generated_commands=[],
            confidence=0.8,
            frequency=3,
        )
        with pytest.raises(ValueError, match="generated_commands"):
            await gen.create_candidate(data)


class TestGetCandidate:
    @pytest.mark.asyncio
    async def test_get_candidate_found(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchone.return_value = {
            "id": 1,
            "pattern": "test.*",
            "example_input": "test",
            "generated_commands": ["cmd"],
            "confidence": 0.8,
            "frequency": 3,
            "status": "pending",
            "source_task_id": None,
            "metadata": None,
            "created_at": datetime.now(timezone.utc),
            "reviewed_at": None,
        }

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn

        gen = AutoTemplateGenerator(db)
        result = await gen.get_candidate(1)

        assert isinstance(result, TemplateCandidate)
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_get_candidate_not_found(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()
        cursor.fetchone.return_value = None

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn

        gen = AutoTemplateGenerator(db)
        result = await gen.get_candidate(999)
        assert result is None


class TestListCandidates:
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

        gen = AutoTemplateGenerator(db)
        result = await gen.list_candidates()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_with_data(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchall.return_value = [
            {
                "id": 1,
                "pattern": "p1",
                "example_input": "e1",
                "generated_commands": ["c1"],
                "confidence": 0.8,
                "frequency": 5,
                "status": "pending",
                "source_task_id": None,
                "metadata": None,
                "created_at": datetime.now(timezone.utc),
                "reviewed_at": None,
            },
            {
                "id": 2,
                "pattern": "p2",
                "example_input": "e2",
                "generated_commands": ["c2"],
                "confidence": 0.7,
                "frequency": 3,
                "status": "pending",
                "source_task_id": None,
                "metadata": None,
                "created_at": datetime.now(timezone.utc),
                "reviewed_at": None,
            },
        ]

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn

        gen = AutoTemplateGenerator(db)
        result = await gen.list_candidates()

        assert len(result) == 2
        assert all(isinstance(c, TemplateCandidate) for c in result)


class TestApproveCandidate:
    @pytest.mark.asyncio
    async def test_approve_success(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        pending_row = {
            "id": 1,
            "pattern": "test.*",
            "example_input": "test",
            "generated_commands": ["cmd"],
            "confidence": 0.8,
            "frequency": 3,
            "status": "pending",
            "source_task_id": None,
            "metadata": None,
            "created_at": datetime.now(timezone.utc),
            "reviewed_at": None,
        }

        approved_row = {**pending_row, "status": "approved", "reviewed_at": datetime.now(timezone.utc)}

        cursor.fetchone.side_effect = [pending_row, approved_row]

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn
        db.transaction.return_value = conn

        gen = AutoTemplateGenerator(db)
        result = await gen.approve_candidate(1, "approved_template")

        assert result is not None
        assert result.status == "approved"
        assert result.reviewed_at is not None


class TestRejectCandidate:
    @pytest.mark.asyncio
    async def test_reject_success(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        rejected_row = {
            "id": 1,
            "pattern": "test.*",
            "example_input": "test",
            "generated_commands": ["cmd"],
            "confidence": 0.8,
            "frequency": 3,
            "status": "rejected",
            "source_task_id": None,
            "metadata": {"rejection_reason": "Low quality"},
            "created_at": datetime.now(timezone.utc),
            "reviewed_at": datetime.now(timezone.utc),
        }

        cursor.fetchone.return_value = rejected_row

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.transaction.return_value = conn

        gen = AutoTemplateGenerator(db)
        result = await gen.reject_candidate(1, "Low quality")

        assert result is not None
        assert result.status == "rejected"


class TestPatternExtraction:
    def test_extract_pattern_basic(self):
        db = MagicMock()
        gen = AutoTemplateGenerator(db)
        result = gen._extract_pattern("backup database postgresql")
        assert result == "backup database postgresql"

    def test_extract_pattern_normalizes_whitespace(self):
        db = MagicMock()
        gen = AutoTemplateGenerator(db)
        result = gen._extract_pattern("backup   database  postgresql")
        assert "  " not in result

    def test_extract_pattern_truncates_long(self):
        db = MagicMock()
        gen = AutoTemplateGenerator(db)
        long_input = "x" * 1000
        result = gen._extract_pattern(long_input)
        assert len(result) <= 500

    def test_extract_pattern_empty_returns_empty(self):
        db = MagicMock()
        gen = AutoTemplateGenerator(db)
        assert gen._extract_pattern("") == ""
        assert gen._extract_pattern("   ") == ""


class TestParseCommands:
    def test_parse_commands_basic(self):
        db = MagicMock()
        gen = AutoTemplateGenerator(db)
        result = gen._parse_commands('["cmd1", "cmd2", "cmd3"]')
        assert result == ["cmd1", "cmd2", "cmd3"]

    def test_parse_commands_empty(self):
        db = MagicMock()
        gen = AutoTemplateGenerator(db)
        assert gen._parse_commands("") == []
        assert gen._parse_commands("[]") == []

    def test_parse_commands_strips_quotes(self):
        db = MagicMock()
        gen = AutoTemplateGenerator(db)
        result = gen._parse_commands('"cmd1", "cmd2"')
        assert all(not c.startswith('"') for c in result)


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_create_with_unicode(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchone.return_value = {
            "id": 1,
            "pattern": "日本語パターン",
            "example_input": "日本語入力",
            "generated_commands": ["コマンド"],
            "confidence": 0.8,
            "frequency": 3,
            "status": "pending",
            "source_task_id": None,
            "metadata": None,
            "created_at": datetime.now(timezone.utc),
            "reviewed_at": None,
        }

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.transaction.return_value = conn

        gen = AutoTemplateGenerator(db)
        data = TemplateCandidateCreate(
            pattern="日本語パターン",
            example_input="日本語入力",
            generated_commands=["コマンド"],
            confidence=0.8,
            frequency=3,
        )
        result = await gen.create_candidate(data)
        assert result.pattern == "日本語パターン"

    @pytest.mark.asyncio
    async def test_create_with_sql_injection_safe(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchone.return_value = {
            "id": 1,
            "pattern": "'; DROP TABLE template_candidates;--",
            "example_input": "injection test",
            "generated_commands": ["cmd"],
            "confidence": 0.8,
            "frequency": 3,
            "status": "pending",
            "source_task_id": None,
            "metadata": None,
            "created_at": datetime.now(timezone.utc),
            "reviewed_at": None,
        }

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.transaction.return_value = conn

        gen = AutoTemplateGenerator(db)
        data = TemplateCandidateCreate(
            pattern="'; DROP TABLE template_candidates;--",
            example_input="injection test",
            generated_commands=["cmd"],
            confidence=0.8,
            frequency=3,
        )
        result = await gen.create_candidate(data)
        assert "DROP TABLE" in result.pattern

    def test_validation_bounds(self):
        with pytest.raises(Exception):
            TemplateCandidateCreate(
                pattern="test",
                example_input="test",
                generated_commands=["cmd"],
                confidence=1.5,
                frequency=3,
            )

        with pytest.raises(Exception):
            TemplateCandidateCreate(
                pattern="test",
                example_input="test",
                generated_commands=["cmd"],
                confidence=0.8,
                frequency=0,
            )

    @pytest.mark.asyncio
    async def test_detect_patterns_no_tasks(self):
        db = MagicMock()
        conn = AsyncMock()
        cursor = AsyncMock()

        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = None

        conn.execute.return_value = cursor
        conn.__aenter__.return_value = conn
        conn.__aexit__.return_value = None
        db.connection.return_value = conn
        db.transaction.return_value = conn

        gen = AutoTemplateGenerator(db)
        request = CandidateDetectionRequest(min_frequency=3, scan_period_days=7)
        report = await gen.detect_patterns(request)

        assert isinstance(report, CandidateDetectionReport)
        assert report.patterns_detected == 0
        assert report.candidates_generated == 0
