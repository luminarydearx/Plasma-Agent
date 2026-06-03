<div align="center">

```
██████╗ ██╗      █████╗ ███████╗███╗   ███╗ █████╗
██╔══██╗██║     ██╔══██╗██╔════╝████╗ ████║██╔══██╗
██████╔╝██║     ███████║███████╗██╔████╔██║███████║
██╔═══╝ ██║     ██╔══██║╚════██║██║╚██╔╝██║██╔══██║
██║     ███████╗██║  ██║███████║██║ ╚═╝ ██║██║  ██║
╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝
          ⚡ A G E N T   ⚡
```

# 🌌 Database-Centric Autonomous AI Agent

### *Reason, Plan, Execute, Learn — All on PostgreSQL*

[![Python](https://img.shields.io/badge/Python-3.13+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18+-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![psycopg3](https://img.shields.io/badge/psycopg-3.2+-green)](https://www.psycopg.org/)
[![pytest](https://img.shields.io/badge/pytest-887%20tests-brightgreen?logo=pytest)](https://pytest.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)](#)
[![Phase](https://img.shields.io/badge/Phase-Production%20Ready-8B00FF)](#)

</div>

---

## ✨ Overview

**PlasmaAgent** adalah autonomous AI agent yang berjalan sepenuhnya di atas PostgreSQL sebagai state store. Tanpa Redis, tanpa Celery, tanpa message broker, tanpa local LLM storage — hanya **Python + PostgreSQL** untuk production-grade autonomous task orchestration.

```
╭─────────────────────────────────────────────────────────────────╮
│  🧠 Reason → 📋 Plan → ⚡ Execute → 📊 Learn → 🔄 Improve     │
│       ↑                                              │          │
│       └──────────── 🌟 Self-Evolution ───────────────┘          │
╰─────────────────────────────────────────────────────────────────╯
```

### 🎯 What Makes PlasmaAgent Different?

| Feature | Traditional Agents | PlasmaAgent |
|---------|-------------------|-------------|
| State Management | Redis/Celery/Files | ✅ PostgreSQL only |
| LLM Storage | 10-40GB local models | ✅ Zero storage (rule-based + cloud-ready) |
| Task Planning | Manual | ✅ Natural language → auto-decomposed |
| Error Recovery | Manual intervention | ✅ Automatic retry + suggestions |
| Self-Improvement | None | ✅ Learns from execution history |
| Concurrency | Message brokers | ✅ PostgreSQL `FOR UPDATE SKIP LOCKED` |

---

## 🚀 Features

### 🧠 Phase 3: Advanced Intelligence

#### 🎯 Natural Language Understanding
- **🧠 Natural Language Task Generation** — "backup database setiap jam 2 pagi" → task otomatis
- **🔀 Task Decomposition** — Break complex tasks into sub-tasks dengan dependency graph (DAG)
- **💾 Context Manager** — Pass context antar sequential tasks (`${prev_task.output}`)
- **🛡️ Error Recovery** — Intelligent suggestions saat task gagal dengan 10+ error patterns
- **🎯 Conditional Execution** — Execute steps berdasarkan kondisi (`if ${prev.exit_code} == 0`)
- **⚡ Parallel Execution** — Run independent steps concurrently dengan semaphore control
- **🔄 Retry Strategies** — Exponential backoff, max retries, conditional retry

#### 📊 Self-Improvement Loop
- **📈 Template Metrics** — Track success rates, execution times, failure patterns
- **🎨 Template Evolution** — Learn dari successful patterns
- **🏷️ Template Versioning** — Track template changes over time
- **🔬 A/B Testing** — Compare template versions dengan statistical analysis
- **🗑️ Template Retirement** — Auto-retire low-performing templates
- **🤖 Auto-Template Generation** — Create new templates dari user patterns

#### 💡 Smart Suggestions Engine
- **🎯 Next Action Recommendations** — Context-aware suggestions berdasarkan task state
- **🔍 Similar Task Discovery** — Find related tasks menggunakan command similarity
- **🚨 Anomaly Detection** — Detect suspicious commands (`rm -rf`, `format c:`, SQL injection)
- **⚡ Performance Analysis** — Identify slow commands & optimization opportunities
- **📊 General Suggestions** — System-wide recommendations dari task patterns

### ⚡ Phase 2: Execution Engine

#### 🐚 Shell Executor
- **Async subprocess** dengan real-time output capture
- **Semaphore-based concurrency** control (max 100 parallel)
- **Fail-fast cancellation** dengan proper task cleanup
- **Timeout handling** (max 24 hours per task)
- **Cross-platform** (Windows/Linux/macOS)

#### 📝 Step Management
- Track setiap command dengan status, exit code, duration
- **Execution logs** tersimpan di database (stdout/stderr)
- **Retry mechanism** — FAILED → PENDING, run lagi dari step yang gagal
- **Timeout & Cancellation** — Configurable per task

### 🗄️ Phase 1: Database-Centric Foundation

#### 🏛️ PTSM (PostgreSQL Transactional State Machine)
```
     ┌─────────┐
     │ PENDING │◄──────────── retry
     └────┬────┘               │
          │ run                │
          ▼                    │
     ┌─────────┐               │
     │ RUNNING │──── fail ────►├───► FAILED
     └────┬────┘               │
          │                    │
          ├──── cancel ───────►├───► CANCELLED
          │                    │
          └──── complete ─────►└───► COMPLETED
```

- **Valid state transitions** enforced di database level
- **`FOR UPDATE SKIP LOCKED`** untuk concurrent safety
- **Atomic transactions** — Crash recovery otomatis
- **Connection pooling** — psycopg3 AsyncConnectionPool dengan SelectorEventLoop

### 🎨 Developer Experience

- **🎭 Plasma Theme** — Rich panels dengan cosmic colors (Cyan, Magenta, Violet, Gold, Aurora Green, Nebula Pink)
- **📦 CLI-First Design** — Semua operasi via terminal (Typer + Rich)
- **🔍 Doctor Command** — System health check dalam satu command
- **📊 Metrics Dashboard** — Real-time performance tracking
- **🔐 Security Hardening** — SQL/shell injection protection, input sanitization, null bytes rejection

---

## 📦 Installation

### Prerequisites
- Python 3.13+
- PostgreSQL 18+
- [uv](https://github.com/astral-sh/uv) (recommended Python package manager)

### Quick Install

```bash
# Clone repository
git clone https://github.com/yourusername/plasmaagent.git
cd plasmaagent

# Install dependencies
uv sync

# Setup database
createdb -U postgres plasmaagent

# Run migrations
uv run alembic upgrade head

# Verify installation
uv run plasma doctor
```

---

## 🎬 Quick Start

### 1️⃣ Create a Task

```bash
# Manual task creation
uv run plasma task create \
  --name "Backup Database" \
  --command "pg_dump plasmaagent > backup.sql" \
  --command "echo Backup completed"

# 🧠 AI-powered task generation (natural language)
uv run plasma task generate --input "backup database postgresql setiap jam 2 pagi" --yes
```

### 2️⃣ Execute

```bash
# Run task with real-time output
uv run plasma task run --id <task-id>

# Run with streaming output
uv run plasma task run --id <task-id> --stream
```

### 3️⃣ Monitor & Analyze

```bash
# List all tasks
uv run plasma task list

# Show task details with logs & steps
uv run plasma task show --id <task-id> --logs
uv run plasma task show --id <task-id> --steps

# 📊 View metrics & performance
uv run plasma metrics show
uv run plasma metrics analyze
uv run plasma metrics optimize
```

### 4️⃣ Smart Suggestions

```bash
# Get AI-powered recommendations
uv run plasma ai suggest --task-id <task-id>

# Find similar tasks
uv run plasma ai similar --task-id <task-id>

# Detect anomalies
uv run plasma ai anomalies --task-id <task-id>
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLI Layer (Typer + Rich)                      │
│   plasma task | plasma metrics | plasma ai | plasma doctor      │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer                               │
│  TaskService | ExecutionService | TaskGenerator | MetricsTracker│
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                  Intelligence Layer (Phase 3)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Decomposer   │  │ Context Mgr  │  │ Error Analyzer│          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Retry Exec   │  │ Parallel Exec│  │ Suggestions  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Template Lrn │  │ A/B Testing  │  │ Auto-Generate│          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    Execution Layer (Phase 2)                     │
│  ShellExecutor | StepManager | ExecutionLogger | RetryExecutor  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│              Data Layer (PostgreSQL + pgvector)                  │
│  tasks | task_steps | execution_logs | template_metrics         │
│  template_versions | ab_tests | telemetry | alembic_version     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧪 Testing

```bash
# Run full test suite (887+ tests)
uv run pytest

# Run unit tests only (776 tests, ~23s)
uv run pytest tests/unit/

# Run integration tests
uv run pytest tests/integration/

# Run with coverage
uv run pytest --cov=src --cov-report=html
```

### Test Coverage

| Category | Tests | Status |
|----------|------:|--------|
| Core Foundation (Phase 1) | 11 | ✅ |
| Execution Engine (Phase 2) | 45 | ✅ |
| AI Intelligence (Phase 3 MVP) | 51 | ✅ |
| CLI Robustness | 72 | ✅ |
| Self-Improvement (3.4) | 37 | ✅ |
| Advanced Reasoning (3.5) | 408 | ✅ |
| Template Evolution (3.6) | 207 | ✅ |
| Smart Suggestions (3.7) | 70 | ✅ |
| **Total** | **887+** | **✅ 100%** |

### Hybrid Testing Philosophy
Setiap sub-phase di-test secara menyeluruh:
- ✅ Unit tests (model, service, utility)
- ✅ Integration tests (end-to-end flow)
- ✅ Edge cases (security, stress, boundary)
- ✅ Performance tests (concurrency, large data)
- ✅ Cross-phase regression (no breakage)

---

## 📚 CLI Commands

```
Usage: plasma [OPTIONS] COMMAND [ARGS]...

╭─ Commands ──────────────────────────────────────────────────╮
│ doctor     Check system health and dependencies             │
│ task       Task management commands                         │
│ metrics    Template metrics & optimization                  │
│ ai         AI-powered operations & suggestions              │
│ schedule   Task scheduling (cron-like)                      │
│ templates  Template evolution management                    │
╰─────────────────────────────────────────────────────────────╯
```

### Task Commands
- `plasma task create` — Create new task
- `plasma task list` — List all tasks
- `plasma task show` — Show task details (with `--logs`, `--steps`)
- `plasma task run` — Execute task
- `plasma task cancel` — Cancel running task
- `plasma task retry` — Retry failed task
- `plasma task delete` — Delete task
- `plasma task generate` — 🧠 AI-powered task generation from natural language

### AI Commands
- `plasma ai suggest` — Get smart suggestions for a task
- `plasma ai similar` — Find similar tasks
- `plasma ai anomalies` — Detect suspicious patterns
- `plasma ai performance` — Analyze execution performance

### Metrics Commands
- `plasma metrics show` — View template metrics
- `plasma metrics analyze` — Run pattern analysis
- `plasma metrics optimize` — Get optimization recommendations

---

## 🔒 Security Features

- ✅ **Input Sanitization** — Null bytes, SQL injection, shell injection protection
- ✅ **Length Limits** — MAX_INPUT_LENGTH = 10,000 chars
- ✅ **Fail-Fast Validation** — Non-interactive mode protection (no hanging)
- ✅ **Parameterized Queries** — All database operations safe
- ✅ **State Machine Enforcement** — Invalid transitions rejected
- ✅ **Concurrent Safety** — `FOR UPDATE SKIP LOCKED` prevents race conditions
- ✅ **Anomaly Detection** — Automatic detection of dangerous commands
- ✅ **Pattern Matching** — 9+ dangerous command patterns detected

---

## 🌈 Plasma Theme Colors

```
Plasma Cyan     #00D4FF  — Primary actions, info
Plasma Magenta  #FF00D4  — Errors, warnings
Plasma Violet   #8B00FF  — Information
Solar Gold      #FFD700  — Highlights, titles
Aurora Green    #00FF7F  — Success
Nebula Pink     #FF1493  — Accents
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.13+ |
| Database | PostgreSQL 18+ with pgvector |
| ORM | psycopg3 (async) |
| Migrations | Alembic |
| CLI | Typer + Rich |
| Testing | pytest + pytest-asyncio |
| Package Manager | uv |
| Vector Search | pgvector |
| Validation | Pydantic V2 |
| Task Decomposition | Custom DAG engine |
| Parallel Execution | asyncio + semaphore |

---

## 📖 Documentation

- 📘 [ROADMAP.md](ROADMAP.md) — Project roadmap & phases
- 🎨 [PLASMA_THEME.md](docs/PLASMA_THEME.md) — Theme & color system
- 🏗️ [Architecture](docs/ARCHITECTURE.md) — Deep dive into design
- 🔌 [API Reference](docs/API.md) — Full API documentation

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

### Development Setup

```bash
# Fork and clone
git clone https://github.com/yourusername/plasmaagent.git
cd plasmaagent

# Create virtualenv
uv venv
uv sync

# Run tests
uv run pytest -v

# Run linter
uv run ruff check src/ tests/
```

### Code Standards
- **No comments** — Self-documenting code with clear names
- **Type hints** — 100% coverage dengan Pydantic V2
- **Single blank line** — Clean, readable spacing
- **Hybrid testing** — Every feature tested comprehensively

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- 🎨 **Rich** — Beautiful terminal formatting
- 🐘 **PostgreSQL** — World's most advanced open source database
- 🐍 **Python** — Programming language
- ⚡ **psycopg3** — Modern PostgreSQL adapter
- 🚀 **Typer** — CLI framework
- 🧪 **pytest** — Testing framework

---

<div align="center">

### 🌟 Made with 💜 by the PlasmaAgent Team

**If this project helps you, please consider giving it a ⭐**

[Report Bug](https://github.com/yourusername/plasmaagent/issues) · [Request Feature](https://github.com/yourusername/plasmaagent/issues)

---

*Built with ❤️ for the autonomous agent community*

*From natural language to autonomous execution — that's the Plasma way.* ⚡

</div>
