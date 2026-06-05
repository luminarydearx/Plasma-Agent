# 📘 FASE.md - PlasmaAgent Development Roadmap

**Last Updated:** 2026-06-05 16:45  
**Current Phase:** Phase 5.1 - Memory System  
**Status:** 🟢 IN PROGRESS (Task 5.1.3 COMPLETE)  
**Next Task:** 5.1.4 - Conversation Service

---

## 🎯 CURRENT FOCUS: Phase 5.1 - Memory System

### 📍 Current Status
- **Task 5.1.1:** ✅ COMPLETE - Memory Models (27 tests)
- **Task 5.1.2:** ✅ COMPLETE - Migration 012 (tables created)
- **Task 5.1.3:** ✅ COMPLETE - Memory Service (19 tests)
- **Task 5.1.4:** ⏳ NEXT - Conversation Service
- **Total Tests:** 46 new tests (27 + 19)

### 🚨 CRITICAL INSTRUCTIONS FOR LOCAL AI (Qwen2.5-Coder-7B)

**YOU MUST:**
1. Read this entire FASE.md before coding
2. Check `git status` for uncommitted changes
3. Run `uv run pytest tests/unit -q` to verify baseline (should be 1134+ tests)
4. Follow EXACT patterns from existing code (see examples below)
5. Write tests for EVERY function you implement
6. Update this FASE.md after completing each task
7. **NO COMMENTS IN CODE** - Not even docstrings. Clean code only.
8. Use `psycopg` (NOT `asyncpg`) for database operations

