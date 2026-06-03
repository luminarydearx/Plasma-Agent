from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from plasmaagent.ai.templates.models import (
    RollbackReport,
    TemplateVersion,
    TemplateVersionCreate,
)
from plasmaagent.core.database import Database


_ADLER32_MOD = 2**31


class TemplateVersionService:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create_version(self, data: TemplateVersionCreate) -> TemplateVersion:
        async with self._db.transaction() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                lock_key = self._template_lock_key(data.template_id)
                await cursor.execute(
                    "SELECT pg_advisory_xact_lock(%s)",
                    (lock_key,),
                )

                await cursor.execute(
                    """
                    SELECT COALESCE(MAX(version_number), 0) AS max_version
                    FROM template_versions
                    WHERE template_id = %s
                    """,
                    (data.template_id,),
                )
                row = await cursor.fetchone()
                max_version = (row["max_version"] if row and row["max_version"] is not None else 0)
                version_number = max_version + 1

                version_id = uuid.uuid4()
                await cursor.execute(
                    """
                    INSERT INTO template_versions
                        (id, template_id, version_number, commands, pattern_name,
                         confidence, change_description, created_by, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    RETURNING *
                    """,
                    (
                        version_id,
                        data.template_id,
                        version_number,
                        json.dumps(list(data.commands)),
                        data.pattern_name,
                        data.confidence,
                        data.change_description,
                        data.created_by,
                    ),
                )
                row = await cursor.fetchone()
                if not row:
                    raise RuntimeError("Failed to create template version")
                return self._row_to_model(row)

    async def list_versions(
        self,
        template_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TemplateVersion]:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT * FROM template_versions
                    WHERE template_id = %s
                    ORDER BY version_number DESC
                    LIMIT %s OFFSET %s
                    """,
                    (template_id, limit, offset),
                )
                rows = await cursor.fetchall()
                return [self._row_to_model(row) for row in rows] if rows else []

    async def get_version(self, version_id: UUID) -> TemplateVersion | None:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    "SELECT * FROM template_versions WHERE id = %s",
                    (version_id,),
                )
                row = await cursor.fetchone()
                return self._row_to_model(row) if row else None

    async def get_latest_version(self, template_id: UUID) -> TemplateVersion | None:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT * FROM template_versions
                    WHERE template_id = %s
                    ORDER BY version_number DESC
                    LIMIT 1
                    """,
                    (template_id,),
                )
                row = await cursor.fetchone()
                return self._row_to_model(row) if row else None

    async def get_version_by_number(
        self, template_id: UUID, version_number: int
    ) -> TemplateVersion | None:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT * FROM template_versions
                    WHERE template_id = %s AND version_number = %s
                    """,
                    (template_id, version_number),
                )
                row = await cursor.fetchone()
                return self._row_to_model(row) if row else None

    async def rollback(
        self,
        template_id: UUID,
        target_version_number: int,
        created_by: str | None = None,
    ) -> RollbackReport:
        source_version = await self.get_version_by_number(
            template_id, target_version_number
        )
        if not source_version:
            raise ValueError(
                f"Version {target_version_number} not found for template {template_id}"
            )

        current_latest = await self.get_latest_version(template_id)
        from_version = current_latest.version_number if current_latest else 0

        rollback_data = TemplateVersionCreate(
            template_id=template_id,
            commands=source_version.commands,
            pattern_name=source_version.pattern_name,
            confidence=source_version.confidence,
            change_description=f"Rollback to version {target_version_number}",
            created_by=created_by,
        )

        new_version = await self.create_version(rollback_data)

        return RollbackReport(
            template_id=template_id,
            from_version=from_version,
            to_version=target_version_number,
            new_version_number=new_version.version_number,
            success=True,
        )

    async def count_versions(self, template_id: UUID) -> int:
        async with self._db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT COUNT(*) AS count FROM template_versions
                    WHERE template_id = %s
                    """,
                    (template_id,),
                )
                row = await cursor.fetchone()
                return row["count"] if row else 0

    async def delete_version(self, version_id: UUID) -> bool:
        async with self._db.transaction() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "DELETE FROM template_versions WHERE id = %s",
                    (version_id,),
                )
                return cursor.rowcount > 0

    @staticmethod
    def _template_lock_key(template_id: UUID) -> int:
        digest = hashlib.md5(str(template_id).encode(), usedforsecurity=False).digest()
        raw = int.from_bytes(digest[:8], byteorder="big", signed=False)
        return (raw % _ADLER32_MOD)

    def _row_to_model(self, row: dict[str, Any]) -> TemplateVersion:
        commands = row["commands"]
        if isinstance(commands, list):
            commands = tuple(commands)
        elif isinstance(commands, str):
            commands = tuple(json.loads(commands))
        return TemplateVersion(
            id=row["id"],
            template_id=row["template_id"],
            version_number=row["version_number"],
            commands=commands,
            pattern_name=row["pattern_name"],
            confidence=row["confidence"],
            change_description=row.get("change_description"),
            created_at=row["created_at"],
            created_by=row.get("created_by"),
        )
