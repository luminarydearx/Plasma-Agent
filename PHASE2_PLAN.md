# Phase 2: Execution Engine - Implementation Plan

## Overview

Phase 2 mengimplementasikan **Execution Engine** — "body" dari agent yang bertanggung jawab mengeksekusi perintah shell dan mencatat hasilnya ke database.

**Goal:** Agent dapat menjalankan shell commands, capture output secara real-time, dan menyimpan execution history di `execution_logs` table.

---

## Architecture Compliance

### Principles yang Harus Dijaga

1. **Every Action is an Atomic Transaction**
   - Setiap state transition (PENDING → RUNNING → COMPLETED/FAILED) adalah atomic SQL UPDATE
   - Setiap execution_log entry adalah INSERT dalam transaction

2. **All State is Persistent**
   - Tidak ada in-memory state yang tidak di-persist ke database
   - Output stream langsung di-insert ke `execution_logs`
   - Step status di-update di `task_steps` secara real-time

3. **Database-Centric Execution**
   - Execution Engine membaca `task_steps` untuk tahu command apa yang harus dijalankan
   - Execution Engine menulis output ke `execution_logs`
   - Execution Engine mengupdate `task_steps.status` setelah selesai

4. **Observability**
   - Setiap command execution di-log ke `execution_logs` dengan timestamp, output, error, duration
   - Telemetry dicatat ke `telemetry` table untuk setiap operation

---

## Components

### 1. Shell Executor (`src/plasmaagent/executor/shell.py`)

**Responsibility:**
- Menjalankan shell command via `subprocess` dengan PTY support (Windows)
- Capture stdout dan stderr secara real-time
- Handle timeout dan cancellation
- Return exit code, output, dan duration

**Technical Details:**
- Gunakan `asyncio.create_subprocess_shell` untuk async execution
- Windows PTY emulation via `conpty` atau fallback ke `subprocess.PIPE`
- Streaming output: setiap line langsung di-insert ke `execution_logs`
- Timeout: configurable per step (default 300s)
- Cancellation: check `task.status` setiap 1 detik, abort jika CANCELLED

**Key Functions:**
```python
async def execute_shell_command(
    command: str,
    step_id: UUID,
    timeout: int = 300
) -> ExecutionResult
```

### 2. Execution Service (`src/plasmaagent/services/execution_service.py`)

**Responsibility:**
- Orchestrate execution of all steps untuk sebuah task
- Read `task_steps` dari database
- Call Shell Executor untuk setiap step
- Update `task_steps.status` (PENDING → RUNNING → COMPLETED/FAILED)
- Update `tasks.status` setelah semua steps selesai
- Handle retry logic (re-run failed steps)

**Key Functions:**
```python
async def execute_task(task_id: UUID) -> None
async def execute_step(step_id: UUID) -> StepResult
```

### 3. Execution Logger (`src/plasmaagent/services/execution_logger.py`)

**Responsibility:**
- Insert execution output ke `execution_logs` table
- Real-time streaming: setiap line output langsung di-persist
- Calculate duration untuk setiap log entry
- Handle large output (chunking jika > 10KB per line)

**Key Functions:**
```python
async def log_output(step_id: UUID, output: str, stream: str) -> None
async def get_execution_logs(step_id: UUID) -> list[ExecutionLog]
```

### 4. Step Manager (`src/plasmaagent/services/step_manager.py`)

**Responsibility:**
- Create steps untuk sebuah task (dari plan)
- Update step status (PENDING → RUNNING → COMPLETED/FAILED)
- Query steps untuk sebuah task
- Handle step ordering dan dependencies

**Key Functions:**
```python
async def create_step(task_id: UUID, command: str, order: int) -> UUID
async def update_step_status(step_id: UUID, status: StepStatus) -> None
async def get_task_steps(task_id: UUID) -> list[TaskStep]
```

### 5. CLI Commands (`src/plasmaagent/cli/execute.py`)

**Responsibility:**
- `plasma execute run <task-id>` — Jalankan task (execute all steps)
- `plasma execute status <task-id>` — Tampilkan progress execution
- `plasma execute logs <task-id>` — Tampilkan execution logs
- `plasma execute logs --stream <task-id>` — Real-time log streaming

**Key Commands:**
```bash
plasma execute run <task-id>
plasma execute status <task-id>
plasma execute logs <task-id> [--stream]
```

---

## Database Schema (Phase 2 Extensions)

