import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from datetime import datetime
from uuid import UUID

from plasmaagent.core.database import get_database
from plasmaagent.core.asyncio_compat import run_async
from plasmaagent.security.auth_service import AuthService, AuthenticationError
from plasmaagent.security.audit_service import AuditService, AuditLogQuery
from plasmaagent.security.models import UserCreate, UserRole, UserLogin

app = typer.Typer()
console = Console()




@app.command("create")
def create_user(
    username: str = typer.Option(..., help="Username"),
    password: str = typer.Option(..., help="Password", prompt=True, hide_input=True),
    email: Optional[str] = typer.Option(None, help="Email address"),
    role: str = typer.Option("user", help="Role: admin, user, readonly"),
    inactive: bool = typer.Option(False, help="Create as inactive user"),
):
    if role not in ["admin", "user", "readonly"]:
        console.print(f"[red]Error: Invalid role '{role}'. Must be admin, user, or readonly[/red]")
        raise typer.Exit(1)

    role_enum = UserRole(role)

    async def _create():
        db = get_database()
        await db.connect()
        auth = AuthService(db)
        audit = AuditService(db)

        try:
            user_data = UserCreate(
                username=username,
                email=email,
                password=password,
                role=role_enum,
                is_active=not inactive,
            )
            user = await auth.create_user(user_data)

            await audit.log(
                action="create_user",
                username=username,
                resource_type="user",
                resource_id=user.id,
                details={"role": role, "email": email},
                success=True,
            )

            console.print(f"[green]✓ User created successfully[/green]")
            console.print(f"  ID: {user.id}")
            console.print(f"  Username: {user.username}")
            console.print(f"  Email: {user.email or 'N/A'}")
            console.print(f"  Role: {user.role.value}")
            console.print(f"  Active: {user.is_active}")

        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
        finally:
            await db.disconnect()

    run_async(_create())


@app.command("list")
def list_users():
    async def _list():
        db = get_database()
        await db.connect()

        try:
            async with db.connection() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, username, email, role, is_active, created_at, last_login
                    FROM users
                    ORDER BY created_at DESC
                    """
                )

            if not rows:
                console.print("[yellow]No users found[/yellow]")
                return

            table = Table(title="Users")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Username", style="green")
            table.add_column("Email")
            table.add_column("Role")
            table.add_column("Active")
            table.add_column("Created")
            table.add_column("Last Login")

            for row in rows:
                table.add_row(
                    str(row["id"])[:8] + "...",
                    row["username"],
                    row["email"] or "N/A",
                    row["role"],
                    "✓" if row["is_active"] else "✗",
                    row["created_at"].strftime("%Y-%m-%d %H:%M") if row["created_at"] else "N/A",
                    row["last_login"].strftime("%Y-%m-%d %H:%M") if row["last_login"] else "Never",
                )

            console.print(table)

        finally:
            await db.disconnect()

    run_async(_list())


@app.command("delete")
def delete_user(
    user_id: str = typer.Argument(..., help="User ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    try:
        uid = UUID(user_id)
    except ValueError:
        console.print(f"[red]Error: Invalid user ID format: {user_id}[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Delete user {user_id}?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    async def _delete():
        db = get_database()
        await db.connect()
        audit = AuditService(db)

        try:
            async with db.connection() as conn:
                result = await conn.execute("DELETE FROM users WHERE id = $1", uid)

            if result == "DELETE 1":
                await audit.log(
                    action="delete_user",
                    resource_type="user",
                    resource_id=uid,
                    success=True,
                )
                console.print(f"[green]✓ User deleted: {user_id}[/green]")
            else:
                console.print(f"[yellow]User not found: {user_id}[/yellow]")

        finally:
            await db.disconnect()

    run_async(_delete())


@app.command("disable")
def disable_user(user_id: str = typer.Argument(..., help="User ID")):
    try:
        uid = UUID(user_id)
    except ValueError:
        console.print(f"[red]Error: Invalid user ID format: {user_id}[/red]")
        raise typer.Exit(1)

    async def _disable():
        db = get_database()
        await db.connect()
        audit = AuditService(db)

        try:
            async with db.connection() as conn:
                result = await conn.execute(
                    "UPDATE users SET is_active = FALSE, updated_at = $1 WHERE id = $2",
                    datetime.utcnow(),
                    uid,
                )

            if result == "UPDATE 1":
                await audit.log(
                    action="update_user",
                    resource_type="user",
                    resource_id=uid,
                    details={"is_active": False},
                    success=True,
                )
                console.print(f"[green]✓ User disabled: {user_id}[/green]")
            else:
                console.print(f"[yellow]User not found: {user_id}[/yellow]")

        finally:
            await db.disconnect()

    run_async(_disable())


@app.command("enable")
def enable_user(user_id: str = typer.Argument(..., help="User ID")):
    try:
        uid = UUID(user_id)
    except ValueError:
        console.print(f"[red]Error: Invalid user ID format: {user_id}[/red]")
        raise typer.Exit(1)

    async def _enable():
        db = get_database()
        await db.connect()
        audit = AuditService(db)

        try:
            async with db.connection() as conn:
                result = await conn.execute(
                    "UPDATE users SET is_active = TRUE, updated_at = $1 WHERE id = $2",
                    datetime.utcnow(),
                    uid,
                )

            if result == "UPDATE 1":
                await audit.log(
                    action="update_user",
                    resource_type="user",
                    resource_id=uid,
                    details={"is_active": True},
                    success=True,
                )
                console.print(f"[green]✓ User enabled: {user_id}[/green]")
            else:
                console.print(f"[yellow]User not found: {user_id}[/yellow]")

        finally:
            await db.disconnect()

    run_async(_enable())


@app.command("audit")
def show_audit_logs(
    limit: int = typer.Option(50, help="Number of logs to show"),
    action: Optional[str] = typer.Option(None, help="Filter by action"),
    username: Optional[str] = typer.Option(None, help="Filter by username"),
    failed: bool = typer.Option(False, help="Show only failed actions"),
):
    async def _show():
        db = get_database()
        await db.connect()
        audit = AuditService(db)

        try:
            query = AuditLogQuery(
                limit=limit,
                action=action,
                username=username,
                success=False if failed else None,
            )
            logs = await audit.query(query)

            if not logs:
                console.print("[yellow]No audit logs found[/yellow]")
                return

            table = Table(title=f"Audit Logs (last {len(logs)})")
            table.add_column("Timestamp", style="cyan", no_wrap=True)
            table.add_column("User", style="green")
            table.add_column("Action")
            table.add_column("Resource")
            table.add_column("Success")
            table.add_column("Details")

            for log in logs:
                table.add_row(
                    log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    log.username or "N/A",
                    log.action,
                    f"{log.resource_type}:{str(log.resource_id)[:8] if log.resource_id else 'N/A'}",
                    "✓" if log.success else "✗",
                    str(log.details)[:50] if log.details else "",
                )

            console.print(table)

        finally:
            await db.disconnect()

    run_async(_show())
