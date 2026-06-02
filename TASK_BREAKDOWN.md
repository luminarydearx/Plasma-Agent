# TASK_BREAKDOWN.md — PlasmaAgent

## Phase 1: Foundational Core

### Sub-Phase 1.1: Environment Setup (~1 hour)

#### Task 1.1.1: Verify Python 3.13.3
- **Command:** `python --version`
- **Expected:** Python 3.13.3
- **Status:** [ ]
- **Result:** 

#### Task 1.1.2: Verify uv
- **Command:** `uv --version`
- **Expected:** uv 0.x.x
- **Status:** [ ]
- **Result:** 

#### Task 1.1.3: Verify PostgreSQL
- **Command:** `psql --version`
- **Expected:** PostgreSQL 16+
- **Status:** [ ]
- **Result:** 

#### Task 1.1.4: Verify pgvector Extension
- **Command:** `psql -U postgres -c "SELECT * FROM pg_available_extensions WHERE name = 'vector';"`
- **Expected:** Extension available
- **Status:** [ ]
- **Result:** 

#### Task 1.1.5: Create Database
- **Command:** `psql -U postgres -c "CREATE DATABASE plasmaagent;"`
- **Expected:** Database created
- **Status:** [ ]
- **Result:** 

---

### Sub-Phase 1.2: Project Scaffolding (~1 hour)

#### Task 1.2.1: Create pyproject.toml
- **File:** `pyproject.toml`
- **Contents:**
  ```toml
  [project]
  name = "plasmaagent"
  version = "0.1.0"
  requires-python = ">=3.13"
  dependencies = [
      "psycopg[binary]>=3.2.0",
      "pydantic-settings>=2.0.0",
      "typer>=0.12.0",
      "rich>=13.0.0",
      "structlog>=24.0.0",
  ]
  
  [project.scripts]
  plasma = "plasmaagent.cli.main:app"
  
  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"
  
  [tool.ruff]
  line-length = 100
  target-version = "py313"
  
  [tool.ruff.lint]
  select = ["E", "F", "I", "N", "W", "UP"]
  
  [tool.mypy]
  python_version = "3.13"
  strict = true
  
  [tool.pytest.ini_options]
  asyncio_mode = "auto"
  ```
- **Status:** [ ]

#### Task 1.2.2: Initialize Git Repository
- **Command:** `git init`
- **Status:** [ ]

#### Task 1.2.3: Create .gitignore
- **File:** `.gitignore`
- **Status:** [ ]

#### Task 1.2.4: Create Makefile
- **File:** `Makefile`
- **Targets:** `install`, `lint`, `test`, `migrate`, `run`
- **Status:** [ ]

#### Task 1.2.5: Create Directory Structure
- **Directories:**
  - `src/plasmaagent/core/`
  - `src/plasmaagent/cli/`
  - `src/plasmaagent/models/`
  - `src/plasmaagent/services/`
  - `src/plasmaagent/utils/`
  - `tests/unit/`
  - `tests/integration/`
  - `migrations/versions/`
- **Status:** [ ]

---

### Sub-Phase 1.3: Database Connection Layer (~2 hours)

#### Task 1.3.1: Create Config Module
- **File:** `src/plasmaagent/core/config.py`
- **Contents:**
  - Use `pydantic-settings` to load from environment
  - Fields: `DATABASE_URL`, `LOG_LEVEL`, `APP_NAME`
  - Default: `postgresql+psycopg://postgres:090208@localhost:5432/plasmaagent`
- **Status:** [ ]

#### Task 1.3.2: Create Database Module
- **File:** `src/plasmaagent/core/database.py`
- **Contents:**
  - Create async connection pool using `psycopg.AsyncConnectionPool`
  - Provide `get_connection()` async context manager
  - Implement health check function
- **Status:** [ ]

#### Task 1.3.3: Write Connection Tests
- **File:** `tests/unit/test_database.py`
- **Tests:**
  - Test connection pool creation
  - Test health check
  - Test connection context manager
- **Status:** [ ]

---

### Sub-Phase 1.4: Schema & Migrations (~3 hours)

#### Task 1.4.1: Install and Configure Alembic
- **Command:** `uv add --dev alembic`
- **Command:** `alembic init migrations`
- **File:** `alembic.ini` (configure for psycopg3)
- **Status:** [ ]

