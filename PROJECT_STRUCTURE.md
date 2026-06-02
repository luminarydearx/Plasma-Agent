# PROJECT_STRUCTURE.md — PlasmaAgent

## Directory Tree

```
PlasmaAgent/
├── .git/                          # Git repository
├── .gitignore                     # Git ignore rules
├── alembic.ini                    # Alembic configuration
├── Makefile                       # Common commands
├── pyproject.toml                 # Project metadata & dependencies
├── README.md                      # Project overview
│
├── migrations/                    # Database migrations
│   ├── env.py                     # Alembic environment
│   ├── script.py.mako             # Migration template
│   └── versions/                  # Migration files
│       └── 001_initial_schema.py  # Initial schema with pgvector
│
├── src/                           # Source code
│   └── plasmaagent/               # Main package
│       ├── __init__.py            # Package init
│       ├── __version__.py         # Version string
│       │
│       ├── core/                  # Core infrastructure
│       │   ├── __init__.py
│       │   ├── config.py          # Configuration (pydantic-settings)
│       │   ├── database.py        # Database connection (psycopg3)
│       │   ├── exceptions.py      # Custom exceptions
│       │   └── state_machine.py   # PTSM implementation
│       │
│       ├── models/                # Data models
│       │   ├── __init__.py
│       │   ├── task.py            # Task model
│       │   ├── task_step.py       # TaskStep model
│       │   ├── execution_log.py   # ExecutionLog model
│       │   └── telemetry.py       # Telemetry model
│       │
│       ├── services/              # Business logic
│       │   ├── __init__.py
│       │   ├── task_service.py    # Task CRUD & lifecycle
│       │   ├── step_service.py    # Step management
│       │   └── log_service.py     # Log management
│       │
│       ├── cli/                   # Command-line interface
│       │   ├── __init__.py
│       │   ├── main.py            # Main typer app
│       │   ├── theme.py           # PlasmaAgent theme (colors)
│       │   ├── logo.py            # ASCII plasma sphere logo
│       │   ├── tasks.py           # Task commands
│       │   └── doctor.py          # Health check command
│       │
│       └── utils/                 # Utilities
│           ├── __init__.py
│           ├── logging.py         # Structlog configuration
│           └── validation.py      # Input validation helpers
│
├── tests/                         # Test suite
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   │
│   ├── unit/                      # Unit tests
│   │   ├── __init__.py
│   │   ├── test_config.py
│   │   ├── test_database.py
│   │   ├── test_state_machine.py
│   │   └── test_models.py
│   │
│   └── integration/               # Integration tests
│       ├── __init__.py
│       ├── test_lifecycle.py
│       ├── test_state_transitions.py
│       ├── test_crash_recovery.py
│       └── test_pgvector.py
│
└── docs/                          # Documentation
    ├── ARCHITECTURE.md            # Architecture overview
    ├── API.md                     # Internal API reference
    ├── CLI.md                     # CLI usage guide
    └── DEVELOPMENT.md             # Development guide
```

---

## Module Ownership & Responsibilities

### core/
**Owner:** System Architect  
**Responsibility:** Infrastructure, database, configuration, state machine  
**Dependencies:** None (leaf module)  
**Dependents:** models, services, cli

### models/
**Owner:** Backend Engineer  
**Responsibility:** Data models, Pydantic schemas, type definitions  
**Dependencies:** core  
**Dependents:** services, cli

### services/
**Owner:** Backend Engineer  
**Responsibility:** Business logic, CRUD operations, workflow orchestration  
**Dependencies:** core, models  
**Dependents:** cli

### cli/
**Owner:** Backend Engineer  
**Responsibility:** User interface, command parsing, output formatting  
**Dependencies:** core, models, services  
**Dependents:** None (entry point)

### utils/
**Owner:** Backend Engineer  
**Responsibility:** Shared utilities, helpers, logging  
**Dependencies:** core  
**Dependents:** All modules

---

## Dependency Flow

```
cli/
  ├─> services/
  │     ├─> models/
  │     │     └─> core/
  │     └─> core/
  ├─> models/
  └─> core/

utils/
  └─> core/
```

**Rule:** No circular dependencies. `core/` never imports from other modules.

---

## Naming Conventions

### Files
- **Modules:** `snake_case.py` (e.g., `state_machine.py`)
- **Tests:** `test_<module>.py` (e.g., `test_database.py`)
- **Migrations:** `NNN_<description>.py` (e.g., `001_initial_schema.py`)

### Classes
- **Models:** PascalCase (e.g., `Task`, `TaskStep`)
- **Services:** PascalCase + Service suffix (e.g., `TaskService`)
- **Exceptions:** PascalCase + Error/Exception suffix (e.g., `InvalidStateTransitionError`)

### Functions
- **Public:** `snake_case` (e.g., `get_connection`)
- **Private:** `_snake_case` (e.g., `_validate_transition`)
- **Async:** Prefix with `async` or use `async def` (e.g., `async def fetch_task`)

### Constants
- **UPPER_SNAKE_CASE** (e.g., `MAX_RETRIES`, `DEFAULT_TIMEOUT`)

---

## Database Schema (Phase 1)

