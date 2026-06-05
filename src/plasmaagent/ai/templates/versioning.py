from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any
from uuid import UUID
from datetime import datetime, timezone

from plasmaagent.ai.templates.models import (
    RollbackReport,
    TemplateVersion,
    TemplateVersionCreate,
)
from plasmaagent.core.database import Database


class TemplateVersionService:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create_version(self, data: TemplateVersionCreate) -> TemplateVersion:
        version_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        max_row = await self._db.fetch_one(
            """
            SELECT COALESCE(MAX(version_number), 0) AS max_version
            FROM template_versions
            WHERE template_id = :tid
            """,
            {"tid": str(data.template_id)},
        )
        max_version = (max_row["max_version"] if max_row and max_row["max_version"] is not None else 0)
        version_number = max_version + 1

        await self._db.execute(
            """
            INSERT INTO template_versions
                (id, template_id, version_number, commands, pattern_name,
                 confidence, change_description, created_by, created_at)
            VALUES (:id, :tid, :vnum, :cmds, :pname, :conf, :desc, :by, :now)
            """,
            {
                "id": version_id,
                "tid": str(data.template_id),
                "vnum": version_number,
                "cmds": json.dumps(list(data.commands)),
                "pname": data.pattern_name,
                "conf": data.confidence,
                "desc": data.change_description or "",
                "by": data.created_by or "",
                "now": now,
            },
        )

        return TemplateVersion(
            id=version_id,
            template_id=str(data.template_id),
            version_number=version_number,
            commands=tuple(data.commands),
            pattern_name=data.pattern_name,
            confidence=data.confidence,
            change_description=data.change_description,
            created_at=now,
            created_by=data.created_by,
        )

    async def list_versions(
        self,
        template_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TemplateVersion]:
        rows = await self._db.fetch_all(
            """
            SELECT * FROM template_versions
            WHERE template_id = :tid
            ORDER BY version_number DESC
            LIMIT :limit OFFSET :offset
            """,
            {"tid": str(template_id), "limit": limit, "offset": offset},
        )
        return [self._row_to_model(row) for row in rows] if rows else []

    async def get_version(self, version_id: UUID) -> TemplateVersion | None:
        row = await self._db.fetch_one(
            "SELECT * FROM template_versions WHERE id = :id",
            {"id": str(version_id)},
        )
        return self._row_to_model(row) if row else None

    async def get_latest_version(self, template_id: UUID) -> TemplateVersion | None:
        row = await self._db.fetch_one(
            """
            SELECT * FROM template_versions
            WHERE template_id = :tid
            ORDER BY version_number DESC
            LIMIT 1
            """,
            {"tid": str(template_id)},
        )
        return self._row_to_model(row) if row else None

    async def get_version_by_number(
        self, template_id: UUID, version_number: int
    ) -> TemplateVersion | None:
        row = await self._db.fetch_one(
            """
            SELECT * FROM template_versions
            WHERE template_id = :tid AND version_number = :vnum
            """,
            {"tid": str(template_id), "vnum": version_number},
        )
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
            template_id=str(template_id),
            from_version=from_version,
            to_version=target_version_number,
            new_version_number=new_version.version_number,
            success=True,
        )

    async def count_versions(self, template_id: UUID) -> int:
        row = await self._db.fetch_one(
            """
            SELECT COUNT(*) AS count FROM template_versions
            WHERE template_id = :tid
            """,
            {"tid": str(template_id)},
        )
        return row["count"] if row else 0

    async def delete_version(self, version_id: UUID) -> bool:
        async with self._db.transaction() as conn:
            from sqlalchemy import text
            result = await conn.execute(
                text("DELETE FROM template_versions WHERE id = :id"),
                {"id": str(version_id)},
            )
            return result.rowcount > 0

    def _row_to_model(self, row: dict[str, Any]) -> TemplateVersion:
        commands = row.get("commands")
        if isinstance(commands, list):
            commands = tuple(commands)
        elif isinstance(commands, str):
            try:
                commands = tuple(json.loads(commands))
            except json.JSONDecodeError:
                commands = ()
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
