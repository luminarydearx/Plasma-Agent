"""Configuration management using pydantic-settings."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="PlasmaAgent", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Enable debug mode")

    # Database
    database_url: str = Field(
        default="postgresql+psycopg://postgres:090208@localhost:5432/plasmaagent",
        description="PostgreSQL connection URL",
    )
    database_pool_size: int = Field(default=10, description="Connection pool size")
    database_max_overflow: int = Field(
        default=20, description="Maximum overflow connections"
    )
    database_pool_timeout: int = Field(
        default=30, description="Pool timeout in seconds"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or console)")

    # Execution
    execution_timeout: int = Field(
        default=300, description="Default execution timeout in seconds"
    )
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    @property
    def is_debug(self) -> bool:
        """Check if debug mode is enabled."""
        return self.debug


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