**YOU MUST NOT:**
- Use inline comments (# comment)
- Use docstrings (""" comment """)
- Use asyncio.run() in CLI (use run_async() helper)
- Skip tests
- Push without running tests
- Modify files outside scope of current task
- Use asyncpg (project uses psycopg)

---

## ✅ Completed Tasks (Phase 5.1)

### Task 5.1.1: Memory Models ✅ COMPLETE

**Status:** DONE  
**Commit:** `e0a550b`  
**Files Created:**
- `src/plasmaagent/memory/models.py` (3.6 KB)
- `src/plasmaagent/memory/__init__.py` (344 B)
- `tests/unit/test_memory_models.py` (27 tests)

**What Was Implemented:**
```python
MemoryType (enum): CONVERSATION, PATTERN, FACT, PREFERENCE, TASK_RESULT
Memory (BaseModel, frozen): id, user_id, content, embedding, metadata, memory_type, timestamps
ConversationMessage (BaseModel, frozen): id, user_id, session_id, role, content, created_at
ConversationSession (BaseModel, frozen): id, user_id, title, message_count, timestamps
TaskPattern (BaseModel, frozen): id, user_id, task_name, commands, success metrics
MemorySearchResult (BaseModel, frozen): memory, similarity
MemoryStats (BaseModel, frozen): total_memories, memories_by_type, total_conversations, total_patterns
```

**Tests:** 27/27 PASSING ✅

---

### Task 5.1.2: Migration 012 ✅ COMPLETE

**Status:** DONE  
**Commit:** `e0a550b`  
**Files Created:**
- `migrations/versions/012_memory_system.py` (4.1 KB)
- Fixed `migrations/versions/011_security_tables.py` (standardized format)

**Tables Created:**
```sql
memories (id, user_id, content, embedding, metadata, memory_type, timestamps)
conversation_sessions (id, user_id, title, message_count, timestamps)
conversation_messages (id, session_id, user_id, role, content, created_at)
task_patterns (id, user_id, task_name, commands, success metrics, timestamps)
```

**Indexes:**
- idx_memories_type, idx_memories_user, idx_memories_created
- idx_sessions_user, idx_sessions_updated
- idx_messages_session, idx_messages_created, idx_messages_user
- idx_patterns_user, idx_patterns_name, idx_patterns_confidence

**Verification:**
```bash
uv run alembic current  # Output: 012 (head)
uv run plasma doctor    # Output: ✓ Schema: Initialized
```

---

### Task 5.1.3: Memory Service ✅ COMPLETE

**Status:** DONE  
**Commit:** `d8e8ff7`  
**Files Created:**
- `src/plasmaagent/memory/service.py` (5.8 KB)
- `tests/unit/test_memory_service.py` (19 tests)

**What Was Implemented:**
```python
class MemoryService:
    async def store_memory(content, memory_type, user_id, metadata, embedding) -> Memory
    async def get_memory(memory_id) -> Memory
    async def delete_memory(memory_id) -> None
    async def search_memories(query, limit, memory_type, user_id) -> list[Memory]
    async def get_memories_by_type(memory_type, limit, user_id) -> list[Memory]
    async def get_stats() -> MemoryStats
```

**Key Features:**
- Uses psycopg (NOT asyncpg) for database operations
- Text search with ILIKE (no vector embedding yet - Phase 5.2)
- Proper error handling with MemoryNotFoundError
- Async context manager pattern for cursor
- Row-to-model conversion with embedding parsing

**Tests:** 19/19 PASSING ✅

**Database Pattern (IMPORTANT for next tasks):**
```python
async with self._conn.cursor() as cur:
    await cur.execute("SELECT * FROM table WHERE id = %s", (id,))
    row = await cur.fetchone()
```

---

## 📋 Remaining Tasks (Phase 5.1)

### Task 5.1.4: Conversation Service ⏳ NEXT

**Goal:** Manage conversation sessions and messages

**File to Create:** `src/plasmaagent/memory/conversation_service.py`

**Required Implementation:**
```python
class ConversationService:
    def __init__(self, conn: psycopg.AsyncConnection):
        self._conn = conn
    
    async def create_session(self, user_id: UUID, title: str | None = None) -> ConversationSession
    async def get_session(self, session_id: UUID) -> ConversationSession
    async def list_sessions(self, user_id: UUID, limit: int = 50) -> list[ConversationSession]
    async def delete_session(self, session_id: UUID) -> None
    async def add_message(self, session_id: UUID, user_id: UUID, role: str, content: str) -> ConversationMessage
    async def get_messages(self, session_id: UUID, limit: int = 100) -> list[ConversationMessage]
    async def get_context(self, session_id: UUID, max_messages: int = 10) -> list[ConversationMessage]
```

**Database Queries:**
```python
async def create_session(self, user_id: UUID, title: str | None = None) -> ConversationSession:
    session_id = uuid4()
    now = datetime.now()
    
    await self._conn.execute(
        """
        INSERT INTO conversation_sessions (id, user_id, title, message_count, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (session_id, user_id, title, 0, now, now)
    )
    
    return ConversationSession(
        id=session_id,
        user_id=user_id,
        title=title,
        message_count=0,
        created_at=now,
        updated_at=now
    )

async def add_message(self, session_id: UUID, user_id: UUID, role: str, content: str) -> ConversationMessage:
    message_id = uuid4()
    now = datetime.now()
    
    async with self._conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO conversation_messages (id, session_id, user_id, role, content, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (message_id, session_id, user_id, role, content, now)
        )
        
        await cur.execute(
            """
            UPDATE conversation_sessions
            SET message_count = message_count + 1, updated_at = %s
            WHERE id = %s
            """,
            (now, session_id)
        )
    
    return ConversationMessage(
        id=message_id,
        user_id=user_id,
        session_id=session_id,
        role=role,
        content=content,
        created_at=now
    )
```

**Tests Required:** `tests/unit/test_conversation_service.py`
- Test create_session success
- Test create_session with title
- Test get_session found
- Test get_session not found (raise error)
- Test list_sessions with limit
- Test list_sessions empty
- Test delete_session success
- Test delete_session not found
- Test add_message success
- Test add_message increments message_count
- Test get_messages with limit
- Test get_messages empty
- Test get_context returns last N messages
- Mock database with MockAsyncCursor (see test_memory_service.py)
- Target: 20+ tests

**Commit:** `feat(memory): implement ConversationService for session management`

---

### Task 5.1.5: Task Pattern Service ⏳ PENDING

**Goal:** Learn and retrieve successful task patterns

**File to Create:** `src/plasmaagent/memory/pattern_service.py`

**Required Methods:**
```python
class PatternService:
    def __init__(self, conn: psycopg.AsyncConnection):
        self._conn = conn
    
    async def learn_pattern(self, task_name: str, commands: list[str], duration_ms: float, user_id: UUID | None = None) -> TaskPattern
    async def update_pattern(self, pattern_id: UUID, success: bool, duration_ms: float) -> TaskPattern
    async def get_pattern(self, pattern_id: UUID) -> TaskPattern
    async def find_similar_patterns(self, task_name: str, limit: int = 5) -> list[TaskPattern]
    async def get_top_patterns(self, limit: int = 10) -> list[TaskPattern]
    async def retire_pattern(self, pattern_id: UUID) -> None
```

**Key Logic:**
```python
async def learn_pattern(self, task_name: str, commands: list[str], duration_ms: float, user_id: UUID | None = None) -> TaskPattern:
    pattern_id = uuid4()
    now = datetime.now()
    
    await self._conn.execute(
        """
        INSERT INTO task_patterns (id, user_id, task_name, commands, success_count, avg_duration_ms, confidence, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (pattern_id, user_id, task_name, commands, 1, duration_ms, 0.5, now, now)
    )
    
    return TaskPattern(
        id=pattern_id,
        user_id=user_id,
        task_name=task_name,
        commands=commands,
        success_count=1,
        avg_duration_ms=duration_ms,
        confidence=0.5,
        created_at=now,
        updated_at=now
    )

async def update_pattern(self, pattern_id: UUID, success: bool, duration_ms: float) -> TaskPattern:
    async with self._conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM task_patterns WHERE id = %s",
            (pattern_id,)
        )
        row = await cur.fetchone()
        
        if not row:
            raise PatternNotFoundError(pattern_id)
        
        old_count = row[4]
        old_avg = row[5]
        old_confidence = row[6]
        
        new_count = old_count + 1 if success else old_count
        new_avg = ((old_avg * old_count) + duration_ms) / new_count if new_count > 0 else duration_ms
        new_confidence = min(1.0, old_confidence + (0.1 if success else -0.1))
        
        now = datetime.now()
        await cur.execute(
            """
            UPDATE task_patterns
            SET success_count = %s, avg_duration_ms = %s, confidence = %s, updated_at = %s
            WHERE id = %s
            """,
            (new_count, new_avg, new_confidence, now, pattern_id)
        )
```

**Tests Required:** `tests/unit/test_pattern_service.py`
- Target: 20+ tests

**Commit:** `feat(memory): implement PatternService for learning task patterns`

---

### Task 5.1.6: Memory CLI ⏳ PENDING

**Goal:** Add CLI commands for memory management

**File to Create:** `src/plasmaagent/cli/memory.py`

**Required Commands:**
```bash
plasma memory store --content "User prefers dark mode" --type preference
plasma memory search --query "user preferences" --limit 10
plasma memory list --type conversation --limit 50
plasma memory delete <memory-id>
plasma memory stats
plasma conversation start --title "Debug session"
plasma conversation list
plasma conversation show <session-id>
plasma conversation delete <session-id>
plasma pattern list --limit 10
plasma pattern show <pattern-id>
```

**Register in main.py:**
```python
from plasmaagent.cli.memory import memory_app
app.add_typer(memory_app, name="memory")
```

**CLI Pattern (IMPORTANT):**
```python
import typer
from rich.console import Console
from plasmaagent.core.database import get_database
from plasmaagent.core.async_utils import run_async

memory_app = typer.Typer()
console = Console()

@memory_app.command()
def stats():
    async def _stats():
        async with get_database() as db:
            async with db.connection() as conn:
                from plasmaagent.memory.service import MemoryService
                service = MemoryService(conn)
                stats = await service.get_stats()
                console.print(f"Total memories: {stats.total_memories}")
                console.print(f"Total conversations: {stats.total_conversations}")
                console.print(f"Total patterns: {stats.total_patterns}")
    
    run_async(_stats())
```

**Tests Required:** Manual testing with real database

**Commit:** `feat(cli): add memory management commands`

---

### Task 5.1.7: Integration Tests ⏳ PENDING

**Goal:** End-to-end tests for memory system

**File to Create:** `tests/integration/test_memory_integration.py`

**Required Tests:**
1. Store memory → search → retrieve
2. Create conversation → add messages → get context
3. Learn pattern → update → find similar
4. Memory stats after multiple operations
5. Delete cascade (session → messages)

**Run:**
```bash
uv run pytest tests/integration/test_memory_integration.py -v
```

**Commit:** `test(memory): add integration tests for memory system`

---

## 🛠️ Code Patterns (COPY THESE EXACTLY)

### Pattern 1: Service Class (NO COMMENTS)
```python
import psycopg
from uuid import UUID, uuid4
from datetime import datetime
from plasmaagent.memory.models import Memory, MemoryType

class MemoryService:
    def __init__(self, conn: psycopg.AsyncConnection):
        self._conn = conn
    
    async def get_memory(self, memory_id: UUID) -> Memory:
        async with self._conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM memories WHERE id = %s",
                (memory_id,)
            )
            row = await cur.fetchone()
        
        if not row:
            raise MemoryNotFoundError(memory_id)
        
        return self._row_to_memory(row)
```

### Pattern 2: Unit Test with MockAsyncCursor (NO COMMENTS)
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime

class MockAsyncCursor:
    def __init__(self):
        self.execute = AsyncMock()
        self.fetchone = AsyncMock()
        self.fetchall = AsyncMock()
        self.rowcount = 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

@pytest.fixture
def mock_conn():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    mock_cursor = MockAsyncCursor()
    conn.cursor = MagicMock(return_value=mock_cursor)
    return conn, mock_cursor

@pytest.fixture
def memory_service(mock_conn):
    conn, _ = mock_conn
    return MemoryService(conn)

@pytest.mark.asyncio
async def test_get_memory_success(memory_service, mock_conn):
    conn, mock_cursor = mock_conn
    memory_id = uuid4()
    now = datetime.now()
    mock_cursor.fetchone.return_value = (
        memory_id, None, 'Test memory', None, {}, 'fact', now, now
    )
    
    result = await memory_service.get_memory(memory_id)
    
    assert result.id == memory_id
    assert result.content == 'Test memory'
```

### Pattern 3: CLI Command (NO COMMENTS)
```python
import typer
from rich.console import Console
from plasmaagent.core.database import get_database
from plasmaagent.core.async_utils import run_async

memory_app = typer.Typer()
console = Console()

@memory_app.command()
def stats():
    async def _stats():
        async with get_database() as db:
            async with db.connection() as conn:
                from plasmaagent.memory.service import MemoryService
                service = MemoryService(conn)
                stats = await service.get_stats()
                console.print(f"Total memories: {stats.total_memories}")
    
    run_async(_stats())
```

---

## 📊 Testing Commands

```bash
uv run pytest tests/unit -q
uv run pytest tests/unit/test_memory_models.py -v
uv run pytest tests/unit/test_memory_service.py -v
uv run pytest tests/unit -k "memory" -v
uv run pytest tests/unit --cov=src/plasmaagent/memory --cov-report=html
```

**Current Test Count:** 1134+ tests (1088 base + 46 new memory tests)

---

## 🔄 Git Commands

```bash
git add src/plasmaagent/memory/
git add tests/unit/test_memory*.py
git commit -m "feat(memory): implement [task description]"
git push origin master
```

---

## 🚨 Troubleshooting

### Error: "ModuleNotFoundError: No module named 'asyncpg'"
**Solution:** Project uses `psycopg`, not `asyncpg`. Update imports:
```python
import psycopg
# NOT: import asyncpg
```

### Error: "'coroutine' object does not support the asynchronous context manager protocol"
**Solution:** Use MockAsyncCursor class in tests (see Pattern 2 above)

### Error: "relation 'users' does not exist"
**Solution:** Run migrations:
```bash
uv run alembic upgrade head
```

### Error: "test timeout"
```bash
uv run pytest tests/unit -x --timeout=60
```

---

## 📝 Handoff Notes (When Token Limit Reached)

If you run out of tokens:

1. **Commit current progress:**
```bash
git add .
git commit -m "WIP: [task description] - [percentage]% complete"
```

2. **Update this FASE.md:**
- Mark current task as 🚧 IN PROGRESS
- Add "Handoff Notes" section below
- Describe what's done and what's left

3. **Next developer (local AI) should:**
- Read this FASE.md completely
- Check git log for recent commits
- Run tests to verify baseline
- Continue from NEXT task

---

## 📚 Resources

- **Pydantic V2:** https://docs.pydantic.dev/latest/
- **psycopg (async):** https://www.psycopg.org/psycopg3/docs/advanced/async.html
- **Alembic:** https://alembic.sqlalchemy.org/
- **Typer:** https://typer.tiangolo.com/

---

## 🎯 Phase 5.2 Preview (After 5.1 Complete)

**Phase 5.2: RAG (Retrieval-Augmented Generation)**
- Install pgvector extension
- Vector embeddings with sentence-transformers
- Semantic search with cosine similarity
- Document ingestion (PDF, MD, TXT)
- Context window management
- Source attribution

**Estimated:** ~10 hours | ~8 tasks

---

**END OF FASE.md**

**Last Update:** 2026-06-05 16:45 by Qwen3.7 Max  
**Next Update:** After Task 5.1.4 completion
