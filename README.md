# PlasmaAgent

Database-Centric Agentic Execution Framework

## Overview

PlasmaAgent is a production-grade execution framework that treats PostgreSQL as the central nervous system of an AI agent. Every action is an atomic transaction. Every state is persistent. Every failure is recoverable.

## Philosophy

- **Database-Centric Architecture**: PostgreSQL is not just storage—it's the engine
- **State Machine as Core**: All execution is governed by the PostgreSQL Transactional State Machine (PTSM)
- **Recovery-First Design**: Crash → restart → resume exactly where you left off
- **Full Observability**: Every action logged, every decision auditable

## Requirements

- Python 3.13.3+
- PostgreSQL 16+ with pgvector extension
- uv package manager

## Installation

```bash
# Clone repository
git clone <repository-url>
cd PlasmaAgent

# Install dependencies
make dev

# Initialize database
make db-init

# Install CLI
make install-cli
```

## Quick Start

```bash
# Check system health
plasma doctor

# Create a task
plasma task create --name "Deploy application" --description "Deploy to production"

# List tasks
plasma task list

# Run a task
plasma task run --id <task-uuid>

# Show task details
plasma task show --id <task-uuid>
```

## Development

```bash
# Run tests
make test

# Run linter
make lint

# Type checking
make type-check

# Format code
make format

# Run all checks
make check
```

## Architecture

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## Project Structure

```
PlasmaAgent/
├── src/plasmaagent/
│   ├── core/          # Infrastructure (config, database, state machine)
│   ├── models/        # Data models
│   ├── services/      # Business logic
│   ├── cli/           # Command-line interface
│   └── utils/         # Utilities
├── tests/             # Test suite
├── migrations/        # Database migrations
└── docs/              # Documentation
```

## Visual Identity

**Logo:** Plasma Sphere (energy plasma, not Hermes)

**Colors:**
- Electric Cyan (#00FFFF) — Primary actions
- Plasma Magenta (#FF00FF) — Errors/warnings
- Deep Violet (#8B00FF) — Information

## License

Proprietary - All rights reserved

## Status

**Phase 1: Foundational Core** — In Progress
