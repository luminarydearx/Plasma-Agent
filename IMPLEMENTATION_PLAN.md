# IMPLEMENTATION_PLAN.md — PlasmaAgent

## Status: APPROVED (with modifications)
## Last Updated: 2026-06-02

---

## Gap Analysis: Architecture vs Current State

| Aspect | Architecture Spec | Current State | Gap |
|---|---|---|---|
| Database | PostgreSQL with pgvector, central to system | Not installed | **CRITICAL** |
| Python | 3.13.3 | Installed | ✅ OK |
| uv | Package manager | Installed | ✅ OK |
| CLI framework | Not specified (was click) → **typer** | Not implemented | **MISSING** |
| DB driver | Not specified (was asyncpg) → **psycopg3** | Not implemented | **MISSING** |
| ORM | None (raw SQL) | N/A | ✅ OK |
| Migration | Not specified → **alembic** | Not implemented | **MISSING** |
| Vector support | pgvector | Not enabled | **CRITICAL** |
| State Machine | PTSM (PostgreSQL Transactional) | Not implemented | **MISSING** |
| Task Model | `tasks`, `task_steps`, `execution_logs`, `telemetry` | Not implemented | **MISSING** |
| CLI branding | PlasmaAgent (plasma sphere) | Not implemented | **MISSING** |
| Docker | Forbidden | N/A | ✅ OK |
| Redis | Forbidden | N/A | ✅ OK |
| Frontend | Forbidden | N/A | ✅ OK |

---

## Technical Stack Decisions (Approved)

| Layer | Choice | Rationale |
|---|---|---|
| **Python** | 3.13.3 | Already installed, modern async features |
| **Package Manager** | uv | Fast, already installed |
| **DB Driver** | **psycopg3** | Per user modification request |
| **Migrations** | alembic | Industry standard, works with raw SQL |
| **Vector Extension** | pgvector | Required from initial migration |
| **CLI Framework** | **typer** | Per user modification request |
| **Terminal UI** | rich | Color-rich output, used by typer |
| **Config** | pydantic-settings | Type-safe config from env |
| **Logging** | structlog → telemetry table | Per architecture (all state in DB) |
| **Testing** | pytest + pytest-asyncio | Standard async testing |
| **Linting** | ruff | Fast, comprehensive |
| **Type Checking** | mypy | Strict mode |

---

## Phase 1: Foundational Core (Target: ~15-18 hours)

### Sub-Phase 1.1: Environment Setup
- [ ] Verify Python 3.13.3
- [ ] Verify uv installation
- [ ] Verify PostgreSQL 16+ installation
- [ ] Verify pgvector extension availability
- [ ] Create database `plasmaagent`

### Sub-Phase 1.2: Project Scaffolding
- [ ] Create `pyproject.toml` with dependencies
- [ ] Initialize git repository
- [ ] Create `.gitignore`
- [ ] Create `Makefile` for common commands
- [ ] Set up pre-commit hooks (ruff, mypy)

### Sub-Phase 1.3: Database Connection Layer
- [ ] Create `src/plasmaagent/core/config.py` (pydantic-settings)
- [ ] Create `src/plasmaagent/core/database.py` (psycopg3 async pool)
- [ ] Create connection health check
- [ ] Write unit tests for connection

### Sub-Phase 1.4: Schema & Migrations
- [ ] Install and configure alembic
- [ ] Create initial migration with:
  - `CREATE EXTENSION IF NOT EXISTS vector;` (pgvector)
  - `tasks` table (id, name, description, status, created_at, updated_at)
  - `task_steps` table (id, task_id, step_order, command, status, output, started_at, finished_at)
  - `execution_logs` table (id, task_id, step_id, log_level, message, timestamp)
  - `telemetry` table (id, event_type, payload, timestamp)
- [ ] Verify pgvector extension is enabled
- [ ] Write migration rollback test

### Sub-Phase 1.5: PTSM (PostgreSQL Transactional State Machine)
- [ ] Define state enum: `PENDING`, `RUNNING`, `PAUSED`, `COMPLETED`, `FAILED`, `CANCELLED`
- [ ] Create `src/plasmaagent/core/state_machine.py`
- [ ] Implement atomic state transitions (with `FOR UPDATE SKIP LOCKED`)
- [ ] Implement crash recovery (detect RUNNING tasks on startup)
- [ ] Write state transition tests
- [ ] Write crash recovery test

### Sub-Phase 1.6: CLI Foundation
- [ ] Create `src/plasmaagent/cli/main.py` with typer
- [ ] Implement Rich console with PlasmaAgent theme:
  - Electric Cyan (#00FFFF) — primary actions
  - Plasma Magenta (#FF00FF) — errors/warnings
  - Deep Violet (#8B00FF) — information
- [ ] Create ASCII plasma sphere logo
- [ ] Implement `plasma --help`, `plasma --version`
- [ ] Implement `plasma doctor` (health check)

### Sub-Phase 1.7: Task Lifecycle CLI
- [ ] Create `src/plasmaagent/cli/tasks.py`
- [ ] Implement `plasma task create --name "..." --description "..."`
- [ ] Implement `plasma task run --id <uuid>`
- [ ] Implement `plasma task cancel --id <uuid>`
- [ ] Implement `plasma task retry --id <uuid>`
- [ ] Implement `plasma task list [--status <status>]`
- [ ] Implement `plasma task show --id <uuid>`

### Sub-Phase 1.8: Integration Tests
- [ ] Test full task lifecycle (create → run → complete)
- [ ] Test state transition constraints
- [ ] Test crash recovery scenario
- [ ] Test pgvector operations
- [ ] Achieve >90% coverage on Phase 1 code

---

## Phase 2: Execution Engine (Skeleton — detail after Phase 1)
- Shell step executor (subprocess with PTY)
- Output capture → execution_logs
- Step retry logic
- Task pause/resume
- Real-time CLI streaming

## Phase 3: AI & LLM Integration (Skeleton — detail after Phase 2)
- Context manager (pgvector embeddings)
- Self-healing prompt generator
- LLM provider abstraction (OpenAI/Anthropic/local)
- Step suggestion engine

## Phase 4: Advanced Features (Skeleton — detail after Phase 3)
- Multi-step task planning
- Context learning from past executions
- Error pattern recognition
- Performance optimization

---

## Constraints Checklist

- [x] No Docker
- [x] No Redis
- [x] No Kubernetes
- [x] Python 3.13.3 only
- [x] PostgreSQL only (no other databases)
- [x] All state in PostgreSQL (no filesystem state)
- [x] No frontend until explicitly approved
- [x] CLI command name: `plasma`
- [x] Visual identity: plasma sphere (not Hermes)

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| pgvector not installed | Verify in Task 1.1, install if missing |
| psycopg3 async issues | Use connection pool with proper timeout |
| State machine deadlocks | Use `FOR UPDATE SKIP LOCKED`, add timeout |
| CLI performance | Lazy imports, minimal startup overhead |
| Migration conflicts | Single migration file per sub-phase |
