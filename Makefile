.PHONY: install dev lint format test type-check migrate db-init clean

# Install production dependencies
install:
	uv sync

# Install development dependencies
dev:
	uv sync --dev

# Run linter
lint:
	uv run ruff check src/ tests/

# Format code
format:
	uv run ruff format src/ tests/

# Run tests
test:
	uv run pytest

# Run tests with coverage
test-cov:
	uv run pytest --cov=src/plasmaagent --cov-report=html

# Type checking
type-check:
	uv run mypy src/

# Database migrations
migrate:
	uv run alembic upgrade head

# Create new migration
migration:
	uv run alembic revision --autogenerate -m "$(msg)"

# Initialize database
db-init: migrate

# Install CLI globally
install-cli:
	uv pip install -e .

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete

# Run all checks
check: lint type-check test

# Development shell
shell:
	uv run python
