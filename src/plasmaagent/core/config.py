from functools import lru_cache

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
    app_version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)

    database_url: str = Field(
        default="postgresql+psycopg://postgres:090208@localhost:5432/plasmaagent"
    )
    database_pool_size: int = Field(default=10)
    database_max_overflow: int = Field(default=20)
    database_pool_timeout: int = Field(default=30)

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
