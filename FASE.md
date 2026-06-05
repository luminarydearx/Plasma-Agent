# 📘 FASE.md - PlasmaAgent Development Roadmap

**Last Updated:** 2026-06-05  
**Current Phase:** Phase 5 - Intelligence Expansion  
**Status:** 🚧 IN PROGRESS

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture & Tech Stack](#architecture--tech-stack)
3. [Project Structure](#project-structure)
4. [Completed Phases](#completed-phases)
5. [Current Phase: Phase 5](#current-phase-phase-5)
6. [Development Guidelines](#development-guidelines)
7. [Testing Strategy](#testing-strategy)
8. [Git Workflow](#git-workflow)
9. [Instructions for Local AI](#instructions-for-local-ai)

---

## 🎯 Project Overview

**PlasmaAgent** adalah AI-powered task automation system yang mengubah natural language menjadi executable tasks dengan PostgreSQL backend, state machine execution, dan self-improvement capabilities.

### Core Features
- Natural language task generation (rule-based NLP)
- PostgreSQL-backed task storage with asyncpg
- State machine execution engine (PENDING → RUNNING → COMPLETED/FAILED)
- Template-based task patterns with self-improvement
- Advanced reasoning (decomposition, dependency graphs, parallel execution)
- Production hardening (scheduling, observability, security, reliability)

### Target Users
- DevOps engineers automating repetitive tasks
- System administrators managing infrastructure
- Developers building CI/CD pipelines
- Anyone who wants to automate shell commands via natural language

---

## 🏗️ Architecture & Tech Stack

### Backend Stack
- **Language:** Python 3.13
- **Database:** PostgreSQL 18 with asyncpg (async driver)
- **ORM:** None (raw SQL with asyncpg for performance)
- **Validation:** Pydantic V2 (frozen models, strict validation)
- **CLI:** Typer with Rich for beautiful output
- **Testing:** pytest + pytest-asyncio
- **Migrations:** Alembic
- **Package Manager:** uv (fast Python package manager)

### Key Libraries
```python
# Core
asyncpg==0.31.0          # Async PostgreSQL driver
pydantic==2.13           # Data validation (V2, frozen models)
typer==0.19.2            # CLI framework
rich==14.2.0             # Terminal formatting

# Testing
pytest==9.0.1            # Test framework
pytest-asyncio==1.3.0    # Async test support
pytest-cov==7.0.0        # Coverage reporting

# Utilities
python-dotenv==1.2.1     # Environment variables
alembic==1.17.1          # Database migrations
httpx==0.28.1            # HTTP client (for webhooks)
bcrypt==5.0.0            # Password hashing
```

### Design Patterns
- **State Machine:** Tasks follow PENDING → RUNNING → COMPLETED/FAILED lifecycle
- **Repository Pattern:** Database access via `Database` class with async context managers
- **Service Layer:** Business logic in service classes (e.g., `TaskService`, `SchedulerService`)
- **Dependency Injection:** Services receive dependencies via constructor
- **Frozen Models:** Pydantic models use `frozen=True` for immutability

---

## 📁 Project Structure

```
PlasmaAgent/
├── src/plasmaagent/
│   ├── __init__.py
│   ├── cli/                    # Typer CLI commands
│   │   ├── main.py            # Main CLI entry point
│   │   ├── tasks.py           # Task management commands
│   │   ├── schedule.py        # Scheduling commands
│   │   ├── monitor.py         # Observability commands
│   │   ├── alerts.py          # Alert management
│   │   ├── metrics.py         # Self-improvement metrics
│   │   ├── security.py        # User management
│   │   └── recovery.py        # Disaster recovery
│   │
│   ├── core/                   # Core business logic
│   │   ├── database.py        # Database connection pool
│   │   ├── task.py            # Task model & service
│   │   ├── executor.py        # Task execution engine
│   │   └── state_machine.py   # Task state transitions
│   │
│   ├── intelligence/           # NLP & reasoning
│   │   ├── nlp_engine.py      # Rule-based NLP patterns
│   │   ├── decomposer.py      # Task decomposition (DAG)
│   │   ├── context.py         # Context management
│   │   ├── error_analyzer.py  # Error pattern analysis
│   │   ├── reasoning.py       # Reasoning service
│   │   └── suggestions.py     # Smart suggestions
│   │
│   ├── scheduling/             # Task scheduling
│   │   ├── cron_parser.py     # Cron expression parser
│   │   ├── service.py         # Scheduler service
│   │   ├── worker.py          # Background scheduler
│   │   ├── dependencies.py    # Task dependencies
│   │   └── persistence.py     # Schedule persistence
│   │
│   ├── observability/          # Monitoring & alerts
│   │   ├── metrics_service.py # Metrics aggregation
│   │   ├── dashboard.py       # Terminal dashboard
│   │   ├── alert_service.py   # Alert system
│   │   └── telegram.py        # Telegram notifications
│   │
│   ├── security/               # Auth & audit
│   │   ├── auth_service.py    # Authentication
│   │   ├── permission_service.py # RBAC
│   │   └── audit_service.py   # Audit logging
│   │
│   ├── reliability/            # Resilience patterns
│   │   ├── circuit_breaker.py # Circuit breaker
│   │   ├── backoff.py         # Retry strategies
│   │   ├── degradation.py     # Graceful degradation
│   │   ├── resilience.py      # Health checks
│   │   └── disaster_recovery.py # Backup/recovery
│   │
│   └── models/                 # Pydantic models
│       ├── task.py            # Task, Step, Log models
│       ├── schedule.py        # Schedule models
│       ├── alert.py           # Alert models
│       └── user.py            # User, Session models
│
├── tests/
│   ├── unit/                   # Unit tests (1088+ tests)
│   │   ├── test_*.py          # One test file per module
│   │   └── conftest.py        # Shared fixtures
│   └── integration/            # Integration tests
│       └── test_*.py
│
├── migrations/versions/        # Alembic migrations
│   ├── 001_initial.py
│   ├── 002_intelligence.py
│   ├── ...
│   └── 012_reliability.py
│
├── pyproject.toml              # Project config (uv)
├── alembic.ini                 # Alembic config
├── .env.example                # Environment template
├── README.md                   # User documentation
├── ROADMAP.md                  # Feature roadmap
└── FASE.md                     # This file (development guide)
```

---

## ✅ Completed Phases

### Phase 1: Foundation ✅
**Status:** COMPLETE  
**Tests:** 11 tests passing  
**Features:**
- Database schema with asyncpg connection pool
- Task model with state machine (PENDING → RUNNING → COMPLETED/FAILED)
- CLI commands: `plasma task create/list/show/run/delete`
- Execution engine with stdout/stderr capture
- Alembic migrations

**Key Files:**
- `src/plasmaagent/core/database.py`
- `src/plasmaagent/core/task.py`
- `src/plasmaagent/core/executor.py`
- `src/plasmaagent/cli/tasks.py`

---

### Phase 2: Execution Engine ✅
**Status:** COMPLETE  
**Tests:** 45 tests passing  
**Features:**
- Multi-step task execution
- Parallel step execution
- Error handling and retry logic
- Execution logs with timestamps
- Task cancellation

**Key Files:**
- `src/plasmaagent/core/executor.py` (enhanced)
- `src/plasmaagent/core/state_machine.py`

---

### Phase 3: Intelligence Layer ✅
**Status:** COMPLETE  
**Tests:** 776+ tests passing  
**Sub-Phases:**

#### 3.1 NLP Engine (MVP)
- Rule-based pattern matching for common tasks
- Confidence scoring (80-95%)
- Template-based task generation
- CLI: `plasma task generate --input "backup database"`

#### 3.2 Self-Improvement Loop
- Template success tracking
- Performance metrics (execution time, success rate)
- Optimization recommendations
- CLI: `plasma metrics show/analyze/optimize`

#### 3.3 Advanced Reasoning
- Task decomposition (break complex tasks into subtasks)
- Dependency graph (DAG) with topological sort
- Conditional step execution
- Parallel step execution
- Context management (variable substitution)
- Error analyzer (pattern recognition)
- Retry strategies (exponential backoff)
- Reasoning service orchestration

#### 3.4 Template Evolution
- Template learner (learn from successful tasks)
- Template versioning (A/B testing)
- Template retirement (low success rate)
- Auto-template generation

#### 3.5 Smart Suggestions
- Next action recommendations
- Similar task lookup
- Anomaly detection
- Performance optimization hints

**Key Files:**
- `src/plasmaagent/intelligence/*.py`
- `tests/unit/test_*.py` (408+ tests)

---

### Phase 4: Production Hardening ✅
**Status:** COMPLETE  
**Tests:** 300+ tests passing  
**Sub-Phases:**

#### 4.1 Scheduling & Automation
- Cron expression parser (5-field format)
- Background scheduler worker (asyncio)
- One-time scheduled tasks
- Recurring patterns (daily, weekly, monthly)
- Task dependencies (on_success, on_failure)
- Scheduler persistence (survive restarts)
- CLI: `plasma schedule create/list/delete/enable/disable`

#### 4.2 Observability & Monitoring
- Metrics aggregation service (execution stats, percentiles)
- Terminal dashboard (Rich Live, real-time updates)
- Alert system (webhook integration, cooldown)
- Telegram bot notifications
- Health monitoring endpoint
- CLI: `plasma monitor dashboard/metrics/alerts`

#### 4.3 Security & Audit
- User authentication (bcrypt password hashing)
- Role-based access control (admin, user, readonly)
- Audit logging (who did what when)
- Session management
- CLI: `plasma user create/list/delete/login`

#### 4.4 Reliability Engineering
- Circuit breaker pattern (3 states: CLOSED/OPEN/HALF_OPEN)
- Exponential backoff with jitter
- Graceful degradation (4 levels: FULL/PARTIAL/MINIMAL/NONE)
- Health checks integration
- Disaster recovery (backup/restore with checksums)
- CLI: `plasma recovery backup/restore/list`

**Key Files:**
- `src/plasmaagent/scheduling/*.py`
- `src/plasmaagent/observability/*.py`
- `src/plasmaagent/security/*.py`
- `src/plasmaagent/reliability/*.py`
- `migrations/versions/009-012_*.py`

---

## 🚧 Current Phase: Phase 5

### Phase 5: Intelligence Expansion
**Status:** 🚧 IN PROGRESS  
**Goal:** Add memory, RAG, multi-agent coordination, and tool use

#### Sub-Phase 5.1: Memory System ⏳ NEXT
**Goal:** Persistent memory with vector embeddings for semantic search

**Tasks:**
1. **5.1.1 Memory Models** - Pydantic models for memories (short-term, long-term)
2. **5.1.2 Vector Store** - pgvector extension for embeddings
3. **5.1.3 Embedding Service** - Generate embeddings (sentence-transformers or API)
4. **5.1.4 Memory Service** - Store/retrieve/query memories
5. **5.1.5 Conversation History** - Track user interactions
6. **5.1.6 Task Patterns Library** - Store successful task patterns
7. **5.1.7 Memory CLI** - CLI commands for memory management
8. **5.1.8 Integration Tests** - End-to-end memory workflows

**Database Changes:**
```sql
-- Migration 013_memory.sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    content TEXT NOT NULL,
    embedding vector(384),  -- 384-dim embeddings
    metadata JSONB DEFAULT '{}',
    memory_type VARCHAR(50) NOT NULL,  -- 'conversation', 'pattern', 'fact'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_memories_type ON memories(memory_type);
CREATE INDEX idx_memories_user ON memories(user_id);

CREATE TABLE conversation_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    session_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'user', 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conversation_session ON conversation_history(session_id);
CREATE INDEX idx_conversation_user_time ON conversation_history(user_id, created_at);
```

**Implementation Plan:**

**Task 5.1.1: Memory Models**
```python
# src/plasmaagent/memory/models.py
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from uuid import UUID
from enum import Enum

class MemoryType(str, Enum):
    CONVERSATION = "conversation"
    PATTERN = "pattern"
    FACT = "fact"

class Memory(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    id: UUID
    user_id: UUID | None = None
    content: str
    embedding: list[float] | None = None  # 384-dim vector
    metadata: dict = Field(default_factory=dict)
    memory_type: MemoryType
    created_at: datetime
    updated_at: datetime

class ConversationMessage(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    id: UUID
    user_id: UUID
    session_id: UUID
    role: str  # 'user' or 'assistant'
    content: str
    created_at: datetime
```

**Task 5.1.2: Vector Store Setup**
```bash
# Install pgvector extension
psql -U postgres -d plasmaagent -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Add to pyproject.toml
[project.dependencies]
pgvector = "^0.3.0"
sentence-transformers = "^3.0.0"  # For local embeddings
```

**Task 5.1.3: Embedding Service**
```python
# src/plasmaagent/memory/embedding_service.py
from sentence_transformers import SentenceTransformer
import numpy as np

class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
    
    def encode(self, text: str) -> list[float]:
        """Generate 384-dim embedding for text."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]
```

**Task 5.1.4: Memory Service**
```python
# src/plasmaagent/memory/service.py
import asyncpg
from uuid import UUID
from .models import Memory, MemoryType
from .embedding_service import EmbeddingService

class MemoryService:
    def __init__(self, db: asyncpg.Connection, embedding_service: EmbeddingService):
        self.db = db
        self.embedding_service = embedding_service
    
    async def store_memory(
        self,
        content: str,
        memory_type: MemoryType,
        user_id: UUID | None = None,
        metadata: dict | None = None
    ) -> Memory:
        """Store a new memory with embedding."""
        embedding = self.embedding_service.encode(content)
        
        row = await self.db.fetchrow("""
            INSERT INTO memories (content, embedding, metadata, memory_type, user_id)
            VALUES ($1, $2::vector, $3::jsonb, $4, $5)
            RETURNING id, content, embedding, metadata, memory_type, user_id, created_at, updated_at
        """, content, embedding, metadata or {}, memory_type.value, user_id)
        
        return Memory(**dict(row))
    
    async def search_similar(
        self,
        query: str,
        limit: int = 10,
        memory_type: MemoryType | None = None
    ) -> list[Memory]:
        """Search for similar memories using cosine similarity."""
        query_embedding = self.embedding_service.encode(query)
        
        query_sql = """
            SELECT id, content, embedding, metadata, memory_type, user_id, created_at, updated_at,
                   1 - (embedding <=> $1::vector) as similarity
            FROM memories
        """
        params = [query_embedding]
        
        if memory_type:
            query_sql += " WHERE memory_type = $2"
            params.append(memory_type.value)
        
        query_sql += " ORDER BY embedding <=> $1::vector LIMIT $" + str(len(params) + 1)
        params.append(limit)
        
        rows = await self.db.fetch(query_sql, *params)
        return [Memory(**dict(row)) for row in rows]
```

**Testing Strategy:**
- Unit tests for each service method (mock database)
- Integration tests with real pgvector
- Performance tests (embedding generation speed, search latency)
- Edge cases (empty content, very long text, unicode)

---

#### Sub-Phase 5.2: RAG (Retrieval-Augmented Generation) ⏳ PENDING
**Goal:** Ingest documents and provide semantic search for context

**Tasks:**
1. Document ingestion (PDF, Markdown, TXT)
2. Chunking strategy (512 tokens with 50 token overlap)
3. Semantic search with pgvector
4. Context window management
5. Source attribution
6. CLI: `plasma rag ingest/search/query`

---

#### Sub-Phase 5.3: Multi-Agent Coordination ⏳ PENDING
**Goal:** Orchestrate multiple specialized agents

**Tasks:**
1. Agent orchestration (planner + executor + reviewer)
2. Task delegation protocol
3. Parallel execution coordination
4. Conflict resolution
5. Agent communication bus
6. CLI: `plasma agent list/delegate/coordinate`

---

#### Sub-Phase 5.4: Tool Use & Skills ⏳ PENDING
**Goal:** Dynamic skill loading and composition

**Tasks:**
1. Skill registry (learned capabilities)
2. Dynamic skill loading (plugin architecture)
3. Skill composition (chain skills together)
4. Skill versioning
5. CLI: `plasma skill list/install/use`

---

## 📝 Development Guidelines

### Code Style
- **Type Hints:** REQUIRED on all functions and methods
- **Pydantic V2:** Use `ConfigDict(frozen=True)` for immutable models
- **Async/Await:** All database operations must be async
- **Error Handling:** Explicit exceptions with custom exception classes
- **Naming:** snake_case for functions/variables, PascalCase for classes

### Example: Service Class
```python
# ✅ GOOD
class TaskService:
    def __init__(self, db: asyncpg.Connection):
        self._db = db
    
    async def create_task(self, name: str, commands: list[str]) -> Task:
        """Create a new task with validation."""
        if not name.strip():
            raise ValueError("Task name cannot be empty")
        
        if not commands:
            raise ValueError("Task must have at least one command")
        
        row = await self._db.fetchrow("""
            INSERT INTO tasks (name, commands, status)
            VALUES ($1, $2, $3)
            RETURNING id, name, commands, status, created_at
        """, name, commands, TaskStatus.PENDING.value)
        
        return Task(**dict(row))

# ❌ BAD
class TaskService:
    def __init__(self, db):  # Missing type hint
        self.db = db
    
    def create_task(self, name, commands):  # Not async, no type hints
        # No validation
        result = self.db.execute("INSERT INTO tasks ...")  # Not async
        return result
```

### Database Access Pattern
```python
# ✅ CORRECT: Use async context manager
async with get_database() as db:
    async with db.connection() as conn:
        async with conn.transaction():
            await conn.execute("UPDATE tasks SET status=$1 WHERE id=$2", status, task_id)

# ❌ WRONG: Direct connection without context manager
conn = await asyncpg.connect(DATABASE_URL)
await conn.execute("UPDATE tasks ...")
await conn.close()
```

### Error Handling
```python
# ✅ GOOD: Custom exceptions with context
class TaskNotFoundError(Exception):
    def __init__(self, task_id: UUID):
        self.task_id = task_id
        super().__init__(f"Task {task_id} not found")

async def get_task(task_id: UUID) -> Task:
    row = await db.fetchrow("SELECT * FROM tasks WHERE id=$1", task_id)
    if not row:
        raise TaskNotFoundError(task_id)
    return Task(**dict(row))

# ❌ BAD: Generic exceptions
async def get_task(task_id: UUID) -> Task:
    row = await db.fetchrow("SELECT * FROM tasks WHERE id=$1", task_id)
    if not row:
        raise Exception("Not found")  # Too generic
    return Task(**dict(row))
```

---

## 🧪 Testing Strategy

### Test Structure
```python
# tests/unit/test_task_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from plasmaagent.core.task import TaskService, Task

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.fetchrow = AsyncMock()
    db.fetch = AsyncMock()
    db.execute = AsyncMock()
    return db

@pytest.fixture
def task_service(mock_db):
    return TaskService(mock_db)

@pytest.mark.asyncio
async def test_create_task_success(task_service, mock_db):
    # Arrange
    mock_db.fetchrow.return_value = {
        'id': '123',
        'name': 'Test Task',
        'commands': ['echo hello'],
        'status': 'pending',
        'created_at': datetime.now()
    }
    
    # Act
    task = await task_service.create_task('Test Task', ['echo hello'])
    
    # Assert
    assert task.name == 'Test Task'
    assert task.commands == ['echo hello']
    assert task.status == TaskStatus.PENDING
    mock_db.fetchrow.assert_called_once()

@pytest.mark.asyncio
async def test_create_task_empty_name(task_service):
    # Act & Assert
    with pytest.raises(ValueError, match="cannot be empty"):
        await task_service.create_task('', ['echo hello'])
```

### Running Tests
```bash
# Run all unit tests
uv run pytest tests/unit -v

# Run with coverage
uv run pytest tests/unit --cov=src/plasmaagent --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_task_service.py -v

# Run tests matching pattern
uv run pytest tests/unit -k "test_create_task" -v
```

### Test Coverage Goals
- **Unit Tests:** 90%+ coverage for all service classes
- **Integration Tests:** Cover all CLI commands end-to-end
- **Edge Cases:** Empty input, invalid UUID, SQL injection, unicode, long strings

---

## 🔄 Git Workflow

### Commit Message Format (Conventional Commits)
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `test`: Add or update tests
- `docs`: Documentation changes
- `refactor`: Code refactoring (no feature/fix)
- `chore`: Maintenance tasks
- `perf`: Performance improvements

**Scopes:**
- `core`, `cli`, `intelligence`, `scheduling`, `observability`, `security`, `reliability`, `memory`

**Examples:**
```bash
# Good commits
git commit -m "feat(memory): implement MemoryService with pgvector search"
git commit -m "fix(cli): handle invalid UUID format gracefully"
git commit -m "test(memory): add 25 unit tests for MemoryService"
git commit -m "docs(fase): update FASE.md with Phase 5 details"

# Bad commits
git commit -m "update code"  # Too vague
git commit -m "fix bug"      # No scope, no details
git commit -m "WIP"          # Never commit WIP
```

### Push Strategy
- **Push after completing a sub-phase** (e.g., after 5.1 complete)
- **Push after major bug fixes**
- **Never push broken code** (all tests must pass)
- **Never push secrets** (.env, API keys, passwords)

### Branch Strategy
- **master:** Stable, production-ready code
- **feature/*:** New features (optional, for large features)
- **hotfix/*:** Critical bug fixes (optional)

---

## 🤖 Instructions for Local AI (Qwen2.5-Coder 7B)

### Your Role
You are a **Senior Python Engineer** continuing development of PlasmaAgent. You have access to:
- Full codebase in `C:\Users\Dearly Febriano\Documents\PlasmaAgent`
- PostgreSQL database with migrations
- 1088+ unit tests (all passing)
- This FASE.md document as your guide

### Before Coding ANYTHING
1. **Read FASE.md** to understand current phase and next tasks
2. **Check git status** to see uncommitted changes
3. **Run existing tests** to ensure baseline is working: `uv run pytest tests/unit -q`
4. **Read related files** before modifying (use OmniForge MCP)

### Task Execution Protocol
For each task in the current sub-phase:

1. **Understand Requirements**
   - Read task description in FASE.md
   - Check related models/services in codebase
   - Identify dependencies

2. **Implement Feature**
   - Create new files or modify existing ones
   - Follow code style guidelines (type hints, async, frozen models)
   - Add inline comments for complex logic only

3. **Write Tests**
   - Unit tests for all new functions/methods
   - Test happy path + edge cases + error cases
   - Mock database with AsyncMock
   - Run tests: `uv run pytest tests/unit/test_new_feature.py -v`

4. **Verify Integration**
   - Run all unit tests: `uv run pytest tests/unit -q`
   - Fix any broken tests
   - Ensure 100% pass rate

5. **Update FASE.md**
   - Mark task as ✅ COMPLETE
   - Update test count
   - Add any important notes

6. **Commit Changes**
   - Use conventional commit format
   - Example: `feat(memory): implement Task 5.1.1 - Memory models`

### Common Pitfalls to Avoid
- ❌ Don't use `asyncio.run()` in CLI commands (use `run_async()` helper)
- ❌ Don't forget `await` for async functions
- ❌ Don't use mutable default arguments (use `Field(default_factory=dict)`)
- ❌ Don't hardcode database URLs (use environment variables)
- ❌ Don't skip tests (write them for every function)
- ❌ Don't push without running tests first

### When You're Stuck
1. **Check existing code** for similar patterns
2. **Read Pydantic V2 docs** (use Context7 MCP if available)
3. **Check test files** for usage examples
4. **Ask for clarification** in comments (mark with `# TODO: clarify`)

### Handoff Protocol (When Token Limit Reached)
If you're about to run out of tokens:

1. **Commit current progress** (even if incomplete)
2. **Update FASE.md** with:
   - Current task status
   - What's done
   - What's left
   - Any blockers
3. **Write handoff comment** in code:
   ```python
   # TODO: [HANDOFF] Continue implementing search_similar()
   # - Done: store_memory() method
   # - Next: Implement cosine similarity search
   # - Blocker: Need to test with real pgvector
   ```

---

## 📊 Progress Tracking

### Current Status (2026-06-05)
- **Phase 1-4:** ✅ COMPLETE (1088+ tests passing)
- **Phase 5.1:** 🚧 NOT STARTED
- **Phase 5.2-5.4:** ⏳ PENDING

### Next Actions
1. Start Task 5.1.1 (Memory Models)
2. Create `src/plasmaagent/memory/` directory
3. Implement Pydantic models (Memory, ConversationMessage)
4. Write 10+ unit tests
5. Commit: `feat(memory): implement Task 5.1.1 - Memory models`

### Estimated Timeline
- **Phase 5.1 (Memory):** ~12 hours (8 tasks)
- **Phase 5.2 (RAG):** ~10 hours (6 tasks)
- **Phase 5.3 (Multi-Agent):** ~15 hours (8 tasks)
- **Phase 5.4 (Tool Use):** ~10 hours (6 tasks)
- **Total Phase 5:** ~47 hours

---

## 🔗 Resources

### Documentation
- [Pydantic V2 Docs](https://docs.pydantic.dev/latest/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/current/)
- [Typer CLI](https://typer.tiangolo.com/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)

### Project Links
- **GitHub:** https://github.com/luminarydearx/Plasma-Agent
- **Issues:** https://github.com/luminarydearx/Plasma-Agent/issues

---

## 📝 Changelog

### 2026-06-05
- ✅ Phase 4 (Production Hardening) COMPLETE
- ✅ Pushed 6 commits to GitHub (0214599..8b1cd0a)
- ✅ Created FASE.md with comprehensive development guide
- 🚧 Starting Phase 5 (Intelligence Expansion)

---

**END OF FASE.md**
