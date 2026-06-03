# ⚡ PlasmaAgent

**Database-Centric Agentic Execution Framework**

A production-ready AI agent framework that transforms natural language into executable tasks with zero local LLM storage, intelligent self-improvement, and bulletproof reliability.

![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![PostgreSQL](https://img.shields.io/badge/postgresql-18+-336791.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Tests](https://img.shields.io/badge/tests-231%20passed-brightgreen.svg)

---

## 🎯 What is PlasmaAgent?

PlasmaAgent is an autonomous AI agent that:

- **Understands** natural language commands ("backup database postgresql plasmaagent")
- **Generates** executable multi-step tasks with 95% confidence
- **Executes** tasks sequentially with real-time output streaming
- **Learns** from execution history to improve future performance
- **Self-optimizes** template confidence scores based on success metrics
- **Decomposes** complex tasks into sub-tasks with dependency graphs
- **Recovers** from failures with intelligent retry strategies
- **Suggests** next actions based on execution patterns

All without requiring local LLM storage, Docker, Redis, or external services.

---

## ✨ Key Features

### 🧠 Intelligence Engine

- **Rule-Based Pattern Matching** — 5 task templates (backup, cleanup, disk, git, system) with 80-95% confidence
- **Task Decomposition** — Break complex tasks into sub-tasks with sequential/parallel execution modes
- **Self-Improvement Loop** — Track execution metrics, analyze failures, auto-adjust confidence scores
- **Smart Suggestions** — Recommend next actions based on execution history

### ⚡ Execution Engine

- **Async Subprocess Execution** — Run shell commands with real-time stdout/stderr capture
- **Step-by-Step Tracking** — Monitor each command's status, exit code, and duration
- **Failure Handling** — Stop on first failure or continue with error recovery
- **Timeout Support** — Configurable per-task timeouts with graceful cancellation
- **Execution Logging** — Full audit trail stored in PostgreSQL

### 🗄️ Database-Centric Architecture

- **PostgreSQL Transactional State Machine (PTSM)** — Atomic state transitions with crash recovery
- **Async Connection Pool** — psycopg3 with SelectorEventLoop (Windows-compatible)
- **Execution Metrics** — Track success rates, execution times, failure patterns
- **Template Evolution** — Learn from successful user-created tasks

### 🛡️ Production Hardening

- **Security** — SQL injection safe, shell injection prevention, null byte rejection
- **Robustness** — Input validation (max 10,000 chars), fail-fast on edge cases
- **Observability** — Real-time metrics, execution logs, performance tracking
- **CLI-First** — Beautiful Rich-powered terminal UI with Plasma theme

---

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- PostgreSQL 18+
- Windows 11 (tested) / Linux / macOS

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/plasmaagent.git
cd plasmaagent

# Install dependencies with uv
uv sync

# Initialize database
uv run alembic upgrade head

# Verify installation
uv run plasma doctor
```

### First Task

```bash
# Generate task from natural language
uv run plasma task generate --input "backup database postgresql plasmaagent" --yes

# Output:
# ✅ Task created: 24c6d329-ebd8-4496-84b4-b253ffe5b354
# Run with: plasma task run --id 24c6d329-ebd8-4496-84b4-b253ffe5b354

# Execute the task
uv run plasma task run --id 24c6d329-ebd8-4496-84b4-b253ffe5b354

# View execution logs
uv run plasma task show --id 24c6d329-ebd8-4496-84b4-b253ffe5b354 --logs
```

---

## 📖 Usage

### Task Management

```bash
# Create task manually
uv run plasma task create \
  --name "Backup Database" \
  --description "Daily backup" \
  --command "pg_dump -U postgres plasmaagent > backup.sql" \
  --command "echo Backup completed"

# List all tasks
uv run plasma task list

# Show task details
uv run plasma task show --id <task-id>

# Run task
uv run plasma task run --id <task-id>

# Cancel running task
uv run plasma task cancel --id <task-id>

# Retry failed task
uv run plasma task retry --id <task-id>

# Delete task
uv run plasma task delete --id <task-id> --force
```

### AI-Powered Task Generation

```bash
# Preview generated task (no database write)
uv run plasma task generate --input "check disk space" --preview

# Generate and create task
uv run plasma task generate --input "git commit changes" --yes

# Generate with specific provider
uv run plasma task generate --input "show system info" --provider rule_based --yes
```

**Supported Patterns:**
- `backup database postgresql <dbname>` → pg_dump commands
- `cleanup old files in <path>` → File cleanup commands
- `check disk space` → Disk monitoring commands
- `git commit changes` → Git workflow commands
- `show system info` → System information commands

### Metrics & Analytics

```bash
# View template metrics
uv run plasma metrics show

# Analyze low-performing templates
uv run plasma metrics analyze

# Optimize confidence scores (dry run)
uv run plasma metrics optimize --dry-run

# Apply optimizations
uv run plasma metrics optimize
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI Layer                               │
│  (Rich-powered terminal UI, command parsing, user input)    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Intelligence Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Decomposer   │  │ Metrics      │  │ Optimizer    │      │
│  │ (Task →      │  │ Tracker      │  │ (Confidence  │      │
│  │  SubTasks)   │  │ (Success/    │  │  Auto-       │      │
│  │              │  │  Failure)    │  │  Adjust)     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Execution Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Shell        │  │ Step         │  │ Execution    │      │
│  │ Executor     │  │ Manager      │  │ Logger       │      │
│  │ (async       │  │ (Track       │  │ (stdout/     │      │
│  │  subprocess) │  │  progress)   │  │  stderr)     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Database Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Tasks        │  │ Task Steps   │  │ Execution    │      │
│  │ (PTSM        │  │ (Step-by-    │  │ Logs         │      │
│  │  State       │  │  step        │  │ (Full        │      │
│  │  Machine)    │  │  tracking)   │  │  audit       │      │
│  │              │  │              │  │  trail)      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │ Template     │  │ Telemetry    │                        │
│  │ Metrics      │  │ (Events)     │                        │
│  │ (Success     │  │              │                        │
│  │  rates)      │  │              │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧪 Testing

```bash
# Run all tests (231 tests)
uv run pytest

# Run unit tests only
uv run pytest tests/unit/

# Run integration tests only
uv run pytest tests/integration/

# Run with coverage
uv run pytest --cov=src/plasmaagent --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_decomposer.py -v
```

**Test Coverage:**
- ✅ 231 tests passing
- ✅ Unit tests (models, services, CLI)
- ✅ Integration tests (end-to-end flows)
- ✅ Edge cases (SQL injection, shell injection, unicode, null bytes)
- ✅ Stress tests (concurrent execution, large inputs)
- ✅ Security tests (injection attempts, malicious input)

---

## 🔧 Configuration

### Environment Variables

```bash
# Database connection
export DATABASE_URL=postgresql://postgres:password@localhost:5432/plasmaagent

# Optional: Debug mode
export PLASMA_DEBUG=true
```

### Database Setup

```bash
# Create database
psql -U postgres -c "CREATE DATABASE plasmaagent;"

# Run migrations
uv run alembic upgrade head

# Check migration status
uv run alembic current
uv run alembic history
```

---

## 📊 Performance

| Metric | Value |
|--------|-------|
| Task Generation | < 3ms |
| Task Decomposition | < 100ms |
| Command Execution | ~30ms per step |
| Metrics Tracking | < 500ms |
| Template Analysis | < 2s (100 entries) |
| Test Suite | 231 tests in 13s |

---

## 🛡️ Security

PlasmaAgent implements defense-in-depth security:

- **SQL Injection Prevention** — Parameterized queries, input sanitization
- **Shell Injection Prevention** — Command validation, special character rejection
- **Input Validation** — Max length (10,000 chars), null byte rejection
- **Fail-Fast Validation** — Immediate error on invalid input (no hanging)
- **Non-Interactive Mode Protection** — Require explicit flags for automation
- **Audit Trail** — Full execution logs in PostgreSQL

---

## 🎨 Terminal UI

PlasmaAgent features a beautiful Rich-powered terminal UI with:

- **Plasma Theme** — Cosmic color palette (cyan, magenta, violet, gold)
- **ASCII Art Logo** — Colorized branding
- **Rich Panels** — Bordered output for task details
- **Colored Tables** — Syntax-highlighted task lists
- **Real-Time Streaming** — Live output during execution
- **Bracket Pair Colorization** — Enhanced readability

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`uv run pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

**Code Style:**
- No comments (code should be self-documenting)
- Type hints required for all functions
- Single blank line spacing (no double enters)
- Follow existing patterns in the codebase

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Rich** — Beautiful terminal UI library
- **psycopg3** — Modern PostgreSQL adapter for Python
- **Typer** — CLI framework built on type hints
- **Pydantic V2** — Data validation and settings management
- **pytest** — Testing framework
- **Alembic** — Database migration tool

---

## 📮 Contact

- **GitHub Issues** — Bug reports and feature requests
- **Discussions** — Questions and community support

---

## 🌟 Star History

If you find PlasmaAgent useful, please consider giving it a star on GitHub! ⭐

---

**Built with ❤️ for the AI agent community**