### tasks
| Column | Type | Description |
|---|---|---|
| id | UUID | Primary key, auto-generated |
| name | VARCHAR(255) | Task name (required) |
| description | TEXT | Task description (optional) |
| status | VARCHAR(50) | Current status (PENDING, RUNNING, etc.) |
| created_at | TIMESTAMPTZ | Creation timestamp |
| updated_at | TIMESTAMPTZ | Last update timestamp |

### task_steps
| Column | Type | Description |
|---|---|---|
| id | UUID | Primary key, auto-generated |
| task_id | UUID | Foreign key to tasks |
| step_order | INTEGER | Execution order |
| command | TEXT | Shell command to execute |
| status | VARCHAR(50) | Step status |
| output | TEXT | Captured output |
| started_at | TIMESTAMPTZ | Execution start time |
| finished_at | TIMESTAMPTZ | Execution end time |

### execution_logs
| Column | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| task_id | UUID | Foreign key to tasks |
| step_id | UUID | Foreign key to task_steps (optional) |
| log_level | VARCHAR(20) | DEBUG, INFO, WARNING, ERROR |
| message | TEXT | Log message |
| timestamp | TIMESTAMPTZ | Log timestamp |

### telemetry
| Column | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| event_type | VARCHAR(100) | Event category |
| payload | JSONB | Event data |
| timestamp | TIMESTAMPTZ | Event timestamp |

---

## Visual Identity

### Logo: Plasma Sphere
```
        ╭─────────╮
       ╱  ◉     ◉  ╲
      │    ╲   ╱    │
      │     ◉      │
      │    ╱   ╲    │
       ╲  ◉     ◉  ╱
        ╰─────────╯
```

**Concept:** Spherical plasma core with energy lines radiating outward  
**Meaning:** Represents contained energy, power, and transformation

### Color Palette
| Name | Hex | Usage |
|---|---|---|
| Electric Cyan | #00FFFF | Primary actions, success messages |
| Plasma Magenta | #FF00FF | Errors, warnings, critical alerts |
| Deep Violet | #8B00FF | Information, headers, secondary text |
| Plasma Core | #FFFFFF | Highlights, emphasis |
| Dark Matter | #1A1A2E | Backgrounds (if needed) |

### CLI Branding
```
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   ██████╗ ██╗      █████╗ ███████╗███╗   ███╗ █████╗     ║
║   ██╔══██╗██║     ██╔══██╗██╔════╝████╗ ████║██╔══██╗    ║
║   ██████╔╝██║     ███████║███████╗██╔████╔██║███████║    ║
║   ██╔═══╝ ██║     ██╔══██║╚════██║██║╚██╔╝██║██╔══██║    ║
║   ██║     ███████╗██║  ██║███████║██║ ╚═╝ ██║██║  ██║    ║
║   ╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝    ║
║                                                           ║
║              ╭─────╮  PLASMAAGENT  ╭─────╮               ║
║              │ ◉◉◉ │   v0.1.0      │ ◉◉◉ │               ║
║              ╰─────╯               ╰─────╯               ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
```

---

## Configuration

### Environment Variables
| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://postgres:090208@localhost:5432/plasmaagent` | PostgreSQL connection string |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `APP_NAME` | `PlasmaAgent` | Application name for logging |

### Configuration File (Future)
```toml
# plasmaagent.toml (planned for Phase 2)
[database]
url = "postgresql+psycopg://postgres:090208@localhost:5432/plasmaagent"
pool_size = 10
max_overflow = 20

[logging]
level = "INFO"
format = "json"

[execution]
timeout = 300
max_retries = 3
```

---

## Development Workflow

### Setup
```bash
# Install dependencies
uv sync

# Initialize database
make db-init

# Run migrations
make migrate

# Install CLI
make install
```

### Common Commands
```bash
# Run tests
make test

# Run linter
make lint

# Run type checker
make type-check

# Format code
make format

# Start development shell
make shell
```

### CLI Usage
```bash
# Show help
plasma --help

# Check system health
plasma doctor

# Create a task
plasma task create --name "Deploy app" --description "Deploy to production"

# List tasks
plasma task list

# Run a task
plasma task run --id <uuid>

# Show task details
plasma task show --id <uuid>
```

---

## Security Considerations

### Database
- Use connection pooling with proper timeouts
- Never expose database credentials in logs
- Use parameterized queries (psycopg3 default)

### CLI
- Validate all user input
- Sanitize command strings before execution
- Never log sensitive data (passwords, tokens)

### Logging
- Structure logs with structlog
- Include request IDs for tracing
- Rotate logs to prevent disk overflow

---

## Performance Targets

### Phase 1
- CLI startup time: <500ms
- Database query time: <100ms (simple queries)
- Test suite execution: <30 seconds
- Code coverage: >90%

### Phase 2 (Future)
- Task execution overhead: <100ms
- Log write throughput: >1000 logs/second
- Concurrent task support: 10+ tasks

---

## Future Expansion Points

### Phase 2: Execution Engine
- `src/plasmaagent/executors/` — Shell, Python, HTTP executors
- `src/plasmaagent/streaming/` — Real-time output streaming

### Phase 3: AI Integration
- `src/plasmaagent/ai/` — LLM providers, embeddings
- `src/plasmaagent/context/` — Context manager, pgvector search

### Phase 4: Advanced Features
- `src/plasmaagent/planning/` — Task decomposition
- `src/plasmaagent/learning/` — Pattern recognition
- `src/plasmaagent/api/` — REST API (if needed)
