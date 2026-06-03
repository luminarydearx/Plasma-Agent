import time
import re
import json
from psycopg.types.json import Json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from plasmaagent.core.database import Database
from plasmaagent.ai.templates.auto_generator import (
    TemplateCandidate,
    TemplateCandidateCreate,
    CandidateDetectionRequest,
    CandidateDetectionReport,
)


class AutoTemplateGenerator:
    def __init__(self, db: Database):
        self._db = db

    async def create_candidate(
        self, data: TemplateCandidateCreate
    ) -> TemplateCandidate:
        if not data.pattern.strip():
            raise ValueError("pattern cannot be empty")
        if not data.example_input.strip():
            raise ValueError("example_input cannot be empty")
        if not data.generated_commands:
            raise ValueError("generated_commands cannot be empty")

        async with self._db.transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO template_candidates 
                    (pattern, example_input, generated_commands, confidence, 
                     frequency, source_task_id, metadata, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
                RETURNING id, pattern, example_input, generated_commands, confidence,
                          frequency, status, source_task_id, metadata, 
                          created_at, reviewed_at
                """,
                (
                    data.pattern,
                    data.example_input,
                    json.dumps(data.generated_commands),
                    data.confidence,
                    data.frequency,
                    data.source_task_id,
                    Json(data.metadata) if data.metadata is not None else None,
                ),
            )
            row = await cursor.fetchone()
            return self._row_to_candidate(row)

    async def get_candidate(self, candidate_id: int) -> Optional[TemplateCandidate]:
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, pattern, example_input, generated_commands, confidence,
                       frequency, status, source_task_id, metadata, 
                       created_at, reviewed_at
                FROM template_candidates
                WHERE id = %s
                """,
                (candidate_id,),
            )
            row = await cursor.fetchone()
            return self._row_to_candidate(row) if row else None

    async def list_candidates(
        self, status: str = "pending", limit: int = 50, offset: int = 0
    ) -> List[TemplateCandidate]:
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, pattern, example_input, generated_commands, confidence,
                       frequency, status, source_task_id, metadata, 
                       created_at, reviewed_at
                FROM template_candidates
                WHERE status = %s
                ORDER BY frequency DESC, confidence DESC
                LIMIT %s OFFSET %s
                """,
                (status, limit, offset),
            )
            rows = await cursor.fetchall()
            return [self._row_to_candidate(row) for row in rows]

    async def approve_candidate(
        self, candidate_id: int, template_name: str
    ) -> Optional[TemplateCandidate]:
        candidate = await self.get_candidate(candidate_id)
        if not candidate or candidate.status != "pending":
            return None

        async with self._db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO template_metrics (template_name, pattern)
                VALUES (%s, %s)
                ON CONFLICT (template_name, pattern) DO NOTHING
                """,
                (template_name, candidate.pattern),
            )

            cursor = await conn.execute(
                """
                UPDATE template_candidates
                SET status = 'approved', reviewed_at = NOW()
                WHERE id = %s AND status = 'pending'
                RETURNING id, pattern, example_input, generated_commands, confidence,
                          frequency, status, source_task_id, metadata, 
                          created_at, reviewed_at
                """,
                (candidate_id,),
            )
            row = await cursor.fetchone()
            return self._row_to_candidate(row) if row else None

    async def reject_candidate(
        self, candidate_id: int, reason: str = ""
    ) -> Optional[TemplateCandidate]:
        import json as _json
        rejection_data = _json.dumps({"rejection_reason": reason})
        async with self._db.transaction() as conn:
            cursor = await conn.execute(
                """
                UPDATE template_candidates
                SET status = 'rejected', reviewed_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                WHERE id = %s AND status = 'pending'
                RETURNING id, pattern, example_input, generated_commands, confidence,
                          frequency, status, source_task_id, metadata, 
                          created_at, reviewed_at
                """,
                (rejection_data, candidate_id),
            )
            row = await cursor.fetchone()
            return self._row_to_candidate(row) if row else None

    async def detect_patterns(
        self, request: CandidateDetectionRequest
    ) -> CandidateDetectionReport:
        start = time.perf_counter()

        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT 
                    t.id as task_id,
                    t.payload->>'commands' as commands_json
                FROM tasks t
                WHERE t.status = 'COMPLETED'
                  AND t.created_at >= NOW() - make_interval(days => %s)
                  AND t.payload IS NOT NULL
                ORDER BY t.created_at DESC
                LIMIT 1000
                """,
                (request.scan_period_days,),
            )
            rows = await cursor.fetchall()

        pattern_groups: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            commands_raw = row.get("commands_json")
            if not commands_raw:
                continue

            pattern = self._extract_pattern(commands_raw)
            if not pattern:
                continue

            if pattern not in pattern_groups:
                pattern_groups[pattern] = {
                    "count": 0,
                    "example_task_id": row["task_id"],
                    "commands_raw": commands_raw,
                }
            pattern_groups[pattern]["count"] += 1

        candidates_generated = 0
        duplicates_skipped = 0
        new_candidates = []

        for pattern, data in pattern_groups.items():
            if data["count"] < request.min_frequency:
                continue

            already_exists = await self._pattern_exists(pattern)
            if already_exists:
                duplicates_skipped += 1
                continue

            try:
                commands_list = self._parse_commands(data["commands_raw"])
                confidence = min(0.5 + (data["count"] * 0.05), 0.95)

                candidate_data = TemplateCandidateCreate(
                    pattern=pattern,
                    example_input=pattern,
                    generated_commands=commands_list,
                    confidence=confidence,
                    frequency=data["count"],
                    source_task_id=data["example_task_id"],
                    metadata={"auto_detected": True},
                )
                await self.create_candidate(candidate_data)
                candidates_generated += 1
                new_candidates.append(pattern)
            except Exception:
                continue

        duration_ms = int((time.perf_counter() - start) * 1000)

        return CandidateDetectionReport(
            scanned_at=datetime.now(timezone.utc),
            patterns_detected=len(pattern_groups),
            candidates_generated=candidates_generated,
            duplicate_skipped=duplicates_skipped,
            scan_duration_ms=duration_ms,
            new_candidates=new_candidates,
        )

    async def _pattern_exists(self, pattern: str) -> bool:
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT 1 FROM (
                    SELECT pattern FROM template_metrics WHERE pattern = %s
                    UNION
                    SELECT pattern FROM template_candidates WHERE pattern = %s AND status != 'rejected'
                ) combined
                LIMIT 1
                """,
                (pattern, pattern),
            )
            return await cursor.fetchone() is not None

    def _extract_pattern(self, commands_raw: str) -> str:
        if not commands_raw or len(commands_raw) > 500:
            return ""
        normalized = re.sub(r"[\"\'\s]+", " ", commands_raw.strip())
        return normalized[:500]

    def _parse_commands(self, commands_raw: str) -> List[str]:
        if not commands_raw:
            return []
        cleaned = commands_raw.strip("[]\"' ")
        if not cleaned:
            return []
        parts = [p.strip().strip("\"'") for p in cleaned.split(",")]
        return [p for p in parts if p]

    def _row_to_candidate(self, row) -> TemplateCandidate:
        commands = row["generated_commands"]
        if isinstance(commands, str):
            commands = json.loads(commands)
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return TemplateCandidate(
            id=row["id"],
            pattern=row["pattern"],
            example_input=row["example_input"],
            generated_commands=commands,
            confidence=row["confidence"],
            frequency=row["frequency"],
            status=row["status"],
            source_task_id=row["source_task_id"],
            metadata=metadata,
            created_at=row["created_at"],
            reviewed_at=row["reviewed_at"],
        )
