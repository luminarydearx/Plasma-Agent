import time
import re
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, insert, update, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from plasmaagent.core.database import Database
from plasmaagent.core.schema import Task, TemplateMetric
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

        async with self._db.session() as session:
            from plasmaagent.core.schema import TemplateMetric
            
            candidate = TemplateMetric(
                template_name=data.pattern,
                pattern=data.pattern,
                success_rate=data.confidence,
                avg_execution_time_ms=0,
                total_executions=data.frequency,
                metadata={
                    "example_input": data.example_input,
                    "generated_commands": data.generated_commands,
                    "source_task_id": str(data.source_task_id) if data.source_task_id else None,
                    "status": "pending",
                    **(data.metadata or {}),
                },
            )
            session.add(candidate)
            await session.commit()
            await session.refresh(candidate)
            
            return self._orm_to_candidate(candidate)

    async def get_candidate(self, candidate_id: int) -> Optional[TemplateCandidate]:
        async with self._db.session() as session:
            from plasmaagent.core.schema import TemplateMetric
            
            stmt = select(TemplateMetric).where(TemplateMetric.id == candidate_id)
            result = await session.execute(stmt)
            candidate = result.scalar_one_or_none()
            
            return self._orm_to_candidate(candidate) if candidate else None

    async def list_candidates(
        self, status: str = "pending", limit: int = 50, offset: int = 0
    ) -> List[TemplateCandidate]:
        async with self._db.session() as session:
            from plasmaagent.core.schema import TemplateMetric
            
            stmt = select(TemplateMetric).where(
                TemplateMetric.metadata["status"].as_string() == status
            ).order_by(
                TemplateMetric.total_executions.desc(),
                TemplateMetric.success_rate.desc(),
            ).limit(limit).offset(offset)
            
            result = await session.execute(stmt)
            candidates = result.scalars().all()
            
            return [self._orm_to_candidate(c) for c in candidates]

    async def approve_candidate(
        self, candidate_id: int, template_name: str
    ) -> Optional[TemplateCandidate]:
        candidate = await self.get_candidate(candidate_id)
        if not candidate or candidate.status != "pending":
            return None

        async with self._db.session() as session:
            from plasmaagent.core.schema import TemplateMetric
            
            stmt = (
                update(TemplateMetric)
                .where(TemplateMetric.id == candidate_id)
                .values(
                    template_name=template_name,
                    metadata={
                        **candidate.metadata,
                        "status": "approved",
                        "reviewed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            )
            
            await session.execute(stmt)
            await session.commit()
            
            return await self.get_candidate(candidate_id)

    async def reject_candidate(
        self, candidate_id: int, reason: str = ""
    ) -> Optional[TemplateCandidate]:
        async with self._db.session() as session:
            from plasmaagent.core.schema import TemplateMetric
            
            candidate = await self.get_candidate(candidate_id)
            if not candidate or candidate.status != "pending":
                return None
            
            stmt = (
                update(TemplateMetric)
                .where(TemplateMetric.id == candidate_id)
                .values(
                    metadata={
                        **candidate.metadata,
                        "status": "rejected",
                        "reviewed_at": datetime.now(timezone.utc).isoformat(),
                        "rejection_reason": reason,
                    }
                )
            )
            
            await session.execute(stmt)
            await session.commit()
            
            return await self.get_candidate(candidate_id)

    async def detect_patterns(
        self, request: CandidateDetectionRequest
    ) -> CandidateDetectionReport:
        start = time.perf_counter()

        async with self._db.session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=request.scan_period_days)
            
            stmt = select(Task).where(
                and_(
                    Task.status == "COMPLETED",
                    Task.created_at >= cutoff_date,
                )
            ).order_by(Task.created_at.desc()).limit(1000)
            
            result = await session.execute(stmt)
            tasks = result.scalars().all()

        pattern_groups: Dict[str, Dict[str, Any]] = {}
        for task in tasks:
            if not task.commands:
                continue

            commands_raw = json.dumps(task.commands)
            pattern = self._extract_pattern(commands_raw)
            if not pattern:
                continue

            if pattern not in pattern_groups:
                pattern_groups[pattern] = {
                    "count": 0,
                    "example_task_id": task.id,
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
        async with self._db.session() as session:
            from plasmaagent.core.schema import TemplateMetric
            
            stmt = select(TemplateMetric).where(
                or_(
                    TemplateMetric.pattern == pattern,
                    and_(
                        TemplateMetric.metadata["status"].as_string() != "rejected",
                        TemplateMetric.pattern == pattern,
                    )
                )
            ).limit(1)
            
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

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

    def _orm_to_candidate(self, orm_obj) -> TemplateCandidate:
        metadata = orm_obj.metadata or {}
        commands = metadata.get("generated_commands", [])
        if isinstance(commands, str):
            commands = json.loads(commands)
        
        return TemplateCandidate(
            id=orm_obj.id,
            pattern=orm_obj.pattern,
            example_input=metadata.get("example_input", ""),
            generated_commands=commands,
            confidence=orm_obj.success_rate,
            frequency=orm_obj.total_executions,
            status=metadata.get("status", "pending"),
            source_task_id=metadata.get("source_task_id"),
            metadata=metadata,
            created_at=orm_obj.created_at,
            reviewed_at=datetime.fromisoformat(metadata["reviewed_at"]) if metadata.get("reviewed_at") else None,
        )
