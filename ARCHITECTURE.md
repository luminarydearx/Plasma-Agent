# PlasmaAgent - Architecture Document

## 🎯 Project Vision

**PlasmaAgent** is a database-centric agentic execution framework that combines AI-powered task automation with robust production-grade infrastructure. It serves as an intelligent system administrator that can:

- Execute complex multi-step workflows autonomously
- Learn from execution patterns and optimize over time
- Provide natural language interfaces for system operations
- Maintain security, reliability, and observability at enterprise scale

---

## 📊 Current State (As of 2026-06-06)

### Completed Phases

| Phase | Name | Status | Tests | Key Features |
|-------|------|--------|-------|--------------|
| **1** | Foundation | ✅ COMPLETE | 150+ | PTSM State Machine, Database Layer, Config Management |
| **2** | Execution Engine | ✅ COMPLETE | 200+ | Shell Executor, Retry Logic, Parallel Execution |
| **3** | Intelligence Layer | ✅ COMPLETE | 300+ | NL Pattern Matching, Template System, Self-Improvement |
| **4** | Production Hardening | ✅ COMPLETE | 400+ | Scheduling, Observability, Security, Reliability |
| **5.1** | Memory System | ✅ COMPLETE | 90 | Long-term Memory, Conversation History, Pattern Learning |
| **5.2-5.4** | RAG, Multi-Agent, Tool Use | ✅ COMPLETE | 300+ | Vector Search, Agent Orchestration, Tool Registry |

### In Progress

| Phase | Name | Status | Progress |
|-------|------|--------|----------|
| **5.5** | Security Enhancement | 🟡 STARTED | 0% (Planning done) |

### Test Coverage

- **Total Tests:** 1516+ unit tests, 332+ integration tests
- **Coverage:** ~85% (target: 95%)
- **All Tests Passing:** ✅

---

## 🏗️ Technology Stack

### Core Runtime

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.13 | Primary language |
| PostgreSQL | 18 | Primary database |
| psycopg | 3.2+ | Async DB driver (NOT asyncpg) |
| psycopg-pool | 3.2+ | Connection pooling |
| Pydantic | V2 | Data validation (frozen=True) |
| Typer | 0.12+ | CLI framework |
| Rich | 13+ | Terminal UI |
| Structlog | 24+ | Structured logging |
| httpx | 0.28+ | Async HTTP client |

### AI/ML Components

| Component | Version | Purpose |
|-----------|---------|---------|
| Ollama | Latest | Local LLM inference |
| Qwen2.5-Coder-7B | Q4_K_M | Primary agent model |
| sentence-transformers | TBD | Embedding generation |
| pgvector | TBD | Vector similarity search |

### Development Tools

| Tool | Purpose |
|------|---------|
| uv | Package manager (replaces pip/poetry) |
| Alembic | Database migrations |
| pytest | Testing framework |
| ruff | Linting & formatting |
| mypy | Static type checking |

---

## 🏛️ Architecture Patterns

### 1. Clean Architecture

```
src/plasmaagent/
├── core/              # Framework-agnostic business logic
│   ├── database.py    # DB connection & transactions
│   ├── config.py      # Configuration management
│   └── exceptions.py  # Custom exception hierarchy
├── models/            # Pydantic V2 domain models
│   ├── task.py        # Task, TaskPayload, TaskStatus
│   ├── template.py    # Template, TemplateVersion
│   ├── schedule.py    # Schedule, CronExpression
│   └── memory.py      # Memory, ConversationSession
├── services/          # Business logic services
│   ├── task_service.py
│   ├── template_service.py
│   ├── schedule_service.py
│   └── memory_service.py
├── executor/          # Command execution engines
│   ├── shell.py       # PowerShell/Bash executor
│   ├── retry.py       # Retry logic with backoff
│   └── parallel.py    # Parallel task execution
├── agent/             # AI Agent components
│   ├── orchestrator.py # Agent orchestration
│   ├── tools.py       # Tool registry (13 tools)
│   ├── repl.py        # Interactive chat interface
│   └── ollama_client.py # Ollama API client
└── cli/               # CLI commands (Typer)
    ├── main.py        # Root app
    ├── task.py        # Task commands
    ├── schedule.py    # Schedule commands
    ├── files.py       # File operations
    └── memory.py      # Memory commands
```

