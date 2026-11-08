from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "dev"  # header auth (X-Tenant-Id / X-User-Id) is refused unless this is "dev"
    DATABASE_URL: str = "sqlite+aiosqlite:///./aira.db"
    CORS_ORIGINS: str = "http://localhost:3000"
    COMPANION_MAX_CONCURRENT: int = 4

    LLM_PROVIDER: Literal["fake", "openai_compat"] = "fake"
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_API_KEY: str | None = None
    LLM_MODEL: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
