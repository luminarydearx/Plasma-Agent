from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from plasmaagent.core.database import Database


class AuditAction(str):
    LOGIN = "login"
    LOGOUT = "logout"
    CREATE_USER = "create_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    CREATE_TASK = "create_task"
    UPDATE_TASK = "update_task"
    DELETE_TASK = "delete_task"
    EXECUTE_TASK = "execute_task"
    CREATE_SCHEDULE = "create_schedule"
    DELETE_SCHEDULE = "delete_schedule"
    UPDATE_CONFIG = "update_config"
    ACCESS_DENIED = "access_denied"


class AuditLogEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[UUID] = None
    username: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None

    class Config:
        frozen = True


class AuditLogQuery(BaseModel):
    user_id: Optional[UUID] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    success: Optional[bool] = None
    limit: int = Field(default=100, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)

    class Config:
        frozen = True


class AuditService:
    def __init__(self, db: Database):
        self.db = db

    async def log(
        self,
        action: str,
        user_id: Optional[UUID] = None,
        username: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> AuditLogEntry:
        entry = AuditLogEntry(
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
        )

        async with self.db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO audit_logs 
                (id, timestamp, user_id, username, action, resource_type, resource_id,
                 details, ip_address, user_agent, success, error_message)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                entry.id,
                entry.timestamp,
                entry.user_id,
                entry.username,
                entry.action,
                entry.resource_type,
                entry.resource_id,
                str(entry.details),
                entry.ip_address,
                entry.user_agent,
                entry.success,
                entry.error_message,
            )

        return entry

    async def query(self, query: AuditLogQuery) -> List[AuditLogEntry]:
        conditions = []
        values = []
        param_count = 1

        if query.user_id:
            conditions.append(f"user_id = ${param_count}")
            values.append(query.user_id)
            param_count += 1

        if query.action:
            conditions.append(f"action = ${param_count}")
            values.append(query.action)
            param_count += 1

        if query.resource_type:
            conditions.append(f"resource_type = ${param_count}")
            values.append(query.resource_type)
            param_count += 1

        if query.resource_id:
            conditions.append(f"resource_id = ${param_count}")
            values.append(query.resource_id)
            param_count += 1

        if query.start_time:
            conditions.append(f"timestamp >= ${param_count}")
            values.append(query.start_time)
            param_count += 1

        if query.end_time:
            conditions.append(f"timestamp <= ${param_count}")
            values.append(query.end_time)
            param_count += 1

        if query.success is not None:
            conditions.append(f"success = ${param_count}")
            values.append(query.success)
            param_count += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        values.extend([query.limit, query.offset])

        sql = f"""
            SELECT id, timestamp, user_id, username, action, resource_type, 
                   resource_id, details, ip_address, user_agent, success, error_message
            FROM audit_logs
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ${param_count} OFFSET ${param_count + 1}
        """

        async with self.db.connection() as conn:
            rows = await conn.fetch(sql, *values)
            entries = []
            for row in rows:
                details = row["details"]
                if isinstance(details, str):
                    import json
                    try:
                        details = json.loads(details)
                    except:
                        details = {}
                elif not isinstance(details, dict):
                    details = {}

                entries.append(
                    AuditLogEntry(
                        id=row["id"],
                        timestamp=row["timestamp"],
                        user_id=row["user_id"],
                        username=row["username"],
                        action=row["action"],
                        resource_type=row["resource_type"],
                        resource_id=row["resource_id"],
                        details=details,
                        ip_address=row["ip_address"],
                        user_agent=row["user_agent"],
                        success=row["success"],
                        error_message=row["error_message"],
                    )
                )
            return entries

    async def get_user_activity(
        self, user_id: UUID, limit: int = 100
    ) -> List[AuditLogEntry]:
        query = AuditLogQuery(user_id=user_id, limit=limit)
        return await self.query(query)

    async def get_resource_history(
        self, resource_type: str, resource_id: UUID, limit: int = 100
    ) -> List[AuditLogEntry]:
        query = AuditLogQuery(
            resource_type=resource_type, resource_id=resource_id, limit=limit
        )
        return await self.query(query)

    async def get_failed_actions(
        self, start_time: Optional[datetime] = None, limit: int = 100
    ) -> List[AuditLogEntry]:
        query = AuditLogQuery(
            success=False, start_time=start_time, limit=limit
        )
        return await self.query(query)