### 2. Dependency Injection

All services receive dependencies via constructor:

```python
class TaskService:
    def __init__(self, db: Database):
        self._db = db
    
    async def create_task(self, payload: TaskPayload) -> Task:
        async with self._db.transaction() as conn:
            # Implementation
            pass
```

### 3. Repository Pattern

Database access encapsulated in service methods:

```python
async def get_by_id(self, task_id: UUID) -> Task | None:
    async with self._db.connection() as conn:
        result = await conn.execute(
            "SELECT * FROM tasks WHERE id = %s", (task_id,)
        )
        row = await result.fetchone()
        return Task(**row) if row else None
```

### 4. PTSM (Plasma Task State Machine)

Tasks follow strict state transitions:

```
PENDING → RUNNING → COMPLETED
                ↓
              FAILED
PENDING → CANCELLED
```

State transitions validated at database level via CHECK constraints.

---

## 🗄️ Database Schema

### Core Tables (15+ tables)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `tasks` | Task execution records | id, name, status, payload, created_at |
| `task_executions` | Execution history | id, task_id, started_at, completed_at, exit_code |
| `templates` | Reusable task templates | id, name, pattern, commands, confidence |
| `template_metrics` | Template performance | id, template_id, success_rate, avg_duration |
| `schedules` | Scheduled tasks | id, task_id, cron_expr, next_run, enabled |
| `schedule_runs` | Schedule execution history | id, schedule_id, triggered_at, status |
| `memories` | Long-term memory storage | id, content, embedding, metadata, created_at |
| `conversation_sessions` | Chat sessions | id, title, created_at |
| `conversation_messages` | Chat messages | id, session_id, role, content, timestamp |
| `task_patterns` | Learned task patterns | id, task_name, commands, success_count |
| `alert_rules` | Monitoring alerts | id, name, metric, threshold, webhook |
| `alert_history` | Alert trigger history | id, rule_id, triggered_at, resolved_at |
| `audit_logs` | Security audit trail | id, timestamp, user, action, details |
| `permissions` | Tool permission rules | id, tool_name, path_pattern, level |

### Indexes (50+)

Optimized for common query patterns:

```sql
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);
CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_schedules_next_run ON schedules(next_run) WHERE enabled = true;
```

### Migrations

- **Current:** 012_add_memory_system
- **Next:** 013_add_audit_logs
- **Tool:** Alembic with async support

---

## 🎨 Coding Standards

### MANDATORY Rules

1. **Type Hints Everywhere**
   ```python
   async def create_task(self, payload: TaskPayload) -> Task:
       ...
   ```

2. **Pydantic V2 Models (Frozen)**
   ```python
   class Task(BaseModel):
       id: UUID
       name: str
       status: TaskStatus
       
       model_config = ConfigDict(frozen=True)
   ```

3. **Timezone-Aware Datetimes (UTC)**
   ```python
   from datetime import datetime, timezone
   
   created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
   ```

4. **Parameterized SQL Queries**
   ```python
   await conn.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
   # NEVER: f"SELECT * FROM tasks WHERE id = {task_id}"
   ```

5. **Specific Exception Handling**
   ```python
   try:
       result = await service.create(payload)
   except ValidationError as e:
       console.print(f"[red]Validation error:[/red] {e}")
   except DatabaseError as e:
       console.print(f"[red]Database error:[/red] {e}")
   # NEVER: except Exception:
   ```

6. **Input Validation**
   ```python
   class TaskPayload(BaseModel):
       name: str = Field(min_length=1, max_length=255)
       timeout: int = Field(ge=1, le=3600)
   ```

### FORBIDDEN Patterns

❌ **Comments in code** (minimal only for complex logic)
❌ **String interpolation for SQL** (use %s placeholders)
❌ **Broad exception handling** (`except:` or `except Exception:`)
❌ **Timezone-naive datetimes** (`datetime.now()` without tz)
❌ **eval() or exec()** (security risk)
❌ **asyncpg** (use psycopg)
❌ **Global mutable state** (use dependency injection)

