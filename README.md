<div align="center">

```
██████╗ ██╗      █████╗ ███████╗███╗   ███╗ █████╗ 
██╔══██╗██║     ██╔══██╗██╔════╝████╗ ████║██╔══██╗
██████╔╝██║     ███████║███████╗██╔████╔██║███████║
██╔═══╝ ██║     ██╔══██║╚════██║██║╚██╔╝██║██╔══██║
██║     ███████╗██║  ██║███████║██║ ╚═╝ ██║██║  ██║
╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝
```

# 🌌 Database-Centric Agentic Execution Framework

### *Your Autonomous AI Agent, Powered by PostgreSQL*

[![Python](https://img.shields.io/badge/Python-3.13+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18+-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![psycopg3](https://img.shields.io/badge/psycopg-3.2+-green)](https://www.psycopg.org/)
[![pytest](https://img.shields.io/badge/pytest-216%20tests-brightgreen?logo=pytest)](https://pytest.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)](#)
[![Phase](https://img.shields.io/badge/Phase-Complete-8B00FF)](#)

</div>

---

## ✨ Overview

**PlasmaAgent** adalah autonomous AI agent yang berjalan sepenuhnya di atas PostgreSQL sebagai state store. Tanpa Redis, tanpa Celery, tanpa message broker — hanya **Python + PostgreSQL** untuk production-grade task orchestration.

```
╭─────────────────────────────────────────────────────────────╮
│  🧠 Natural Language → 📋 Task → ⚡ Execution → 📊 Learn     │
│       ↑                                         │           │
│       └──────────── 🔄 Self-Improvement ────────┘           │
╰─────────────────────────────────────────────────────────────╯
```

---

## 🚀 Features

### 🎯 Core Intelligence
- **🧠 Natural Language Task Generation** — "backup database setiap jam 2 pagi" → task otomatis
- **🔀 Task Decomposition** — Break complex tasks into sub-tasks dengan dependency graph
- **💾 Context Manager** — Pass context antar sequential tasks (`${prev_task.output}`)
- **🛡️ Error Recovery** — Intelligent suggestions saat task gagal
- **📊 Self-Improvement Loop** — Auto-adjust confidence scores dari execution history
- **🎨 Template Evolution** — Learn dari successful patterns, retire low performers
- **💡 Smart Suggestions** — Next action recommendations & anomaly detection

### ⚡ Execution Engine
- **🐚 Shell Executor** — Async subprocess dengan real-time output capture
- **📝 Step Management** — Track setiap command dengan status, exit code, duration
- **📜 Execution Logs** — Semua stdout/stderr tersimpan di database
- **🔄 Retry Mechanism** — FAILED → PENDING, run lagi dari step yang gagal
- **⏱️ Timeout & Cancellation** — Configurable per task

### 🗄️ Database-Centric Architecture
- **🏛️ PTSM (PostgreSQL Transactional State Machine)** — Valid state transitions dengan `FOR UPDATE SKIP LOCKED`
- **📈 pgvector Embeddings** — Semantic search untuk RAG & memory
- **💾 Atomic Transactions** — Crash recovery otomatis
- **🔗 Connection Pooling** — psycopg3 AsyncConnectionPool dengan SelectorEventLoop

### 🎨 Developer Experience
- **🎭 Plasma Theme** — Rich panels dengan cosmic colors (Cyan, Magenta, Violet, Gold)
- **📦 CLI-First Design** — Semua operasi via terminal (Typer + Rich)
- **🔍 Doctor Command** — System health check dalam satu command
- **📊 Metrics & Observability** — Real-time performance tracking
- **🔐 Security Hardening** — SQL/shell injection protection, input sanitization

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

# AI-powered task generation
uv run plasma task generate --input "backup database postgresql" --yes
```

### 2️⃣ Execute

```bash
uv run plasma task run --id <task-id>
```

### 3️⃣ Monitor

```bash
# List all tasks
uv run plasma task list

# Show task details with logs
uv run plasma task show --id <task-id> --logs

# Show execution steps
uv run plasma task show --id <task-id> --steps
```

### 4️⃣ Analyze & Optimize

```bash
# View metrics
uv run plasma metrics show

# Analyze patterns
uv run plasma metrics analyze

# Get optimization recommendations
uv run plasma metrics optimize
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Layer (Typer + Rich)                 │
│   plasma task | plasma metrics | plasma doctor | plasma ai  │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                            │
│  TaskService | ExecutionService | TaskGenerator | Metrics   │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                  Intelligence Layer                         │
│  RuleBasedProvider | TaskDecomposer | ContextManager        │
│  Optimizer | Suggester | RecoveryAdvisor                    │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                  Execution Layer                            │
│  ShellExecutor | StepManager | ExecutionLogger              │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│              Data Layer (PostgreSQL + pgvector)             │
│  tasks | task_steps | execution_logs | template_metrics     │
│  telemetry | alembic_version                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 Task Lifecycle

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

---

## 🧪 Testing

```bash
# Run full test suite (216 tests)
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test category
uv run pytest tests/integration/
uv run pytest tests/unit/
```

### Test Coverage

| Category | Tests | Status |
|----------|-------|--------|
| Core Foundation | 11 | ✅ |
| Execution Engine | 45 | ✅ |
| AI Intelligence | 51 | ✅ |
| CLI Robustness | 72 | ✅ |
| Self-Improvement | 37 | ✅ |
| **Total** | **216** | **✅ 100%** |

---

## 📚 CLI Commands

```
Usage: plasma [OPTIONS] COMMAND [ARGS]...

╭─ Commands ──────────────────────────────────────────────────╮
│ doctor     Check system health and dependencies             │
│ task       Task management commands                         │
│ metrics    Template metrics & optimization                  │
│ ai         AI-powered operations                            │
│ schedule   Task scheduling (cron-like)                      │
╰─────────────────────────────────────────────────────────────╯
```

### Task Commands
- `plasma task create` — Create new task
- `plasma task list` — List all tasks
- `plasma task show` — Show task details
- `plasma task run` — Execute task
- `plasma task cancel` — Cancel running task
- `plasma task retry` — Retry failed task
- `plasma task delete` — Delete task
- `plasma task generate` — AI-powered task generation

---

## 🔒 Security Features

- ✅ **Input Sanitization** — Null bytes, SQL injection, shell injection protection
- ✅ **Length Limits** — MAX_INPUT_LENGTH = 10,000 chars
- ✅ **Fail-Fast Validation** — Non-interactive mode protection
- ✅ **Parameterized Queries** — All database operations safe
- ✅ **State Machine Enforcement** — Invalid transitions rejected
- ✅ **Concurrent Safety** — `FOR UPDATE SKIP LOCKED` prevents race conditions

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
| Database | PostgreSQL 18+ |
| ORM | psycopg3 (async) |
| Migrations | Alembic |
| CLI | Typer + Rich |
| Testing | pytest + pytest-asyncio |
| Package Manager | uv |
| Vector Search | pgvector |
| Validation | Pydantic V2 |

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

---

<div align="center">

### 🌟 Made with 💜 by the PlasmaAgent Team

**If this project helps you, please consider giving it a ⭐**

[Report Bug](https://github.com/yourusername/plasmaagent/issues) · [Request Feature](https://github.com/yourusername/plasmaagent/issues)

---

*Built with ❤️ for the autonomous agent community*

</div>