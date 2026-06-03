import time
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from psycopg.types.json import Json
from plasmaagent.core.database import Database
from plasmaagent.ai.templates.retirement import (
    TemplateRetirement,
    TemplateRetirementCreate,
    RetirementScanRequest,
    RetirementScanReport,
)


class RetirementService:
    def __init__(self, db: Database):
        self._db = db

    async def retire_template(self, data: TemplateRetirementCreate) -> TemplateRetirement:
        if not data.template_name.strip():
            raise ValueError("template_name cannot be empty")
        if not data.reason.strip():
            raise ValueError("reason cannot be empty")

        metadata_json = Json(data.metadata) if data.metadata is not None else None

        async with self._db.transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO template_retirements 
                    (template_name, pattern, reason, success_rate, total_uses, 
                     avg_execution_time_ms, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, template_name, pattern, reason, success_rate, 
                          total_uses, avg_execution_time_ms, retired_at, metadata
                """,
                (
                    data.template_name,
                    data.pattern,
                    data.reason,
                    data.success_rate,
                    data.total_uses,
                    data.avg_execution_time_ms,
                    metadata_json,
                ),
            )
            row = await cursor.fetchone()
            return self._row_to_retirement(row)

    async def get_retirement(self, retirement_id: int) -> Optional[TemplateRetirement]:
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, template_name, pattern, reason, success_rate,
                       total_uses, avg_execution_time_ms, retired_at, metadata
                FROM template_retirements
                WHERE id = %s
                """,
                (retirement_id,),
            )
            row = await cursor.fetchone()
            return self._row_to_retirement(row) if row else None

    async def list_retirements(
        self, limit: int = 50, offset: int = 0
    ) -> List[TemplateRetirement]:
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, template_name, pattern, reason, success_rate,
                       total_uses, avg_execution_time_ms, retired_at, metadata
                FROM template_retirements
                ORDER BY retired_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = await cursor.fetchall()
            return [self._row_to_retirement(row) for row in rows]

    async def is_retired(self, template_name: str) -> bool:
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM template_retirements WHERE template_name = %s LIMIT 1",
                (template_name,),
            )
            return await cursor.fetchone() is not None

    async def find_retirement_candidates(
        self, request: RetirementScanRequest
    ) -> List[Dict[str, Any]]:
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT 
                    template_name,
                    pattern,
                    usage_count as total_uses,
                    success_count as successes,
                    failure_count as failures,
                    CASE 
                        WHEN usage_count > 0 
                        THEN total_generation_time_ms::float / usage_count 
                        ELSE 0.0 
                    END as avg_time_ms,
                    CASE 
                        WHEN usage_count > 0 
                        THEN success_count::float / usage_count 
                        ELSE 0.0 
                    END as success_rate
                FROM template_metrics
                WHERE created_at >= NOW() - make_interval(days => %s)
                  AND usage_count >= %s
                """,
                (request.scan_period_days, request.min_uses_threshold),
            )
            rows = await cursor.fetchall()

        candidates = []
        for row in rows:
            success_rate = float(row["success_rate"] or 0.0)
            avg_time = float(row["avg_time_ms"] or 0.0)

            if success_rate < request.success_rate_threshold:
                reason = f"Low success rate: {success_rate:.2%}"
                candidates.append(
                    self._build_candidate(row, success_rate, avg_time, reason)
                )
                continue

            if (
                request.max_execution_time_ms is not None
                and avg_time > request.max_execution_time_ms
            ):
                reason = f"Slow execution: {avg_time:.0f}ms avg"
                candidates.append(
                    self._build_candidate(row, success_rate, avg_time, reason)
                )

        return candidates

    async def scan_and_retire(
        self, request: RetirementScanRequest
    ) -> RetirementScanReport:
        start = time.perf_counter()
        candidates = await self.find_retirement_candidates(request)

        retired = []
        skipped = []

        for candidate in candidates:
            name = candidate["template_name"]
            already_retired = await self.is_retired(name)
            if already_retired:
                skipped.append({"template_name": name, "reason": "Already retired"})
                continue

            try:
                data = TemplateRetirementCreate(
                    template_name=name,
                    pattern=candidate.get("pattern"),
                    reason=candidate["retirement_reason"],
                    success_rate=candidate["success_rate"],
                    total_uses=candidate["total_uses"],
                    avg_execution_time_ms=candidate.get("avg_execution_time_ms"),
                    metadata={
                        "auto_retired": True,
                        "scan_thresholds": {
                            "success_rate": request.success_rate_threshold,
                            "min_uses": request.min_uses_threshold,
                            "max_execution_time_ms": request.max_execution_time_ms,
                        },
                    },
                )
                await self.retire_template(data)
                retired.append(name)
            except Exception as e:
                skipped.append({"template_name": name, "reason": str(e)})

        duration_ms = int((time.perf_counter() - start) * 1000)

        return RetirementScanReport(
            scanned_at=datetime.now(timezone.utc),
            success_rate_threshold=request.success_rate_threshold,
            min_uses_threshold=request.min_uses_threshold,
            max_execution_time_ms=request.max_execution_time_ms,
            candidates_found=len(candidates),
            retired_count=len(retired),
            skipped_count=len(skipped),
            retired_templates=retired,
            skipped_templates=skipped,
            scan_duration_ms=duration_ms,
        )

    async def get_retirement_stats(self) -> Dict[str, Any]:
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT 
                    COUNT(*) as total_retired,
                    COUNT(DISTINCT template_name) as unique_templates,
                    AVG(success_rate) as avg_success_rate_at_retirement,
                    MIN(retired_at) as first_retirement,
                    MAX(retired_at) as last_retirement
                FROM template_retirements
                """
            )
            row = await cursor.fetchone()
            return {
                "total_retired": row["total_retired"] or 0,
                "unique_templates": row["unique_templates"] or 0,
                "avg_success_rate_at_retirement": float(
                    row["avg_success_rate_at_retirement"] or 0.0
                ),
                "first_retirement": row["first_retirement"],
                "last_retirement": row["last_retirement"],
            }

    def _build_candidate(
        self,
        row: Dict[str, Any],
        success_rate: float,
        avg_time: float,
        reason: str,
    ) -> Dict[str, Any]:
        return {
            "template_name": row["template_name"],
            "pattern": row.get("pattern"),
            "total_uses": row["total_uses"],
            "successes": row["successes"],
            "success_rate": success_rate,
            "avg_execution_time_ms": avg_time,
            "retirement_reason": reason,
        }

    def _row_to_retirement(self, row) -> TemplateRetirement:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return TemplateRetirement(
            id=row["id"],
            template_name=row["template_name"],
            pattern=row["pattern"],
            reason=row["reason"],
            success_rate=row["success_rate"],
            total_uses=row["total_uses"],
            avg_execution_time_ms=row["avg_execution_time_ms"],
            retired_at=row["retired_at"],
            metadata=metadata,
        )