### Code Style

- **Line length:** 100 characters
- **Indentation:** 4 spaces
- **Naming:** snake_case for functions/variables, PascalCase for classes
- **Imports:** Absolute imports only
- **Async:** Prefer async/await over threading

---

## 🧪 Testing Strategy

### Test Pyramid

```
    /\
   /  \      E2E Tests (5%)
  /____\     Integration Tests (25%)
 /______\    Unit Tests (70%)
/________\
```

### Unit Tests

- **Location:** `tests/unit/`
- **Count:** 1516+ tests
- **Focus:** Service methods, models, utilities
- **Mocking:** Database connections, external APIs
- **Framework:** pytest + pytest-asyncio

```python
async def test_create_task_success():
    db = MockDatabase()
    service = TaskService(db)
    
    task = await service.create_task(TaskPayload(name="Test", commands=["echo hello"]))
    
    assert task.name == "Test"
    assert task.status == TaskStatus.PENDING
```

### Integration Tests

- **Location:** `tests/integration/`
- **Count:** 332+ tests
- **Focus:** Database operations, CLI commands, API endpoints
- **Database:** Real PostgreSQL instance (test database)
- **Cleanup:** Fixtures handle setup/teardown

```python
async def test_task_lifecycle(db: Database):
    service = TaskService(db)
    
    # Create
    task = await service.create_task(TaskPayload(name="Test", commands=["echo hello"]))
    
    # Execute
    await service.execute_task(task.id)
    
    # Verify
    updated = await service.get_by_id(task.id)
    assert updated.status == TaskStatus.COMPLETED
```

### Test Commands

```bash
# Run all unit tests
uv run pytest tests/unit -v

# Run integration tests (requires database)
uv run pytest tests/integration -v

# Run with coverage
uv run pytest tests/ --cov=src/plasmaagent --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_task_service.py -v

# Run tests matching pattern
uv run pytest tests/ -k "memory" -v
```

---

## 🤖 AI Agent Architecture

### Agent Components

```
┌─────────────────────────────────────┐
│         Interactive REPL            │
│  (repl.py - prompt-toolkit + Rich)  │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      Agent Orchestrator             │
│  (orchestrator.py - coordination)   │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│        Ollama Client                │
│  (ollama_client.py - HTTP API)      │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         Tool Registry               │
│  (tools.py - 13 tools available)    │
└─────────────────────────────────────┘
```

### Available Tools (13)

| Tool | Category | Purpose |
|------|----------|---------|
| `create_file` | File Ops | Create file with content |
| `read_file` | File Ops | Read file content |
| `write_file` | File Ops | Write/append to file |
| `list_directory` | File Ops | List files & folders |
| `delete_file` | File Ops | Delete file/directory |
| `file_info` | File Ops | Get file metadata |
| `execute_shell` | System | Run PowerShell/Bash commands |
| `open_app` | System | Open application or URL |
| `cron_schedule` | Automation | Schedule recurring tasks |
| `store_memory` | Memory | Save to long-term memory |
| `search_memory` | Memory | Search memory |
| `system_info` | Info | Get OS, user, cwd info |
| `current_time` | Info | Get current datetime |

### Tool Calling Protocol

Agent uses JSON format for tool calls:

```json
{"name": "create_file", "arguments": {"path": "/path/to/file.txt", "content": "Hello"}}
```

Orchestrator parses tool calls from model response and executes them.

### Chat Commands

| Command | Purpose |
|---------|---------|
| `exit` / `quit` | Exit chat mode |
| `/reset` | Clear conversation history |
| `/tools` | List available tools |
| `/model` | List available models |
| `/model <name>` | Switch to different model |
| `/clear` | Clear screen & reset chat |

---

## 🚀 Future Roadmap

### Phase 5.5: Security Enhancement (NEXT)

