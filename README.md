# PlasmaAgent

Database-centric agentic execution framework powered by rule-based intelligence.

## Features

- **Task Execution Engine** - Shell commands with real-time output capture
- **Rule-Based Intelligence** - Natural language → task generation
- **Self-Improvement Loop** - Metrics tracking & template optimization
- **PostgreSQL Transactional State Machine** - Reliable task state transitions
- **Plasma Theme** - Rich CLI with cosmic color palette

## Quick Start

```bash
uv sync
uv run alembic upgrade head
uv run plasma --help
```

## CLI Commands

```bash
# Task management
plasma task create --name "Backup DB" --command "pg_dump ..."
plasma task generate --input "backup postgresql plasmaagent" --yes
plasma task run --id <task-id>
plasma task list
plasma task show --id <task-id> --steps --logs

# Metrics & analytics
plasma metrics show
plasma metrics analyze
plasma metrics optimize --dry-run

# Health check
plasma doctor
```

## Testing

```bash
uv run pytest -v           # All 214 tests
uv run pytest tests/unit   # Unit tests only
uv run pytest tests/integration  # Integration tests only
```

## Project Status

- **Current Phase:** 3.5 Advanced Reasoning
- **Tests:** 214/214 passing
- **Roadmap:** See [ROADMAP.md](ROADMAP.md)

## Architecture

```
src/plasmaagent/
├── ai/
│   ├── metrics/        # Template metrics tracker & optimizer
│   └── providers/      # LLM provider abstraction (rule-based active)
├── cli/                # Typer-based CLI commands
├── core/               # Database, config, state machine
├── executor/           # Shell command execution
├── models/             # Pydantic models
└── services/           # Business logic
```

## License

MIT
