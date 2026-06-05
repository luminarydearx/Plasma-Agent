import json
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import uuid4

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

        new_id = str(uuid4())
        metadata_json = json.dumps(data.metadata) if data.metadata is not None else None
        now = datetime.now(timezone.utc)

        await self._db.execute(
            """
            INSERT INTO template_retirements 
                (id, template_name, pattern, reason, success_rate, total_uses, 
                 avg_execution_time_ms, metadata, retired_at)
            VALUES (:id, :name, :pattern, :reason, :success, :uses, :time, :meta, :now)
            """,
            {
                "id": new_id,
                "name": data.template_name,
                "pattern": data.pattern or "",
                "reason": data.reason,
                "success": data.success_rate or 0.0,
                "uses": data.total_uses or 0,
                "time": data.avg_execution_time_ms or 0,
                "meta": metadata_json,
                "now": now,
            },
        )

        return TemplateRetirement(
            id=new_id,
            template_name=data.template_name,
            pattern=data.pattern or "",
            reason=data.reason,
            success_rate=data.success_rate or 0.0,
            total_uses=data.total_uses or 0,
            avg_execution_time_ms=data.avg_execution_time_ms or 0,
            retired_at=now,
            metadata=data.metadata,
        )

    async def get_retirement(self, retirement_id: str) -> Optional[TemplateRetirement]:
        row = await self._db.fetch_one(
            """
            SELECT id, template_name, pattern, reason, success_rate,
                   total_uses, avg_execution_time_ms, retired_at, metadata
            FROM template_retirements
            WHERE id = :id
            """,
            {"id": retirement_id},
        )
        return self._row_to_retirement(row) if row else None

    async def list_retirements(
        self, limit: int = 50, offset: int = 0
    ) -> List[TemplateRetirement]:
        rows = await self._db.fetch_all(
            """
            SELECT id, template_name, pattern, reason, success_rate,
                   total_uses, avg_execution_time_ms, retired_at, metadata
            FROM template_retirements
            ORDER BY retired_at DESC
            LIMIT :limit OFFSET :offset
            """,
            {"limit": limit, "offset": offset},
        )
        return [self._row_to_retirement(row) for row in rows]

    async def is_retired(self, template_name: str) -> bool:
        row = await self._db.fetch_one(
            "SELECT 1 FROM template_retirements WHERE template_name = :name LIMIT 1",
            {"name": template_name},
        )
        return row is not None

    async def find_retirement_candidates(
        self, request: RetirementScanRequest
    ) -> List[Dict[str, Any]]:
        rows = await self._db.fetch_all(
            """
            SELECT 
                template_name,
                pattern,
                usage_count as total_uses,
                success_count as successes,
                failure_count as failures,
                CASE 
                    WHEN usage_count > 0 
                    THEN CAST(total_generation_time_ms AS FLOAT) / usage_count 
                    ELSE 0.0 
                END as avg_time_ms,
                CASE 
                    WHEN usage_count > 0 
                    THEN CAST(success_count AS FLOAT) / usage_count 
                    ELSE 0.0 
                END as success_rate
            FROM template_metrics
            WHERE created_at >= :cutoff
              AND usage_count >= :min_uses
            """,
            {
                "cutoff": time.time() - (request.scan_period_days * 86400),
                "min_uses": request.min_uses_threshold,
            },
        )

        candidates = []
        for row in rows:
            success_rate = float(row.get("success_rate") or 0.0)
            avg_time = float(row.get("avg_time_ms") or 0.0)

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
        row = await self._db.fetch_one(
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
        if not row:
            return {
                "total_retired": 0,
                "unique_templates": 0,
                "avg_success_rate_at_retirement": 0.0,
                "first_retirement": None,
                "last_retirement": None,
            }
        return {
            "total_retired": row.get("total_retired") or 0,
            "unique_templates": row.get("unique_templates") or 0,
            "avg_success_rate_at_retirement": float(
                row.get("avg_success_rate_at_retirement") or 0.0
            ),
            "first_retirement": row.get("first_retirement"),
            "last_retirement": row.get("last_retirement"),
        }

    def _build_candidate(
        self,
        row: Dict[str, Any],
        success_rate: float,
        avg_time: float,
        reason: str,
    ) -> Dict[str, Any]:
        return {
            "template_name": row.get("template_name", ""),
            "pattern": row.get("pattern", ""),
            "total_uses": row.get("total_uses", 0),
            "successes": row.get("successes", 0),
            "success_rate": success_rate,
            "avg_execution_time_ms": avg_time,
            "retirement_reason": reason,
        }

    def _row_to_retirement(self, row: Dict[str, Any]) -> TemplateRetirement:
        metadata = row.get("metadata")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = None
        return TemplateRetirement(
            id=row["id"],
            template_name=row["template_name"],
            pattern=row.get("pattern", ""),
            reason=row["reason"],
            success_rate=row.get("success_rate", 0.0),
            total_uses=row.get("total_uses", 0),
            avg_execution_time_ms=row.get("avg_execution_time_ms", 0),
            retired_at=row.get("retired_at"),
            metadata=metadata,
        )
