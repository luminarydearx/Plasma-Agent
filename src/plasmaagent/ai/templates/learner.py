from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from typing import Any

from psycopg.rows import dict_row

from plasmaagent.ai.templates.models import (
    LearnedTemplate,
    LearningReport,
    TemplateCandidate,
    TemplateSource,
)
from plasmaagent.core.database import Database

MIN_FREQUENCY = 3
MIN_SUCCESS_RATE = 0.7
MIN_CONFIDENCE = 0.5
MAX_PATTERN_LENGTH = 500
COMMAND_SIMILARITY_THRESHOLD = 0.8


class TemplateLearner:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def analyze_tasks(
        self,
        min_frequency: int = MIN_FREQUENCY,
        min_success_rate: float = MIN_SUCCESS_RATE,
        limit: int = 1000,
    ) -> LearningReport:
        start_time = time.time()

        tasks = await self._fetch_successful_tasks(limit)
        command_groups = self._group_by_commands(tasks)
        candidates = self._build_candidates(command_groups, min_frequency, min_success_rate)
        new_count, updated_count = await self._persist_candidates(candidates)

        duration_ms = int((time.time() - start_time) * 1000)

        return LearningReport(
            total_tasks_analyzed=len(tasks),
            successful_tasks=len(tasks),
            candidates_found=len(candidates),
            new_templates=new_count,
            updated_templates=updated_count,
            candidates=tuple(candidates),
            analysis_duration_ms=duration_ms,
        )

    async def _fetch_successful_tasks(self, limit: int) -> list[dict[str, Any]]:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT t.id, t.name, t.description, t.payload,
                           COUNT(ts.id) as step_count
                    FROM tasks t
                    LEFT JOIN task_steps ts ON t.id = ts.task_id
                    WHERE t.status = 'COMPLETED'
                      AND t.payload IS NOT NULL
                    GROUP BY t.id, t.name, t.description, t.payload
                    HAVING COUNT(ts.id) > 0
                    ORDER BY t.created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = await cursor.fetchall()
                return list(rows) if rows else []

    def _group_by_commands(
        self, tasks: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for task in tasks:
            payload = task.get("payload")
            if not payload:
                continue

            commands = payload.get("commands", [])
            if not commands:
                continue

            normalized = self._normalize_commands(commands)
            key = "||".join(normalized)
            groups[key].append(task)

        return dict(groups)

    def _normalize_commands(self, commands: list[str]) -> list[str]:
        normalized = []
        for cmd in commands:
            if not isinstance(cmd, str):
                continue
            cleaned = cmd.strip().lower()
            cleaned = re.sub(r"\s+", " ", cleaned)
            cleaned = self._remove_volatile_parts(cleaned)
            if cleaned and len(cleaned) <= MAX_PATTERN_LENGTH:
                normalized.append(cleaned)
        return normalized

    def _remove_volatile_parts(self, command: str) -> str:
        command = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "<DATE>", command)
        command = re.sub(r"\b\d{2}:\d{2}:\d{2}\b", "<TIME>", command)
        command = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<UUID>", command)
        command = re.sub(r"\b\d+\b", "<NUM>", command)
        command = re.sub(r"'[^']*'", "'<STR>'", command)
        command = re.sub(r'"[^"]*"', '"<STR>"', command)
        return command

    def _build_candidates(
        self,
        command_groups: dict[str, list[dict[str, Any]]],
        min_frequency: int,
        min_success_rate: float,
    ) -> list[TemplateCandidate]:
        candidates = []

        for command_key, tasks in command_groups.items():
            if len(tasks) < min_frequency:
                continue

            commands = command_key.split("||")
            if not commands:
                continue

            pattern_name = self._generate_pattern_name(commands)
            task_ids = tuple(str(t["id"]) for t in tasks[:10])

            candidate = TemplateCandidate(
                pattern_name=pattern_name,
                commands=tuple(commands),
                frequency=len(tasks),
                success_rate=1.0,
                avg_duration_ms=0,
                confidence=min(1.0, len(tasks) / 10.0),
                source=TemplateSource.LEARNED,
                sample_task_ids=task_ids,
            )
            candidates.append(candidate)

        candidates.sort(key=lambda c: (c.frequency, c.confidence), reverse=True)
        return candidates

    def _generate_pattern_name(self, commands: list[str]) -> str:
        if not commands:
            return "unknown_pattern"

        first_cmd = commands[0]
        parts = first_cmd.split()

        name_parts = []
        for part in parts[:3]:
            if part.startswith("<") and part.endswith(">"):
                continue
            if part in ("echo", "cat", "ls", "cd", "mkdir", "rm", "cp", "mv"):
                name_parts.append(part)
            elif re.match(r"^[a-z]+$", part):
                name_parts.append(part)

        if not name_parts:
            name_parts = ["pattern"]

        name = "_".join(name_parts[:3])
        return name[:100]

    async def _persist_candidates(
        self, candidates: list[TemplateCandidate]
    ) -> tuple[int, int]:
        new_count = 0
        updated_count = 0

        async with self._db.transaction() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                for candidate in candidates:
                    await cursor.execute(
                        """
                        SELECT id FROM template_metrics
                        WHERE template_name = %s AND pattern = %s
                        """,
                        (candidate.pattern_name, candidate.commands[0] if candidate.commands else ""),
                    )
                    existing = await cursor.fetchone()

                    if existing:
                        await cursor.execute(
                            """
                            UPDATE template_metrics
                            SET usage_count = usage_count + %s,
                                success_count = success_count + %s,
                                avg_confidence = %s,
                                updated_at = NOW()
                            WHERE id = %s
                            """,
                            (
                                candidate.frequency,
                                int(candidate.frequency * candidate.success_rate),
                                candidate.confidence,
                                existing["id"],
                            ),
                        )
                        updated_count += 1
                    else:
                        await cursor.execute(
                            """
                            INSERT INTO template_metrics
                                (template_name, pattern, usage_count, success_count,
                                 failure_count, avg_confidence, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                            """,
                            (
                                candidate.pattern_name,
                                candidate.commands[0] if candidate.commands else "",
                                candidate.frequency,
                                int(candidate.frequency * candidate.success_rate),
                                0,
                                candidate.confidence,
                            ),
                        )
                        new_count += 1

        return new_count, updated_count

    def get_learned_templates(self) -> list[LearnedTemplate]:
        return []
