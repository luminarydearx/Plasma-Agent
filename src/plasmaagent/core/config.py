from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="PlasmaAgent")
    app_version: str = Field(default="0.2.0")
    debug: bool = Field(default=False)

    database_path: str = Field(
        default=str(Path.home() / ".plasmaagent" / "plasma.db")
    )
    vector_store_path: str = Field(
        default=str(Path.home() / ".plasmaagent" / "vectors")
    )
    embedding_model: str = Field(default="all-MiniLM-L6-v2")

    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    execution_timeout: int = Field(default=300)
    max_retries: int = Field(default=3)

    @property
    def is_debug(self) -> bool:
        return self.debug


@lru_cache
def get_settings() -> Settings:
    return Settings()
