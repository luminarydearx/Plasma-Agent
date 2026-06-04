from typing import Dict, List, Set, Optional
from uuid import UUID
from plasmaagent.security.models import UserRole, Permission
from plasmaagent.security.audit_service import AuditService, AuditAction


class PermissionService:
    def __init__(self, audit_service: Optional[AuditService] = None):
        self.audit_service = audit_service
        self._role_permissions: Dict[str, List[Permission]] = {
            UserRole.ADMIN: [
                Permission(resource="users", actions=["create", "read", "update", "delete", "list"]),
                Permission(resource="tasks", actions=["create", "read", "update", "delete", "execute", "list"]),
                Permission(resource="schedules", actions=["create", "read", "update", "delete", "list"]),
                Permission(resource="audit_logs", actions=["read", "list"]),
                Permission(resource="config", actions=["read", "update"]),
                Permission(resource="metrics", actions=["read"]),
            ],
            UserRole.USER: [
                Permission(resource="users", actions=["read"]),
                Permission(resource="tasks", actions=["create", "read", "update", "delete", "execute", "list"]),
                Permission(resource="schedules", actions=["create", "read", "update", "delete", "list"]),
                Permission(resource="audit_logs", actions=["read"]),
                Permission(resource="config", actions=["read"]),
                Permission(resource="metrics", actions=["read"]),
            ],
            UserRole.READONLY: [
                Permission(resource="users", actions=["read"]),
                Permission(resource="tasks", actions=["read", "list"]),
                Permission(resource="schedules", actions=["read", "list"]),
                Permission(resource="audit_logs", actions=["read"]),
                Permission(resource="config", actions=["read"]),
                Permission(resource="metrics", actions=["read"]),
            ],
        }

    def get_permissions_for_role(self, role: str) -> List[Permission]:
        return self._role_permissions.get(role, [])

    def has_permission(
        self, role: str, resource: str, action: str
    ) -> bool:
        permissions = self.get_permissions_for_role(role)
        for perm in permissions:
            if perm.resource == resource and action in perm.actions:
                return True
        return False

    def check_permission(
        self,
        user_id: UUID,
        username: str,
        role: str,
        resource: str,
        action: str,
        ip_address: Optional[str] = None,
    ) -> bool:
        if self.has_permission(role, resource, action):
            return True

        if self.audit_service:
            import asyncio
            asyncio.create_task(
                self.audit_service.log(
                    action=AuditAction.ACCESS_DENIED,
                    user_id=user_id,
                    username=username,
                    resource_type=resource,
                    details={"attempted_action": action},
                    ip_address=ip_address,
                    success=False,
                    error_message=f"Permission denied: {action} on {resource}",
                )
            )

        return False

    def get_allowed_actions(self, role: str, resource: str) -> Set[str]:
        permissions = self.get_permissions_for_role(role)
        for perm in permissions:
            if perm.resource == resource:
                return set(perm.actions)
        return set()

    def can_read(self, role: str, resource: str) -> bool:
        return self.has_permission(role, resource, "read")

    def can_create(self, role: str, resource: str) -> bool:
        return self.has_permission(role, resource, "create")

    def can_update(self, role: str, resource: str) -> bool:
        return self.has_permission(role, resource, "update")

    def can_delete(self, role: str, resource: str) -> bool:
        return self.has_permission(role, resource, "delete")

    def can_execute(self, role: str, resource: str) -> bool:
        return self.has_permission(role, resource, "execute")

    def add_permission(self, role: str, resource: str, actions: List[str]) -> None:
        if role not in self._role_permissions:
            self._role_permissions[role] = []

        permissions = self._role_permissions[role]
        for perm in permissions:
            if perm.resource == resource:
                existing_actions = set(perm.actions)
                existing_actions.update(actions)
                perm_dict = perm.dict()
                perm_dict["actions"] = list(existing_actions)
                permissions[permissions.index(perm)] = Permission(**perm_dict)
                return

        permissions.append(Permission(resource=resource, actions=actions))

    def remove_permission(self, role: str, resource: str, actions: List[str]) -> bool:
        if role not in self._role_permissions:
            return False

        permissions = self._role_permissions[role]
        for perm in permissions:
            if perm.resource == resource:
                existing_actions = set(perm.actions)
                existing_actions.difference_update(actions)
                if not existing_actions:
                    permissions.remove(perm)
                else:
                    perm_dict = perm.dict()
                    perm_dict["actions"] = list(existing_actions)
                    permissions[permissions.index(perm)] = Permission(**perm_dict)
                return True
        return False