#### Task 5.5.1: Permission System
- **PermissionManager:** Granular control per tool/path
- **AuditLogger:** Log all tool executions
- **Migration 013:** audit_logs, permissions tables
- **CLI Commands:** `plasma permission list/grant/revoke`
- **Acceptance:** 20+ tests, interactive prompts

#### Task 5.5.2: Input Sanitization
- SQL injection detection
- Shell injection prevention
- Path traversal protection
- XSS prevention

#### Task 5.5.3: Access Control (RBAC)
- Roles: admin, user, readonly
- Permission matrices
- User authentication (optional)

#### Task 5.5.4: Encryption
- Encrypt audit logs at rest
- Encrypt memory storage
- Encrypt config files

#### Task 5.5.5: Security Audit & Testing
- Penetration testing
- Security review checklist
- Documentation

### Phase 6: Advanced Intelligence

#### Task 6.1: Advanced RAG
- **Goal:** Semantic search with pgvector
- **Features:**
  - Document ingestion (PDF, Markdown, code)
  - Chunking & embedding generation
  - Hybrid search (keyword + semantic)
  - Source attribution
- **Acceptance:** 30+ tests, search accuracy >90%

#### Task 6.2: Multi-Agent Coordination
- **Goal:** Specialized agents working together
- **Features:**
  - Planner agent (task decomposition)
  - Executor agents (parallel execution)
  - Reviewer agent (quality control)
  - Agent communication protocol
- **Acceptance:** 25+ tests, end-to-end workflow

#### Task 6.3: Skill System
- **Goal:** Reusable skill packages
- **Features:**
  - Skill registry (install/uninstall)
  - Skill composition (chain skills)
  - Skill versioning
  - Skill marketplace (future)
- **Acceptance:** 20+ tests, 5+ built-in skills

### Phase 7: Production Deployment

#### Task 7.1: Docker & Kubernetes
- **Goal:** Containerized deployment
- **Features:**
  - Multi-stage Dockerfile
  - Kubernetes manifests
  - Helm chart
  - Auto-scaling configuration
- **Acceptance:** Deploy to K8s cluster

#### Task 7.2: CI/CD Pipeline
- **Goal:** Automated testing & deployment
- **Features:**
  - GitHub Actions workflow
  - Automated testing (unit, integration, e2e)
  - Code quality checks (ruff, mypy)
  - Automated deployment to staging/production
- **Acceptance:** PR → auto-deploy to staging

#### Task 7.3: Monitoring & Observability
- **Goal:** Production monitoring
- **Features:**
  - Prometheus metrics export
  - Grafana dashboards
  - Distributed tracing (OpenTelemetry)
  - Centralized logging (ELK stack)
- **Acceptance:** Dashboard with key metrics

### Phase 8: Advanced Features

#### Task 8.1: Web UI Dashboard
- **Goal:** Browser-based management interface
- **Tech Stack:** FastAPI + Svelte/React
- **Features:**
  - Task management UI
  - Real-time execution logs
  - Metrics visualization
  - Configuration editor
- **Acceptance:** Full CRUD operations via web

#### Task 8.2: API Gateway
- **Goal:** RESTful API for external integrations
- **Features:**
  - OpenAPI 3.0 spec
  - JWT authentication
  - Rate limiting
  - API versioning
- **Acceptance:** Swagger UI, 20+ endpoints

#### Task 8.3: Plugin System
- **Goal:** Extensible architecture
- **Features:**
  - Plugin discovery & loading
  - Plugin lifecycle management
  - Plugin sandboxing
  - Plugin marketplace (future)
- **Acceptance:** 3+ example plugins

### Phase 9: Enterprise Features

#### Task 9.1: Multi-Tenancy
- **Goal:** Support multiple organizations
- **Features:**
  - Tenant isolation (row-level security)
  - Per-tenant configuration
  - Tenant-specific branding
  - Usage metering & billing
- **Acceptance:** 2+ tenants with isolated data

#### Task 9.2: Compliance & Governance
- **Goal:** Enterprise compliance
- **Features:**
  - GDPR compliance (data retention, right to be forgotten)
  - SOC 2 controls
  - Audit trail (immutable logs)
  - Compliance reporting
