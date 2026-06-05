from typing import Optional
from uuid import UUID

import typer

from plasmaagent.cli.theme import console
from plasmaagent.core.asyncio_compat import run_async
from plasmaagent.memory.models import MemoryType

memory_app = typer.Typer(
    name="memory",
    help="Memory system management",
    no_args_is_help=True,
)


@memory_app.command(name="stats")
def show_stats() -> None:
    async def get_stats() -> None:
        from plasmaagent.core.database import get_database
        from plasmaagent.memory.service import MemoryService

        db = get_database()
        await db.connect()

        try:
            async with db.connection() as conn:
                service = MemoryService(conn)
                stats = await service.get_stats()

                console.print("\n[bold #00D4FF]Memory System Statistics[/bold #00D4FF]\n")
                console.print(f"  Total Memories:       {stats.total_memories}")
                console.print(f"  Total Conversations:  {stats.total_conversations}")
                console.print(f"  Total Patterns:       {stats.total_patterns}")

                if stats.memories_by_type:
                    console.print("\n  [bold]By Type:[/bold]")
                    for mtype, count in stats.memories_by_type.items():
                        console.print(f"    {mtype:20s} {count}")

                console.print()
        finally:
            await db.disconnect()

    run_async(get_stats())


@memory_app.command(name="search")
def search_memories(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results"),
    memory_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type"),
) -> None:
    async def search() -> None:
        from plasmaagent.core.database import get_database
        from plasmaagent.memory.service import MemoryService

        db = get_database()
        await db.connect()

        try:
            async with db.connection() as conn:
                service = MemoryService(conn)

                mt = MemoryType(memory_type) if memory_type else None
                memories = await service.search_memories(query, limit=limit, memory_type=mt)

                if not memories:
                    console.print("\n[yellow]No memories found.[/yellow]\n")
                    return

                console.print(f"\n[bold #00D4FF]Found {len(memories)} memories:[/bold #00D4FF]\n")
                for mem in memories:
                    console.print(f"  [{mem.id}] ({mem.memory_type.value}) {mem.content[:80]}...")
                    if mem.metadata:
                        console.print(f"    metadata: {mem.metadata}")
                    console.print()
        finally:
            await db.disconnect()

    run_async(search())


@memory_app.command(name="add")
def add_memory(
    content: str = typer.Argument(..., help="Memory content"),
    memory_type: MemoryType = typer.Option(MemoryType.FACT, "--type", "-t", help="Memory type"),
    metadata_json: Optional[str] = typer.Option(None, "--metadata", "-m", help="JSON metadata"),
) -> None:
    import json

    async def add() -> None:
        from plasmaagent.core.database import get_database
        from plasmaagent.memory.service import MemoryService

        db = get_database()
        await db.connect()

        try:
            async with db.connection() as conn:
                service = MemoryService(conn)
                metadata = json.loads(metadata_json) if metadata_json else {}
                memory = await service.store_memory(content, memory_type, metadata=metadata)

                console.print(f"\n[bold green]✓ Memory stored[/bold green]\n")
                console.print(f"  ID:   {memory.id}")
                console.print(f"  Type: {memory.memory_type.value}")
                console.print(f"  Content: {memory.content[:100]}")
                console.print()
                await conn.commit()
        except json.JSONDecodeError as e:
            console.print(f"\n[red]Invalid JSON metadata: {e}[/red]\n")
            raise typer.Exit(1)
        finally:
            await db.disconnect()

    run_async(add())


@memory_app.command(name="delete")
def delete_memory(
    memory_id: str = typer.Argument(..., help="Memory ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    async def delete() -> None:
        from plasmaagent.core.database import get_database
        from plasmaagent.memory.service import MemoryService, MemoryNotFoundError

        db = get_database()
        await db.connect()

        try:
            try:
                uid = UUID(memory_id)
            except ValueError:
                console.print(f"\n[red]Invalid memory ID format: {memory_id}[/red]\n")
                raise typer.Exit(1)

            async with db.connection() as conn:
                service = MemoryService(conn)
                try:
                    await service.delete_memory(uid)
                    await conn.commit()
                    console.print(f"\n[bold green]✓ Memory deleted: {uid}[/bold green]\n")
                except MemoryNotFoundError:
                    console.print(f"\n[red]Memory not found: {uid}[/red]\n")
                    raise typer.Exit(1)
        finally:
            await db.disconnect()

    run_async(delete())


@memory_app.command(name="sessions")
def list_sessions(
    limit: int = typer.Option(20, "--limit", "-l", help="Max sessions"),
) -> None:
    async def list_s() -> None:
        from plasmaagent.core.database import get_database
        from plasmaagent.memory.conversation_service import ConversationService

        db = get_database()
        await db.connect()

        try:
            async with db.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT id, user_id, title, message_count, updated_at
                        FROM conversation_sessions
                        ORDER BY updated_at DESC
                        LIMIT %s
                        """,
                        (limit,)
                    )
                    rows = await cur.fetchall()

                if not rows:
                    console.print("\n[yellow]No conversation sessions found.[/yellow]\n")
                    return

                console.print(f"\n[bold #00D4FF]Conversation Sessions ({len(rows)}):[/bold #00D4FF]\n")
                for row in rows:
                    title = row[2] or "(untitled)"
                    console.print(f"  [{row[0]}] {title}")
                    console.print(f"    Messages: {row[3]} | Updated: {row[4]}")
                    console.print()
        finally:
            await db.disconnect()

    run_async(list_s())


@memory_app.command(name="patterns")
def list_patterns(
    limit: int = typer.Option(20, "--limit", "-l", help="Max patterns"),
    task_name: Optional[str] = typer.Option(None, "--name", "-n", help="Filter by task name"),
) -> None:
    async def list_p() -> None:
        from plasmaagent.core.database import get_database
        from plasmaagent.memory.pattern_service import PatternService

        db = get_database()
        await db.connect()

        try:
            async with db.connection() as conn:
                service = PatternService(conn)

                if task_name:
                    patterns = await service.find_by_task_name(task_name, limit=limit)
                else:
                    patterns = await service.get_top_patterns(limit=limit)

                if not patterns:
                    console.print("\n[yellow]No patterns found.[/yellow]\n")
                    return

                console.print(f"\n[bold #00D4FF]Task Patterns ({len(patterns)}):[/bold #00D4FF]\n")
                for p in patterns:
                    console.print(f"  [{p.id}] {p.task_name}")
                    console.print(f"    Commands: {len(p.commands)} | Success: {p.success_count} | Confidence: {p.confidence:.2f}")
                    console.print(f"    Avg Duration: {p.avg_duration_ms:.0f}ms")
                    console.print()
        finally:
            await db.disconnect()

    run_async(list_p())