### `task_steps` Table

```sql
CREATE TABLE task_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    step_number INT NOT NULL,
    command TEXT NOT NULL,
    status step_status NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INT,
    exit_code INT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(task_id, step_number)
);

CREATE INDEX idx_task_steps_task_id ON task_steps(task_id);
CREATE INDEX idx_task_steps_status ON task_steps(status);
```

### `execution_logs` Table

```sql
CREATE TABLE execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    step_id UUID NOT NULL REFERENCES task_steps(id) ON DELETE CASCADE,
    stream execution_stream NOT NULL,
    output TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_execution_logs_step_id ON execution_logs(step_id);
CREATE INDEX idx_execution_logs_timestamp ON execution_logs(timestamp);
```

---

## Task Breakdown

### Sub-Phase 2.1: Database Schema Extensions (~2 hours)

1. **Task 2.1.1:** Create Alembic migration untuk `task_steps` dan `execution_logs`
   - File: `migrations/versions/002_add_execution_tables.py`
   - Verify: `uv run alembic upgrade head`
   - Verify: `psql -c "\dt"` — tables exist

2. **Task 2.1.2:** Update models (`task_step.py`, `execution_log.py`)
   - File: `src/plasmaagent/models/task_step.py`
   - File: `src/plasmaagent/models/execution_log.py`
   - Verify: `uv run pytest tests/unit/test_models.py`

### Sub-Phase 2.2: Shell Executor (~4 hours)

3. **Task 2.2.1:** Implement `ShellExecutor` class
   - File: `src/plasmaagent/executor/shell.py`
   - Features: subprocess, timeout, PTY support (Windows)
   - Verify: Unit test — execute `echo "hello"` dan verify output

4. **Task 2.2.2:** Implement real-time output capture
   - File: `src/plasmaagent/executor/shell.py`
   - Features: async stream reader, line-by-line capture
   - Verify: Unit test — execute `ping -n 3` dan verify 3 lines captured

5. **Task 2.2.3:** Implement cancellation support
   - File: `src/plasmaagent/executor/shell.py`
   - Features: check task status, terminate subprocess
   - Verify: Unit test — cancel long-running command

### Sub-Phase 2.3: Execution Logger (~2 hours)

6. **Task 2.3.1:** Implement `ExecutionLogger` service
   - File: `src/plasmaagent/services/execution_logger.py`
   - Features: insert logs, query logs, calculate duration
   - Verify: Unit test — insert dan query logs

7. **Task 2.3.2:** Integrate logger dengan ShellExecutor
   - File: `src/plasmaagent/executor/shell.py`
   - Features: setiap line output langsung di-log
   - Verify: Integration test — execute command dan verify logs di database

### Sub-Phase 2.4: Step Manager (~2 hours)

8. **Task 2.4.1:** Implement `StepManager` service
   - File: `src/plasmaagent/services/step_manager.py`
   - Features: create step, update status, query steps
   - Verify: Unit test — create dan update steps

9. **Task 2.4.2:** Implement step ordering logic
   - File: `src/plasmaagent/services/step_manager.py`
   - Features: execute steps dalam urutan `step_number`
   - Verify: Integration test — create 3 steps dan verify order

### Sub-Phase 2.5: Execution Service (~3 hours)

10. **Task 2.5.1:** Implement `ExecutionService` orchestration
    - File: `src/plasmaagent/services/execution_service.py`
    - Features: execute task, execute step, handle retry
    - Verify: Integration test — execute task dengan 2 steps

11. **Task 2.5.2:** Implement retry logic
    - File: `src/plasmaagent/services/execution_service.py`
    - Features: re-execute failed steps, max retries
    - Verify: Integration test — fail step, retry, verify success

### Sub-Phase 2.6: CLI Commands (~3 hours)

12. **Task 2.6.1:** Implement `plasma execute run` command
    - File: `src/plasmaagent/cli/execute.py`
    - Features: run task, show progress, real-time output
    - Verify: Manual test — `plasma execute run <task-id>`

13. **Task 2.6.2:** Implement `plasma execute status` command
    - File: `src/plasmaagent/cli/execute.py`
    - Features: show task status, step statuses, progress
    - Verify: Manual test — `plasma execute status <task-id>`

14. **Task 2.6.3:** Implement `plasma execute logs` command
    - File: `src/plasmaagent/cli/execute.py`
    - Features: show logs, stream logs
    - Verify: Manual test — `plasma execute logs <task-id>`

