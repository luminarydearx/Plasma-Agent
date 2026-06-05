<div align="center">

```
██████╗ ██╗      █████╗ ███████╗███╗   ███╗ █████╗ 
██╔══██╗██║     ██╔══██╗██╔════╝████╗ ████║██╔══██╗
██████╔╝██║     ███████║███████╗██╔████╔██║███████║
██╔═══╝ ██║     ██╔══██║╚════██║██║╚██╔╝██║██╔══██╗
██║     ███████╗██║  ██║███████║██║ ╚═╝ ██║██║  ██║
╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝
```

# 🌌 **PLASMA AGENT** 🌌

### *Database-Centric AI Agent with Security Auditing, VaultSync Backup & Advanced Reasoning*

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite)](https://www.sqlite.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://www.sqlalchemy.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

</div>

## 🚀 **Overview**

**PlasmaAgent** adalah **local-first AI Agent framework** yang berjalan sepenuhnya di komputer Anda tanpa依赖 pada cloud services. Dibangun dengan **SQLite + SQLAlchemy** untuk zero-configuration deployment, **AES-256-GCM encryption** untuk data protection, dan **32 modular tools** yang memungkinkan AI untuk berinteraksi dengan sistem Anda secara aman.

### ✨ **Core Features**

| Feature | Description |
|---------|-------------|
| 🧠 **Advanced Reasoning** | Task decomposition, context management, error recovery |
| 🔄 **Self-Improvement** | Template metrics, pattern learning, auto-optimization |
| 🔒 **Zero-Configuration** | SQLite database, no PostgreSQL required |
| 🛡️ **Security Auditing** | SQL injection, XSS, path traversal, hardcoded secrets detection |
| 🔐 **VaultSync** | Zero-knowledge backup with AES-256-GCM encryption |
| 💬 **Interactive Chat** | Natural language interface with 32 tools |
| 📊 **Monitoring** | Real-time metrics, failure patterns, performance analytics |
| 🌐 **Cross-Platform** | Windows, Linux, macOS support |

---

## 🏗️ **Architecture**

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Interface                           │
│  plasma chat | task | monitor | alerts | memory | file | doctor │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                   Agent Orchestrator                            │
│  ┌────────────┐  ┌─────────────┐  ┌────────────────────────┐  │
│  │   Ollama   │  │   Tool      │  │   Permission           │  │
│  │   Client   │  │   Registry  │  │   Manager              │  │
│  └────────────┘  └─────────────┘  └────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    Modular Tools (32)                           │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │file_ops │ │  shell  │ │  web    │ │ system  │ │ security│ │
│  │  (7)    │ │  (2)    │ │  (4)    │ │  (5)    │ │  (1)    │ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │scheduling│ │ memory  │ │clipboard│ │  media  │ │  vault  │ │
│  │  (2)    │ │  (2)    │ │  (2)    │ │  (1)    │ │  (5)    │ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│           SQLite + SQLAlchemy (State Machine)                   │
│  tasks | task_steps | execution_logs | memories | permissions  │
│  alert_rules | alert_events | template_metrics | audit_logs    │
│  template_retirements | template_versions | schedules          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 **Installation**

### **Prerequisites**

- Python 3.13+
- [Ollama](https://ollama.com/) for local LLM inference
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### **Quick Start**

```bash
# Clone repository
git clone https://github.com/luminarydearx/Plasma-Agent.git
cd Plasma-Agent

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .

# Verify installation
uv run plasma doctor

# Start interactive chat
uv run plasma
```

### **Ollama Setup**

```bash
# Install Ollama (if not installed)
# Visit https://ollama.com/download

# Pull a model
ollama pull qwen2.5-coder:7b-instruct-q4_K_M

# Or use any model you prefer
ollama pull llama3.2
ollama pull mistral
```

---

## 🛠️ **32 Tools Available**

### **File Operations** (7 tools)
| Tool | Description | Permission |
|------|-------------|------------|
| `create_file` | Create new file with content | 🔒 Required |
| `read_file` | Read file content | 🔓 Open |
| `write_file` | Write/append to file | 🔒 Required |
| `list_directory` | List files in directory | 🔓 Open |
| `delete_file` | Delete file or directory | 🔒 Required |
| `file_info` | Get file metadata | 🔓 Open |
| `find_file` | Search files by pattern | 🔓 Open |

### **System Operations** (5 tools)
| Tool | Description | Permission |
|------|-------------|------------|
| `system_info` | Get OS, Python, hostname | 🔓 Open |
| `system_stats` | CPU, memory, disk usage | 🔓 Open |
| `current_time` | Current date/time | 🔓 Open |
| `process_list` | List running processes | 🔓 Open |
| `kill_process` | Terminate process | 🔒 Required |

### **Shell & Execution** (2 tools)
| Tool | Description | Permission |
|------|-------------|------------|
| `execute_shell` | Run shell commands | 🔒 Required |
| `open_app` | Launch applications | 🔒 Required |

### **Web & Search** (4 tools)
| Tool | Description | Permission |
|------|-------------|------------|
| `web_search` | DuckDuckGo search | 🔓 Open |
| `web_scrape` | Extract web content | 🔓 Open |
| `youtube_search` | YouTube video search | 🔓 Open |
| `download_file` | Download from URL | 🔒 Required |

### **Scheduling** (2 tools)
| Tool | Description | Permission |
|------|-------------|------------|
| `cron_schedule` | Recurring cron jobs | 🔒 Required |
| `schedule_once` | One-time scheduled task | 🔒 Required |

### **Memory** (2 tools)
| Tool | Description | Permission |
|------|-------------|------------|
| `store_memory` | Save to long-term memory | 🔓 Open |
| `search_memory` | Semantic memory search | 🔓 Open |

### **Security** (1 tool)
| Tool | Description | Permission |
|------|-------------|------------|
| `security_audit` | Comprehensive vulnerability scanner | 🔓 Open |

### **VaultSync Backup** (5 tools)
| Tool | Description | Permission |
|------|-------------|------------|
| `vault_backup` | Encrypted backup creation | 🔒 Required |
| `vault_restore` | Restore from backup | 🔒 Required |
| `vault_list_backups` | List all backups | 🔓 Open |
| `vault_delete_backup` | Delete backup | 🔒 Required |
| `vault_generate_recovery_key` | Generate encryption key | 🔓 Open |

### **Utilities** (4 tools)
| Tool | Description | Permission |
|------|-------------|------------|
| `clipboard_get` | Read clipboard | 🔓 Open |
| `clipboard_set` | Write to clipboard | 🔓 Open |
| `screenshot` | Capture screen | 🔒 Required |
| `send_notification` | Desktop notification | 🔒 Required |

---

## 🛡️ **Security Audit**

PlasmaAgent includes a comprehensive security auditor that detects 7 vulnerability categories:

### **Vulnerability Detection**

| Category | Severity | Examples |
|----------|----------|----------|
| SQL Injection | 🔴 CRITICAL | String formatting in queries, f-strings in SQL |
| Command Injection | 🔴 CRITICAL | `eval()`, `exec()`, `os.system()` with user input |
| Hardcoded Secrets | 🔴 CRITICAL | Passwords, API keys, tokens in code |
| Path Traversal | 🟠 HIGH | Unsafe file paths from user input |
| XSS | 🟠 HIGH | `.innerHTML`, `document.write()`, `v-html` |
| Insecure Crypto | 🟡 MEDIUM | MD5, SHA1, DES, RC4 usage |
| Debug Mode | 🟡 MEDIUM | `DEBUG = True`, print statements |

### **Usage**

```bash
# Via interactive chat
plasma
> Lakukan security audit pada project C:\Projects\myapp

# Results include:
# - Security score (0-100)
# - Vulnerability count by severity
# - File path and line number for each finding
# - Remediation recommendations
```

### **Supported Languages**

- Python (.py)
- JavaScript/TypeScript (.js, .ts, .jsx, .tsx)
- Go (.go)
- Rust (.rs)
- PHP (.php)
- Ruby (.rb)

---

## 🔐 **VaultSync - Zero-Knowledge Backup**

VaultSync protects your data from ransomware, malware, accidental deletion, and hardware failure.

### **Security Model**

```
┌─────────────────────────────────────────┐
│         Zero-Knowledge Architecture     │
├─────────────────────────────────────────┤
│                                         │
│  Developer:     ❌ No access            │
│  Cloud Provider:❌ No access            │
│  Third Party:   ❌ No access            │
│  User:          ✅ Full access          │
│                                         │
│  Encryption keys never leave device     │
│  Backups encrypted before upload        │
│  Recovery key: user-owned only          │
│                                         │
└─────────────────────────────────────────┘
```

### **Encryption Details**

| Component | Algorithm | Details |
|-----------|-----------|---------|
| Data Encryption | AES-256-GCM | Authenticated encryption |
| Key Derivation | PBKDF2-HMAC-SHA256 | 480,000 iterations |
| Integrity Check | SHA-256 | File hash verification |
| Recovery Key | 128-bit random | Format: XXXX-XXXX-XXXX-XXXX |

### **Threat Detection**

VaultSync monitors for ransomware behavior:
- Mass file modifications (>100 files/minute)
- Suspicious extension changes (.encrypted, .locked)
- Rapid file deletion events
- Unknown processes accessing sensitive folders

**Emergency Response:**
1. Create instant snapshot
2. Preserve file metadata
3. Generate security report
4. Alert user

### **Usage**

```bash
# Create encrypted backup
plasma
> Backup folder C:\Projects\MyApp dengan enkripsi
# Returns: Recovery key - SAVE THIS!

# List backups
> List semua backup yang ada

# Restore backup
> Restore backup [backup_id] ke C:\Restore
```

---

## 📊 **Monitoring & Analytics**

### **CLI Commands**

```bash
# View execution metrics (last 24 hours)
uv run plasma monitor metrics

# View top performing templates
uv run plasma monitor top-templates

# View failure patterns
uv run plasma monitor failures

# Real-time dashboard (coming soon)
uv run plasma monitor dashboard
```

### **Metrics Tracked**

- Total executions, success/failure rates
- Average execution time (P50, P95, P99)
- Throughput (tasks/minute)
- Template usage statistics
- Error patterns and frequencies

---

## 🔧 **Configuration**

### **Environment Variables**

```bash
# Ollama configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b-instruct-q4_K_M

# Database configuration
PLASMA_DB_PATH=~/.plasmaagent/plasma.db

# Vector store (for RAG)
PLASMA_VECTOR_PATH=~/.plasmaagent/vectordb
```

### **Config File**

Location: `~/.plasmaagent/config.yaml`

```yaml
ollama:
  base_url: http://localhost:11434
  default_model: qwen2.5-coder:7b-instruct-q4_K_M

database:
  path: ~/.plasmaagent/plasma.db

security:
  audit_extensions: [.py, .js, .ts, .go, .rs, .php, .rb]
  max_file_size_mb: 10

vaultsync:
  backup_location: ~/.plasmaagent/backups
  compression: true
  encryption: true
```

---

## 🧪 **Testing**

```bash
# Run all tests
uv run pytest

# Run specific test module
uv run pytest tests/unit/test_tools.py

# Run with coverage
uv run pytest --cov=plasmaagent

# Test CLI commands
uv run plasma doctor
uv run plasma hello
uv run plasma monitor metrics
uv run plasma task list
```

---

## 📁 **Project Structure**

```
PlasmaAgent/
├── src/plasmaagent/
│   ├── agent/              # Agent orchestration
│   │   ├── orchestrator.py
│   │   ├── repl.py
│   │   ├── tools.py        # Tool registry
│   │   └── permission_manager.py
│   ├── tools/              # Modular tool implementations
│   │   ├── file_ops.py     # 7 file tools
│   │   ├── shell.py        # 2 shell tools
│   │   ├── web.py          # 4 web tools
│   │   ├── system.py       # 5 system tools
│   │   ├── security.py     # Security audit
│   │   ├── vault.py        # 5 VaultSync tools
│   │   └── ...
│   ├── core/               # Core infrastructure
│   │   ├── database.py     # SQLAlchemy async
│   │   ├── schema.py       # Database models
│   │   └── config.py
│   ├── security/           # Security features
│   │   ├── audit_tool.py   # Vulnerability scanner
│   │   └── sanitizer.py    # Input sanitization
│   ├── vaultsync/          # Backup & recovery
│   │   ├── encryption_engine.py
│   │   ├── backup_engine.py
│   │   ├── recovery_engine.py
│   │   └── threat_monitor.py
│   ├── observability/      # Monitoring
│   │   ├── metrics_service.py
│   │   └── alert_service.py
│   └── cli/                # CLI commands
│       ├── main.py
│       ├── monitor.py
│       └── tasks.py
├── tests/                  # Test suite
├── FASE.md                 # Development phases
└── README.md
```

---

## 🌐 **Cross-Platform Support**

| Platform | Status | Notes |
|----------|--------|-------|
| Windows | ✅ Full | PowerShell/cmd support |
| Linux | ✅ Full | Bash support |
| macOS | ✅ Full | zsh/bash support |
| Android | ⏳ Planned | Future release |

---

## 🤝 **Contributing**

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📄 **License**

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 **Acknowledgments**

- [Ollama](https://ollama.com/) - Local LLM inference
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM
- [Rich](https://rich.readthedocs.io/) - Terminal UI
- [Cryptography](https://cryptography.io/) - Encryption

---

<div align="center">

**Built with ❤️ for the local-first AI movement**

*Your data, your computer, your AI.*

</div>
