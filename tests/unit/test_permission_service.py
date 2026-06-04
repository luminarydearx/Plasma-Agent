import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from plasmaagent.security.permission_service import PermissionService
from plasmaagent.security.audit_service import AuditService
from plasmaagent.security.models import UserRole


class TestPermissionService:
    @pytest.fixture
    def permission_service(self):
        return PermissionService()

    @pytest.fixture
    def permission_service_with_audit(self):
        audit_service = MagicMock(spec=AuditService)
        audit_service.log = AsyncMock()
        return PermissionService(audit_service=audit_service)

    def test_admin_has_full_permissions(self, permission_service):
        assert permission_service.has_permission(UserRole.ADMIN, "users", "create")
        assert permission_service.has_permission(UserRole.ADMIN, "users", "delete")
        assert permission_service.has_permission(UserRole.ADMIN, "tasks", "execute")
        assert permission_service.has_permission(UserRole.ADMIN, "config", "update")

    def test_user_permissions(self, permission_service):
        assert permission_service.has_permission(UserRole.USER, "tasks", "create")
        assert permission_service.has_permission(UserRole.USER, "tasks", "execute")
        assert permission_service.has_permission(UserRole.USER, "users", "read")
        
        assert not permission_service.has_permission(UserRole.USER, "users", "delete")
        assert not permission_service.has_permission(UserRole.USER, "config", "update")

    def test_readonly_permissions(self, permission_service):
        assert permission_service.has_permission(UserRole.READONLY, "tasks", "read")
        assert permission_service.has_permission(UserRole.READONLY, "tasks", "list")
        
        assert not permission_service.has_permission(UserRole.READONLY, "tasks", "create")
        assert not permission_service.has_permission(UserRole.READONLY, "tasks", "execute")
        assert not permission_service.has_permission(UserRole.READONLY, "tasks", "delete")

    def test_can_read(self, permission_service):
        assert permission_service.can_read(UserRole.ADMIN, "tasks")
        assert permission_service.can_read(UserRole.USER, "tasks")
        assert permission_service.can_read(UserRole.READONLY, "tasks")

    def test_can_create(self, permission_service):
        assert permission_service.can_create(UserRole.ADMIN, "tasks")
        assert permission_service.can_create(UserRole.USER, "tasks")
        assert not permission_service.can_create(UserRole.READONLY, "tasks")

    def test_can_update(self, permission_service):
        assert permission_service.can_update(UserRole.ADMIN, "users")
        assert not permission_service.can_update(UserRole.USER, "users")
        assert not permission_service.can_update(UserRole.READONLY, "users")

    def test_can_delete(self, permission_service):
        assert permission_service.can_delete(UserRole.ADMIN, "tasks")
        assert permission_service.can_delete(UserRole.USER, "tasks")
        assert not permission_service.can_delete(UserRole.READONLY, "tasks")

    def test_can_execute(self, permission_service):
        assert permission_service.can_execute(UserRole.ADMIN, "tasks")
        assert permission_service.can_execute(UserRole.USER, "tasks")
        assert not permission_service.can_execute(UserRole.READONLY, "tasks")

    def test_get_allowed_actions(self, permission_service):
        actions = permission_service.get_allowed_actions(UserRole.USER, "tasks")
        
        assert "create" in actions
        assert "read" in actions
        assert "execute" in actions
        assert "delete" in actions

    def test_get_allowed_actions_readonly(self, permission_service):
        actions = permission_service.get_allowed_actions(UserRole.READONLY, "tasks")
        
        assert "read" in actions
        assert "list" in actions
        assert "create" not in actions
        assert "execute" not in actions

    def test_check_permission_allowed(self, permission_service):
        user_id = uuid4()
        result = permission_service.check_permission(
            user_id=user_id,
            username="testuser",
            role=UserRole.USER,
            resource="tasks",
            action="create",
        )
        
        assert result is True

    def test_check_permission_denied(self, permission_service):
        user_id = uuid4()
        result = permission_service.check_permission(
            user_id=user_id,
            username="testuser",
            role=UserRole.READONLY,
            resource="tasks",
            action="create",
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_check_permission_denied_logs_audit(self, permission_service_with_audit):
        user_id = uuid4()
        result = permission_service_with_audit.check_permission(
            user_id=user_id,
            username="testuser",
            role=UserRole.READONLY,
            resource="tasks",
            action="create",
            ip_address="127.0.0.1",
        )
        
        assert result is False
        import asyncio
        await asyncio.sleep(0.01)

    def test_add_permission(self, permission_service):
        permission_service.add_permission(
            UserRole.READONLY, "custom_resource", ["read", "list"]
        )
        
        assert permission_service.has_permission(UserRole.READONLY, "custom_resource", "read")
        assert permission_service.has_permission(UserRole.READONLY, "custom_resource", "list")

    def test_add_permission_to_existing_resource(self, permission_service):
        permission_service.add_permission(UserRole.USER, "tasks", ["export"])
        
        assert permission_service.has_permission(UserRole.USER, "tasks", "create")
        assert permission_service.has_permission(UserRole.USER, "tasks", "export")

    def test_remove_permission(self, permission_service):
        permission_service.remove_permission(UserRole.USER, "tasks", ["delete"])
        
        assert permission_service.has_permission(UserRole.USER, "tasks", "create")
        assert not permission_service.has_permission(UserRole.USER, "tasks", "delete")

    def test_remove_all_permissions(self, permission_service):
        permission_service.remove_permission(
            UserRole.READONLY, "tasks", ["read", "list"]
        )
        
        assert not permission_service.has_permission(UserRole.READONLY, "tasks", "read")
        assert not permission_service.has_permission(UserRole.READONLY, "tasks", "list")

    def test_get_permissions_for_role(self, permission_service):
        permissions = permission_service.get_permissions_for_role(UserRole.ADMIN)
        
        assert len(permissions) > 0
        resources = [p.resource for p in permissions]
        assert "users" in resources
        assert "tasks" in resources

    def test_unknown_role_has_no_permissions(self, permission_service):
        permissions = permission_service.get_permissions_for_role("unknown_role")
        assert len(permissions) == 0

    def test_check_permission_unknown_role(self, permission_service):
        result = permission_service.check_permission(
            user_id=uuid4(),
            username="test",
            role="unknown_role",
            resource="tasks",
            action="read",
        )
        assert result is False