- **Acceptance:** Compliance checklist

#### Task 9.3: High Availability
- **Goal:** 99.9% uptime
- **Features:**
  - Database replication (primary-replica)
  - Application clustering
  - Health checks & auto-recovery
  - Disaster recovery procedures
- **Acceptance:** Failover test, <30s recovery

### Phase 10: Final Polish

#### Task 10.1: Documentation
- **Goal:** Comprehensive documentation
- **Deliverables:**
  - User guide (Getting Started, Tutorials)
  - API reference (auto-generated)
  - Architecture guide
  - Deployment guide
  - Troubleshooting guide
- **Acceptance:** Docs site with search

#### Task 10.2: Performance Optimization
- **Goal:** Sub-100ms response times
- **Features:**
  - Database query optimization
  - Connection pooling tuning
  - Caching layer (Redis)
  - Load testing & benchmarking
- **Acceptance:** <100ms p95 latency

#### Task 10.3: Security Hardening
- **Goal:** Production security
- **Features:**
  - Security audit (third-party)
  - Vulnerability scanning
  - Penetration testing
  - Security documentation
- **Acceptance:** No critical vulnerabilities

---

## 🛠️ Development Workflow

### Starting a New Session

1. **Read ARCHITECTURE.md** (this file)
2. **Read FASE.md** (current phase details)
3. **Check git status:** `git status`
4. **Run tests:** `uv run pytest tests/unit -q`
5. **Start development**

### Implementing a New Feature

1. **Understand requirements** (from FASE.md or user)
2. **Design solution** (consider architecture patterns)
3. **Write tests first** (TDD approach)
4. **Implement feature** (follow coding standards)
5. **Run tests:** `uv run pytest tests/ -v`
6. **Commit:** `git commit -m "feat(scope): description"`
7. **Update FASE.md** (mark task complete)

### Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `test`: Test changes
- `docs`: Documentation
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `security`: Security enhancement

**Example:**
```
feat(memory): add conversation history tracking

- Implement ConversationService with session management
- Add migration 012 for conversation tables
- Write 22 unit tests for conversation operations

Closes #123
```

---

## 📋 Handoff Protocol

### For Cloud AI (Qwen-Max, Claude, GPT-4)

1. Read `ARCHITECTURE.md` (this file)
2. Read `FASE.md` for current phase details
3. Use MCP tools for file operations and testing
4. Follow NO COMMENTS policy
5. Commit after each task completion
6. Update FASE.md with progress

### For Local AI (Qwen2.5-Coder-7B, Qwen3-4B)

**Prompt Template:**

```
Baca file ARCHITECTURE.md dan FASE.md di root project.

Saya sudah selesai [COMPLETED_TASKS].

Sekarang lanjutkan [NEXT_TASK].

Ikuti instruksi dengan ketat:
1. [STEP_1]
2. [STEP_2]
3. [STEP_3]
4. Write unit tests (target: X tests)
5. Run tests: uv run pytest tests/unit -k [pattern] -v
6. Commit jika semua tests pass

NO COMMENTS di code. Gunakan psycopg (bukan asyncpg).
Pydantic V2 dengan frozen=True.
```

---

## 📞 Support & Resources

### Documentation

- **Pydantic V2:** https://docs.pydantic.dev/latest/
- **psycopg 3:** https://www.psycopg.org/psycopg3/docs/
- **Typer:** https://typer.tiangolo.com/
- **Rich:** https://rich.readthedocs.io/
- **pytest:** https://docs.pytest.org/

### Project Files

- `ARCHITECTURE.md` - This file (architecture overview)
- `FASE.md` - Current phase details & next tasks
- `SYSTEM_PROMPT.md` - Agent system prompt
- `ROADMAP.md` - High-level roadmap
- `README.md` - User-facing documentation

---

## 📅 Document History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-06-06 | 1.0 | Cloud AI (Qwen-Max) | Initial comprehensive architecture document |

---

**Last Updated:** 2026-06-06  
**Next Update:** After Phase 5.5 completion  
**Maintained By:** Dearly Febriano & AI Assistants