### Sub-Phase 2.7: Integration Tests (~3 hours)

15. **Task 2.7.1:** Write integration tests untuk ShellExecutor
    - File: `tests/integration/test_shell_executor.py`
    - Coverage: execute, timeout, cancellation
    - Verify: `uv run pytest tests/integration/test_shell_executor.py`

16. **Task 2.7.2:** Write integration tests untuk ExecutionService
    - File: `tests/integration/test_execution_service.py`
    - Coverage: execute task, execute step, retry
    - Verify: `uv run pytest tests/integration/test_execution_service.py`

17. **Task 2.7.3:** Write integration tests untuk CLI commands
    - File: `tests/integration/test_execute_cli.py`
    - Coverage: run, status, logs
    - Verify: `uv run pytest tests/integration/test_execute_cli.py`

### Sub-Phase 2.8: Documentation & Audit (~1 hour)

18. **Task 2.8.1:** Update PROJECT_STRUCTURE.md
    - File: `PROJECT_STRUCTURE.md`
    - Add: executor/, services/execution_*.py, cli/execute.py

19. **Task 2.8.2:** Create PHASE2_AUDIT.md
    - File: `PHASE2_AUDIT.md`
    - Content: architecture compliance, test results, known limitations

---

## Technical Decisions

### 1. Shell Execution Strategy

**Decision:** Gunakan `asyncio.create_subprocess_shell` untuk Windows

**Rationale:**
- Async-native, compatible dengan psycopg3 async pool
- Support timeout dan cancellation
- PTY support via `conpty` (Windows 10+) atau fallback ke `subprocess.PIPE`

**Trade-offs:**
- Pro: Simple, async, well-documented
- Con: PTY emulation di Windows bisa tricky

### 2. Real-time Output Streaming

**Decision:** Setiap line output langsung di-insert ke `execution_logs`

**Rationale:**
- Observability: output tersedia real-time di database
- Durability: jika process crash, output yang sudah di-log tidak hilang
- Queryable: bisa query logs dengan SQL

**Trade-offs:**
- Pro: Real-time observability, durable
- Con: Database I/O overhead (acceptable untuk single-node)

### 3. Step Execution Order

**Decision:** Execute steps dalam urutan `step_number` ascending

**Rationale:**
- Simple, predictable
- Sesuai dengan plan generation (steps di-generate dalam urutan)
- Future: bisa extend dengan dependencies jika perlu

**Trade-offs:**
- Pro: Simple, easy to understand
- Con: No parallel execution (acceptable untuk Phase 2)

### 4. Retry Logic

**Decision:** Re-execute failed step dari awal (no checkpoint/resume)

**Rationale:**
- Simple, stateless
- Sesuai dengan PTSM (PostgreSQL Transactional State Machine)
- Future: bisa extend dengan checkpoint jika perlu

**Trade-offs:**
- Pro: Simple, no state management complexity
- Con: Inefficient untuk long-running steps (acceptable untuk Phase 2)

---

## Success Metrics

### Functional Requirements

- ✅ Shell commands dapat dijalankan via `plasma execute run`
- ✅ Output di-capture real-time dan di-persist ke `execution_logs`
- ✅ Step status di-update real-time (PENDING → RUNNING → COMPLETED/FAILED)
- ✅ Task status di-update setelah semua steps selesai
- ✅ Retry logic bekerja (re-execute failed steps)
- ✅ Cancellation bekerja (abort execution jika task di-cancel)

### Non-Functional Requirements

- ✅ 100% state transitions adalah atomic (transactional)
- ✅ 100% output di-persist ke database (no in-memory buffering)
- ✅ Real-time observability (logs tersedia segera setelah command dijalankan)
- ✅ Crash recovery (jika process crash, task dapat di-resume dari step terakhir)

### Performance Requirements

- ✅ Shell command execution latency < 100ms (overhead dari database logging)
- ✅ Output streaming latency < 500ms (dari command ke database)
- ✅ Support commands hingga 300s timeout (configurable)

---

## Constraints

### Hard Constraints

1. **No Docker** — Execution berjalan native di Windows 11
2. **No Redis** — Tidak ada message queue atau pub/sub
3. **No Filesystem Access** — Execution Engine tidak boleh read/write file
4. **Python 3.13.3 Only** — Tidak ada bahasa lain
5. **PostgreSQL Only** — Tidak ada database lain

