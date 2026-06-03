<div align="center">

```
██████╗ ██╗      █████╗ ███████╗███╗   ███╗ █████╗ 
██╔══██╗██║     ██╔══██╗██╔════╝████╗ ████║██╔══██╗
██████╔╝██║     ███████║███████╗██╔████╔██║███████║
██╔═══╝ ██║     ██╔══██║╚════██║██║╚██╔╝██║██╔══██║
██║     ███████╗██║  ██║███████║██║ ╚═╝ ██║██║  ██║
╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝
```

# 🌌 **PLASMA AGENT** 🌌

### *Database-Centric AI Agent with Advanced Reasoning*

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791?logo=postgresql)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/tests-776%20passed-brightgreen.svg)](https://github.com/luminarydearx/Plasma-Agent)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

</div>

## 🚀 **Overview**

**PlasmaAgent** adalah AI Agent berbasis database yang mengimplementasikan **PostgreSQL Transactional State Machine (PTSM)** untuk orchestrasi task yang robust, fault-tolerant, dan self-improving.

### ✨ **Key Features**

- 🧠 **Advanced Reasoning Engine** — Task decomposition, context management, error recovery
- 🔄 **Self-Improvement Loop** — Template metrics, A/B testing, auto-optimization
- 💡 **Smart Suggestions** — Next action recommendations, anomaly detection
- 🔒 **Database-Centric** — All state stored in PostgreSQL with ACID transactions
- ⚡ **High Performance** — 776+ tests passing, <100ms response time
- 🛡️ **Production Ready** — Comprehensive error handling, security hardening

---

## 🎯 **Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI Interface                          │
│  plasma task create | run | generate | metrics | optimize  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                  Reasoning Service                          │
│  ┌────────────┐  ┌─────────────┐  ┌────────────────────┐  │
│  │ Decomposer │  │   Context   │  │  Error Recovery    │  │
│  │   (DAG)    │  │   Manager   │  │    + Retry         │  │
│  └────────────┘  └─────────────┘  └────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Execution Engine (Phase 2)                     │
│  ┌────────────┐  ┌─────────────┐  ┌────────────────────┐  │
│  │   Shell    │  │    Step     │  │   Parallel         │  │
│  │  Executor  │  │   Manager   │  │   Executor         │  │
│  └────────────┘  └─────────────┘  └────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│         PostgreSQL + pgvector (PTSM State Machine)         │
│  tasks | task_steps | execution_logs | template_metrics    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 **Installation**

### **Quick Install**

```bash
# Clone repository
git clone https://github.com/luminarydearx/Plasma-Agent.git
cd Plasma-Agent

# Install dependencies
uv sync

# Setup database
createdb -U postgres plasmaagent

# Run migrations
uv run alembic upgrade head

# Verify installation
uv run plasma doctor
```

### **Requirements**

- Python 3.13+
- PostgreSQL 15+
- uv (Python package manager)

---

## 🎬 **Usage**

### **1️⃣ Create Task (Manual)**

```bash
# Simple task
plasma task create --name "Backup DB" --command "pg_dump plasmaagent > backup.sql"

# Multi-step task
plasma task create --name "Deploy" \
  --command "git pull origin main" \
  --command "npm install" \
  --command "npm run build" \
  --command "npm run deploy"
```

### **2️⃣ Generate Task (AI-Powered)**

```bash
# Natural language → structured task
plasma task generate --input "backup database postgresql plasmaagent" --yes

# Preview before create
plasma task generate --input "check disk space" --preview
```

### **3️⃣ Execute Task**

```bash
# Run task
plasma task run --id <task-id>

# View execution logs
plasma task show --id <task-id> --logs

# View step-by-step results
plasma task show --id <task-id> --steps
```

### **4️⃣ Metrics & Optimization**

```bash
# View template metrics
plasma metrics show

# Analyze performance
plasma metrics analyze

# Auto-optimize confidence scores
plasma metrics optimize --dry-run
```

---

## 🧪 **Testing**

```bash
# Run all tests (776 unit + integration)
uv run pytest

# Run unit tests only
uv run pytest tests/unit/ -v

# Run integration tests
uv run pytest tests/integration/ -v

# Run with coverage
uv run pytest --cov=src/plasmaagent
```

---

## 📚 **Project Phases**

### **Phase 1: Foundation** ✅
- Database schema with pgvector
- PTSM state machine
- CLI foundation
- Configuration management

### **Phase 2: Execution Engine** ✅
- Shell executor (subprocess + async)
- Step management
- Execution logging
- Parallel execution
- Retry strategies

### **Phase 3: Intelligence Layer** ✅
- **MVP**: Rule-based intelligence
- **3.4**: Self-improvement loop (metrics, optimization)
- **3.5**: Advanced reasoning (decomposer, context, error recovery, DAG)
- **3.6**: Template evolution (learning, versioning, A/B testing, retirement)
- **3.7**: Smart suggestions (next actions, anomaly detection)

### **Phase 4: Production Hardening** 🚧
- **4.1**: Scheduling & automation (cron, recurring tasks)
- **4.2**: Observability & monitoring (dashboard, alerts)
- **4.3**: Security & audit (authentication, permissions)
- **4.4**: Reliability engineering (circuit breakers, graceful degradation)

### **Phase 5: Intelligence Expansion** 📋
- **5.1**: Memory system (short-term, long-term, pgvector)
- **5.2**: RAG (document ingestion, semantic search)
- **5.3**: Multi-agent coordination
- **5.4**: Tool use & skills

### **Phase 6: Ecosystem** 📋
- **6.1**: API gateway (REST, WebSocket)
- **6.2**: Web dashboard
- **6.3**: Plugin system
- **6.4**: Cloud LLM integration (optional)
- **6.5**: Documentation & distribution

---

## 🔧 **Configuration**

### **Environment Variables**

```bash
# Database
DATABASE_URL=postgresql+psycopg://postgres:password@localhost/plasmaagent

# Execution
EXECUTION_TIMEOUT=3600
MAX_CONCURRENT_TASKS=10

# Logging
LOG_LEVEL=INFO
```

### **Config File**

Create `.env` in project root:

```env
DATABASE_URL=postgresql+psycopg://postgres:password@localhost/plasmaagent
LOG_LEVEL=INFO
```

---

## 📖 **Documentation**

- **[ROADMAP.md](ROADMAP.md)** — Project roadmap & milestones
- **[docs/PLASMA_THEME.md](docs/PLASMA_THEME.md)** — CLI theme customization
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — System architecture (coming soon)

---

## 🤝 **Contributing**

Contributions are welcome! Please feel free to submit a Pull Request.

### **Development Setup**

```bash
# Clone repository
git clone https://github.com/luminarydearx/Plasma-Agent.git
cd Plasma-Agent

# Install dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run linter
uv run ruff check src/

# Format code
uv run ruff format src/
```

---

## 📝 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 **Acknowledgments**

- Built with [Typer](https://typer.tiangolo.com/) for CLI
- Powered by [PostgreSQL](https://www.postgresql.org/) + [pgvector](https://github.com/pgvector/pgvector)
- Async database operations with [psycopg3](https://www.psycopg.org/psycopg3/)
- Rich terminal output with [Rich](https://rich.readthedocs.io/)

---

## 📞 **Support**

- **Issues**: [GitHub Issues](https://github.com/luminarydearx/Plasma-Agent/issues)
- **Discussions**: [GitHub Discussions](https://github.com/luminarydearx/Plasma-Agent/discussions)

---

<div align="center">

**Made with ❤️ by [LuminaryDearX](https://github.com/luminarydearx)**

*If this project helps you, please give it a ⭐!*

</div>