#### Task 1.4.2: Create Initial Migration
- **File:** `migrations/versions/001_initial_schema.py`
- **SQL:**
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  
  CREATE TABLE tasks (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      name VARCHAR(255) NOT NULL,
      description TEXT,
      status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  
  CREATE TABLE task_steps (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
      step_order INTEGER NOT NULL,
      command TEXT NOT NULL,
      status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
      output TEXT,
      started_at TIMESTAMPTZ,
      finished_at TIMESTAMPTZ,
      UNIQUE(task_id, step_order)
  );
  
  CREATE TABLE execution_logs (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
      step_id UUID REFERENCES task_steps(id) ON DELETE CASCADE,
      log_level VARCHAR(20) NOT NULL,
      message TEXT NOT NULL,
      timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  
  CREATE TABLE telemetry (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      event_type VARCHAR(100) NOT NULL,
      payload JSONB NOT NULL,
      timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  
  CREATE INDEX idx_tasks_status ON tasks(status);
  CREATE INDEX idx_task_steps_task_id ON task_steps(task_id);
  CREATE INDEX idx_execution_logs_task_id ON execution_logs(task_id);
  CREATE INDEX idx_telemetry_event_type ON telemetry(event_type);
  ```
- **Status:** [ ]

#### Task 1.4.3: Verify pgvector Extension
- **Command:** `alembic upgrade head`
- **Verify:** `psql -U postgres -d plasmaagent -c "\dx vector"`
- **Status:** [ ]

---

### Sub-Phase 1.5: PTSM (PostgreSQL Transactional State Machine) (~3 hours)

#### Task 1.5.1: Define State Enum
- **File:** `src/plasmaagent/core/state_machine.py`
- **Enum:** `TaskStatus = PENDING | RUNNING | PAUSED | COMPLETED | FAILED | CANCELLED`
- **Status:** [ ]

#### Task 1.5.2: Implement State Transitions
- **File:** `src/plasmaagent/core/state_machine.py`
- **Function:** `async def transition_task_state(conn, task_id, new_status)`
- **Logic:**
  - Validate allowed transitions
  - Use `SELECT ... FOR UPDATE SKIP LOCKED`
  - Atomic update with timestamp
- **Status:** [ ]

#### Task 1.5.3: Implement Crash Recovery
- **File:** `src/plasmaagent/core/state_machine.py`
- **Function:** `async def recover_crashed_tasks(conn)`
- **Logic:** Find RUNNING tasks, mark as PAUSED or FAILED
- **Status:** [ ]

#### Task 1.5.4: Write State Machine Tests
- **File:** `tests/unit/test_state_machine.py`
- **Tests:**
  - All valid transitions
  - Invalid transition rejection
  - Concurrent transition handling
  - Crash recovery
- **Status:** [ ]

---

### Sub-Phase 1.6: CLI Foundation (~2 hours)

#### Task 1.6.1: Create Main CLI Entry Point
- **File:** `src/plasmaagent/cli/main.py`
- **Contents:**
  - Typer app with rich console
  - Version command
  - Help command
- **Status:** [ ]

#### Task 1.6.2: Create PlasmaAgent Theme
- **File:** `src/plasmaagent/cli/theme.py`
- **Colors:**
  - Electric Cyan (#00FFFF) — primary
  - Plasma Magenta (#FF00FF) — error/warning
  - Deep Violet (#8B00FF) — info
- **Status:** [ ]

#### Task 1.6.3: Create ASCII Logo
- **File:** `src/plasmaagent/cli/logo.py`
- **Design:** Plasma sphere (circular with energy lines)
- **Status:** [ ]

#### Task 1.6.4: Implement Doctor Command
- **Command:** `plasma doctor`
- **Checks:**
  - Python version
  - PostgreSQL connection
  - pgvector extension
  - Database schema version
- **Status:** [ ]

---

### Sub-Phase 1.7: Task Lifecycle CLI (~3 hours)

#### Task 1.7.1: Create Task Commands Module
- **File:** `src/plasmaagent/cli/tasks.py`
- **Status:** [ ]

#### Task 1.7.2: Implement `plasma task create`
- **Arguments:** `--name`, `--description`
- **Output:** Task ID
- **Status:** [ ]

#### Task 1.7.3: Implement `plasma task run`
- **Arguments:** `--id`
- **Logic:** Transition to RUNNING
- **Status:** [ ]

#### Task 1.7.4: Implement `plasma task cancel`
- **Arguments:** `--id`
- **Logic:** Transition to CANCELLED
- **Status:** [ ]

#### Task 1.7.5: Implement `plasma task retry`
- **Arguments:** `--id`
- **Logic:** Reset to PENDING
- **Status:** [ ]

#### Task 1.7.6: Implement `plasma task list`
- **Arguments:** `--status` (optional filter)
- **Output:** Rich table
- **Status:** [ ]

#### Task 1.7.7: Implement `plasma task show`
- **Arguments:** `--id`
- **Output:** Task details with steps
- **Status:** [ ]

---

### Sub-Phase 1.8: Integration Tests (~2 hours)

#### Task 1.8.1: Test Full Task Lifecycle
- **File:** `tests/integration/test_lifecycle.py`
- **Flow:** create → run → complete
- **Status:** [ ]

#### Task 1.8.2: Test State Transitions
- **File:** `tests/integration/test_state_transitions.py`
- **Status:** [ ]

#### Task 1.8.3: Test Crash Recovery
- **File:** `tests/integration/test_crash_recovery.py`
- **Status:** [ ]

#### Task 1.8.4: Test pgvector Operations
- **File:** `tests/integration/test_pgvector.py`
- **Status:** [ ]

#### Task 1.8.5: Code Coverage Check
- **Command:** `pytest --cov=src/plasmaagent`
- **Target:** >90%
- **Status:** [ ]

---

## Phase 2: Execution Engine (Skeleton)

### Sub-Phase 2.1: Shell Executor
- Subprocess with PTY
- Output streaming
- Timeout handling

### Sub-Phase 2.2: Step Management
- Step creation
- Status tracking
- Output capture to execution_logs

### Sub-Phase 2.3: Real-time Streaming
- CLI output streaming
- Log tailing

---

## Phase 3: AI & LLM Integration (Skeleton)

### Sub-Phase 3.1: Context Manager
- pgvector embeddings
- Similarity search

### Sub-Phase 3.2: LLM Provider
- OpenAI integration
- Anthropic integration
- Local model support

### Sub-Phase 3.3: Self-Healing
- Error analysis
- Retry suggestion
- Command correction

---

## Phase 4: Advanced Features (Skeleton)

### Sub-Phase 4.1: Multi-step Planning
- Task decomposition
- Dependency graph

### Sub-Phase 4.2: Learning System
- Success pattern recognition
- Failure pattern avoidance

### Sub-Phase 4.3: Performance Optimization
- Parallel step execution
- Caching layer
