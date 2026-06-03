from __future__ import annotations

import re
import math
import statistics
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Any
from collections import Counter

from plasmaagent.core.database import Database
from plasmaagent.ai.suggestions.models import (
    Recommendation,
    SimilarTask,
    AnomalyReport,
    PerformanceHint,
    SuggestionType,
    Priority,
    SuggestionRequest,
    SuggestionBundle,
)


class SuggestionEngine:
    ANOMALY_COMMANDS_THRESHOLD = 50
    LONG_COMMAND_THRESHOLD = 500
    SLOW_EXECUTION_MS = 30000
    HIGH_FAILURE_RATE = 0.5
    SUSPICIOUS_PATTERNS = (
        r"rm\s+-rf\s+/",
        r"format\s+[a-zA-Z]:",
        r"del\s+/[sS]\s+/[qQ]",
        r"DROP\s+DATABASE",
        r"DROP\s+TABLE\s+\*",
        r"shutdown\s+-h\s+now",
        r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;",
    )

    def __init__(self, db: Database) -> None:
        self._db = db

    async def generate_bundle(self, request: SuggestionRequest) -> SuggestionBundle:
        recommendations: list[Recommendation] = []
        similar_tasks: list[SimilarTask] = []
        anomalies: list[AnomalyReport] = []
        hints: list[PerformanceHint] = []

        if request.task_id is not None:
            if request.include_next_actions:
                recommendations.extend(await self.suggest_next_actions(request.task_id))
            if request.include_similar:
                similar_tasks = await self.find_similar_tasks(
                    request.task_id, limit=request.max_similar
                )
            if request.include_anomalies:
                anomalies = await self.detect_anomalies(
                    request.task_id, threshold=request.anomaly_threshold
                )
            if request.include_performance:
                hints = await self.analyze_performance(request.task_id)

        if request.include_next_actions and request.task_id is None:
            recommendations.extend(await self.suggest_general_actions())

        total = len(recommendations) + len(similar_tasks) + len(anomalies) + len(hints)
        return SuggestionBundle(
            recommendations=recommendations,
            similar_tasks=similar_tasks,
            anomalies=anomalies,
            performance_hints=hints,
            total_suggestions=total,
            generated_at=datetime.now(timezone.utc),
        )

    async def suggest_next_actions(self, task_id: UUID) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, name, status, payload FROM tasks WHERE id = %s",
                (task_id,),
            )
            task = await cursor.fetchone()

        if task is None:
            return recommendations

        status = task["status"]
        now = datetime.now(timezone.utc)

        if status == "PENDING":
            recommendations.append(
                Recommendation(
                    id=uuid4(),
                    suggestion_type=SuggestionType.NEXT_ACTION,
                    priority=Priority.HIGH,
                    title="Execute pending task",
                    description=f"Task '{task['name']}' is ready to run",
                    confidence=0.95,
                    related_task_id=task_id,
                    metadata={"action": "run"},
                    created_at=now,
                )
            )
        elif status == "FAILED":
            recommendations.append(
                Recommendation(
                    id=uuid4(),
                    suggestion_type=SuggestionType.NEXT_ACTION,
                    priority=Priority.HIGH,
                    title="Retry failed task",
                    description=f"Task '{task['name']}' failed and can be retried",
                    confidence=0.85,
                    related_task_id=task_id,
                    metadata={"action": "retry"},
                    created_at=now,
                )
            )
        elif status == "COMPLETED":
            recommendations.append(
                Recommendation(
                    id=uuid4(),
                    suggestion_type=SuggestionType.NEXT_ACTION,
                    priority=Priority.LOW,
                    title="Clean up completed task",
                    description=f"Task '{task['name']}' completed successfully",
                    confidence=0.70,
                    related_task_id=task_id,
                    metadata={"action": "cleanup"},
                    created_at=now,
                )
            )
        elif status == "RUNNING":
            recommendations.append(
                Recommendation(
                    id=uuid4(),
                    suggestion_type=SuggestionType.NEXT_ACTION,
                    priority=Priority.MEDIUM,
                    title="Monitor running task",
                    description=f"Task '{task['name']}' is currently executing",
                    confidence=0.80,
                    related_task_id=task_id,
                    metadata={"action": "monitor"},
                    created_at=now,
                )
            )
        elif status == "CANCELLED":
            recommendations.append(
                Recommendation(
                    id=uuid4(),
                    suggestion_type=SuggestionType.NEXT_ACTION,
                    priority=Priority.MEDIUM,
                    title="Review cancelled task",
                    description=f"Task '{task['name']}' was cancelled",
                    confidence=0.65,
                    related_task_id=task_id,
                    metadata={"action": "review"},
                    created_at=now,
                )
            )

        return recommendations

    async def suggest_general_actions(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        now = datetime.now(timezone.utc)

        async with self._db.connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) AS cnt FROM tasks WHERE status = 'PENDING'"
            )
            pending = (await cursor.fetchone())["cnt"]

            cursor = await conn.execute(
                "SELECT COUNT(*) AS cnt FROM tasks WHERE status = 'FAILED'"
            )
            failed = (await cursor.fetchone())["cnt"]

        if pending > 0:
            recommendations.append(
                Recommendation(
                    id=uuid4(),
                    suggestion_type=SuggestionType.NEXT_ACTION,
                    priority=Priority.MEDIUM,
                    title=f"{pending} pending task(s) awaiting execution",
                    description="Run 'plasma task list' to see pending tasks",
                    confidence=0.90,
                    metadata={"pending_count": pending},
                    created_at=now,
                )
            )

        if failed > 0:
            recommendations.append(
                Recommendation(
                    id=uuid4(),
                    suggestion_type=SuggestionType.NEXT_ACTION,
                    priority=Priority.HIGH,
                    title=f"{failed} failed task(s) need attention",
                    description="Review and retry failed tasks",
                    confidence=0.90,
                    metadata={"failed_count": failed},
                    created_at=now,
                )
            )

        return recommendations

    async def find_similar_tasks(
        self, task_id: UUID, limit: int = 5
    ) -> list[SimilarTask]:
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                "SELECT payload FROM tasks WHERE id = %s", (task_id,)
            )
            source = await cursor.fetchone()

        if source is None or source["payload"] is None:
            return []

        source_commands = self._extract_commands(source["payload"])
        source_set = set(self._normalize_command(c) for c in source_commands)

        if not source_set:
            return []

        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, name, payload, updated_at
                FROM tasks
                WHERE id != %s AND payload IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 200
                """,
                (task_id,),
            )
            candidates = await cursor.fetchall()

        scored: list[SimilarTask] = []
        for candidate in candidates:
            cand_commands = self._extract_commands(candidate["payload"])
            cand_set = set(self._normalize_command(c) for c in cand_commands)

            if not cand_set:
                continue

            intersection = len(source_set & cand_set)
            union = len(source_set | cand_set)
            jaccard = intersection / union if union > 0 else 0.0

            if jaccard > 0.1:
                scored.append(
                    SimilarTask(
                        task_id=candidate["id"],
                        task_name=candidate["name"] or "",
                        similarity_score=round(jaccard, 4),
                        common_commands=intersection,
                        last_executed=candidate["updated_at"],
                    )
                )

        scored.sort(key=lambda x: x.similarity_score, reverse=True)
        return scored[:limit]

    async def detect_anomalies(
        self, task_id: UUID, threshold: float = 2.0
    ) -> list[AnomalyReport]:
        reports: list[AnomalyReport] = []

        async with self._db.connection() as conn:
            cursor = await conn.execute(
                "SELECT id, name, payload FROM tasks WHERE id = %s", (task_id,)
            )
            task = await cursor.fetchone()

        if task is None:
            return reports

        commands = self._extract_commands(task["payload"])

        for cmd in commands:
            for pattern in self.SUSPICIOUS_PATTERNS:
                if re.search(pattern, cmd, re.IGNORECASE):
                    reports.append(
                        AnomalyReport(
                            task_id=task_id,
                            anomaly_type="suspicious_command",
                            severity=Priority.CRITICAL,
                            description=f"Potentially dangerous command detected: {cmd[:200]}",
                            baseline_value=0.0,
                            observed_value=1.0,
                            deviation_factor=10.0,
                            recommendations=[
                                "Review command before execution",
                                "Consider safer alternatives",
                                "Verify target path/scope",
                            ],
                        )
                    )
                    break

        if len(commands) > self.ANOMALY_COMMANDS_THRESHOLD:
            reports.append(
                AnomalyReport(
                    task_id=task_id,
                    anomaly_type="excessive_commands",
                    severity=Priority.HIGH,
                    description=f"Task has {len(commands)} commands (threshold: {self.ANOMALY_COMMANDS_THRESHOLD})",
                    baseline_value=float(self.ANOMALY_COMMANDS_THRESHOLD),
                    observed_value=float(len(commands)),
                    deviation_factor=len(commands) / self.ANOMALY_COMMANDS_THRESHOLD,
                    recommendations=[
                        "Consider breaking into smaller tasks",
                        "Use task decomposition",
                    ],
                )
            )

        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT AVG(duration_ms) AS avg_ms, STDDEV(duration_ms) AS std_ms
                FROM task_steps
                WHERE task_id = %s AND duration_ms IS NOT NULL
                """,
                (task_id,),
            )
            stats = await cursor.fetchone()

            if stats and stats["avg_ms"] and stats["std_ms"]:
                avg = float(stats["avg_ms"])
                std = float(stats["std_ms"])

                if std > 0:
                    cursor = await conn.execute(
                        """
                        SELECT duration_ms FROM task_steps
                        WHERE task_id = %s AND duration_ms IS NOT NULL
                        """,
                        (task_id,),
                    )
                    rows = await cursor.fetchall()

                    for row in rows:
                        observed = float(row["duration_ms"])
                        z_score = abs(observed - avg) / std
                        if z_score >= threshold:
                            reports.append(
                                AnomalyReport(
                                    task_id=task_id,
                                    anomaly_type="execution_time_outlier",
                                    severity=Priority.MEDIUM,
                                    description=f"Execution time {observed:.0f}ms deviates {z_score:.2f}σ from mean {avg:.0f}ms",
                                    baseline_value=avg,
                                    observed_value=observed,
                                    deviation_factor=z_score,
                                    recommendations=[
                                        "Investigate slow command",
                                        "Check for resource contention",
                                    ],
                                )
                            )

        return reports

    async def analyze_performance(self, task_id: UUID) -> list[PerformanceHint]:
        hints: list[PerformanceHint] = []

        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT step_order, command, duration_ms
                FROM task_steps
                WHERE task_id = %s AND duration_ms IS NOT NULL
                ORDER BY step_order
                """,
                (task_id,),
            )
            steps = await cursor.fetchall()

        if not steps:
            return hints

        durations = [int(s["duration_ms"]) for s in steps]
        slow_steps = [
            (i, s) for i, s in enumerate(steps) if int(s["duration_ms"]) > self.SLOW_EXECUTION_MS
        ]

        if slow_steps:
            affected = [s["step_order"] for _, s in slow_steps]
            avg_slow = statistics.mean(int(s["duration_ms"]) for _, s in slow_steps)
            hints.append(
                PerformanceHint(
                    task_id=task_id,
                    hint_type="slow_commands",
                    description=f"{len(slow_steps)} command(s) take > {self.SLOW_EXECUTION_MS}ms (avg {avg_slow:.0f}ms)",
                    estimated_savings_ms=int(avg_slow * 0.3 * len(slow_steps)),
                    confidence=0.75,
                    affected_commands=affected,
                )
            )

        if len(durations) >= 3:
            variance = statistics.variance(durations)
            if variance > 1000000:
                hints.append(
                    PerformanceHint(
                        task_id=task_id,
                        hint_type="inconsistent_timing",
                        description="High variance in execution times suggests resource contention",
                        estimated_savings_ms=int(statistics.mean(durations) * 0.2),
                        confidence=0.60,
                        affected_commands=[s["step_order"] for s in steps],
                    )
                )

        long_commands = [
            (i, s)
            for i, s in enumerate(steps)
            if s["command"] and len(s["command"]) > self.LONG_COMMAND_THRESHOLD
        ]
        if long_commands:
            hints.append(
                PerformanceHint(
                    task_id=task_id,
                    hint_type="long_commands",
                    description=f"{len(long_commands)} command(s) exceed {self.LONG_COMMAND_THRESHOLD} chars",
                    estimated_savings_ms=100,
                    confidence=0.50,
                    affected_commands=[s["step_order"] for _, s in long_commands],
                )
            )

        return hints

    def _extract_commands(self, payload: Any) -> list[str]:
        if payload is None:
            return []
        if isinstance(payload, str):
            try:
                import json
                payload = json.loads(payload)
            except (ValueError, TypeError):
                return []
        if isinstance(payload, dict):
            commands = payload.get("commands", [])
            if isinstance(commands, list):
                return [str(c) for c in commands if c]
        return []

    def _normalize_command(self, cmd: str) -> str:
        cmd = cmd.strip().lower()
        cmd = re.sub(r"[\"'].*?[\"']", "", cmd)
        cmd = re.sub(r"\s+", " ", cmd)
        parts = cmd.split()
        return parts[0] if parts else cmd
