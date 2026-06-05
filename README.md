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

### *Database-Centric AI Agent with Security Auditing, VaultSync Backup & Advanced Reasoning*

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite)](https://www.sqlite.org/)
[![Tests](https://img.shields.io/badge/tests-1516%20passed-brightgreen.svg)](https://github.com/luminarydearx/Plasma-Agent)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

</div>

## 🚀 **Overview**

**PlasmaAgent** adalah AI Agent berbasis database yang mengimplementasikan **Transactional State Machine** untuk orchestrasi task yang robust, fault-tolerant, dan self-improving. Dengan **Interactive Chat Mode**, **Security Auditing**, dan **VaultSync Disaster Recovery**, PlasmaAgent dapat mengakses komputer Anda secara langsung untuk menjalankan perintah, membuat file, membuka aplikasi, menyimpan informasi ke long-term memory, melakukan audit keamanan, dan **melindungi data Anda dari ransomware & disaster**.

### ✨ **Key Features**

- 🧠 **Advanced Reasoning Engine** — Task decomposition, context management, error recovery
- 🔄 **Self-Improvement Loop** — Template metrics, A/B testing, auto-optimization
- 💡 **Smart Suggestions** — Next action recommendations, anomaly detection
- 🔒 **Database-Centric** — All state stored in SQLite with ACID transactions (zero-configuration)
- 🛡️ **Security Auditing** — Comprehensive vulnerability detection (SQL injection, XSS, path traversal, hardcoded secrets, command injection, insecure crypto, debug mode)
- 🔐 **VaultSync** — Zero-knowledge backup & disaster recovery with AES-256-GCM encryption
- ⚡ **High Performance** — 1516+ tests passing, <100ms response time
- 🛡️ **Production Ready** — Comprehensive error handling, security hardening
- 💬 **Interactive Chat Mode** — Natural language interface dengan **32 tools** (file ops, shell execution, app launcher, cron scheduler, memory, security audit, backup & recovery)

---

## 🎯 **Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI Interface                          │
│  plasma task create | run | generate | metrics | optimize  │
│  plasma file create | read | write | list | delete | info  │
│  plasma monitor dashboard | metrics | top-templates        │
│  plasma (interactive chat mode)                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Agent Orchestrator (Chat Mode)                 │
│  ┌────────────┐  ┌─────────────┐  ┌────────────────────┐  │
│  │   Ollama   │  │   Tool      │  │   Memory           │  │
│  │   Client   │  │   Registry  │  │   Integration      │  │
│  └────────────┘  └─────────────┘  └────────────────────┘  │
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
│         SQLite + SQLAlchemy (State Machine)                │
│  tasks | task_steps | execution_logs | template_metrics    │
│  memories | conversation_sessions | task_patterns          │
│  vaultsync_backups | security_events                       │
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

# Verify installation (database auto-created)
uv run plasma doctor