### Soft Constraints

1. **Single-Node** — Tidak ada distributed execution
2. **Sequential Execution** — Steps dijalankan satu per satu (no parallel)
3. **CLI-First** — Frontend dilarang sampai diperintahkan

---

## Risks & Mitigations

### Risk 1: PTY Emulation di Windows

**Description:** Windows tidak memiliki native PTY seperti Unix. `conpty` tersedia di Windows 10+ tapi bisa tricky.

**Mitigation:**
- Gunakan `subprocess.PIPE` sebagai fallback jika PTY tidak tersedia
- Test di Windows 11 untuk verify compatibility
- Jika PTY tidak bekerja, accept plain text output (no ANSI colors)

### Risk 2: Database I/O Overhead

**Description:** Setiap line output di-insert ke database bisa lambat untuk commands dengan banyak output.

**Mitigation:**
- Batch insert jika output > 100 lines (insert setiap 100 lines)
- Use async database operations (non-blocking)
- Monitor performance, optimize jika perlu

### Risk 3: Long-Running Commands

**Description:** Commands yang berjalan > 5 menit bisa timeout atau consume resources.

**Mitigation:**
- Configurable timeout per step (default 300s)
- Cancellation support (check task status setiap 1 detik)
- Progress reporting (update task_steps.status real-time)

---

## Dependencies

### Phase 1 Dependencies

- ✅ Database schema (`tasks`, `task_steps`, `execution_logs`)
- ✅ PTSM (PostgreSQL Transactional State Machine)
- ✅ Async database pool (psycopg3)
- ✅ CLI framework (typer + rich)

### External Dependencies

- `asyncio` — Async subprocess execution
- `subprocess` — Shell command execution
- `psycopg3` — Database operations
- `rich` — CLI output formatting

---

## Timeline

**Estimated Duration:** 20-25 hours (~3-4 days)

**Breakdown:**
- Sub-Phase 2.1 (Schema): 2 hours
- Sub-Phase 2.2 (Shell Executor): 4 hours
- Sub-Phase 2.3 (Logger): 2 hours
- Sub-Phase 2.4 (Step Manager): 2 hours
- Sub-Phase 2.5 (Execution Service): 3 hours
- Sub-Phase 2.6 (CLI Commands): 3 hours
- Sub-Phase 2.7 (Integration Tests): 3 hours
- Sub-Phase 2.8 (Documentation): 1 hour

**Buffer:** +20% untuk debugging dan unexpected issues

---

## Approval Checklist

Sebelum mulai coding, pastikan:

- [ ] User telah approve PHASE2_PLAN.md
- [ ] Phase 1 test suite masih 100% green
- [ ] Database schema Phase 1 intact
- [ ] No comments rule di-enforce (remove semua comments dari Phase 1 code)
- [ ] Execution strategy di-confirm (subprocess + PTY)
- [ ] Retry strategy di-confirm (re-execute dari awal)
- [ ] Timeout default di-confirm (300s)

---

## Next Steps

1. **Wait for user approval**
2. **Clean up Phase 1 code** (remove all comments)
3. **Start Sub-Phase 2.1** (database schema extensions)
4. **Implement Sub-Phases 2.2 - 2.8**
5. **Create PHASE2_AUDIT.md**
6. **Wait for user review**
7. **Start Phase 3** (Reasoning Engine / AI integration)

---

## Code Quality Standards

### No Comments Rule

**Rule:** Tidak boleh ada komentar (# maupun """) di seluruh codebase.

**Rationale:**
- Code harus self-documenting
- Variable names, function names, dan structure harus clear
- Jika perlu penjelasan, refactor code agar lebih clear

**Enforcement:**
- Linter akan flag comments sebagai error
- CI akan fail jika ada comments
- Manual review sebelum commit

### Code Style

- **Naming:** snake_case untuk variables/functions, PascalCase untuk classes
- **Type Hints:** Required untuk semua function signatures
- **Docstrings:** DILARANG (no """ blocks)
- **Line Length:** Max 100 characters
- **Imports:** Group imports (stdlib, third-party, local)

---

## Conclusion

Phase 2 akan mengimplementasikan **Execution Engine** yang robust, observable, dan resilient. Semua execution state di-persist ke PostgreSQL, memastikan durability dan crash recovery. Real-time output streaming memberikan observability yang excellent. Retry dan cancellation support memastikan flexibility.

**Ready to start setelah user approval.**
