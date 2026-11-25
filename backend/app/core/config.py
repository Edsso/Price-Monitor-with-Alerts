"""Configurações da aplicação, lidas de variáveis de ambiente ou do arquivo `.env`."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    scraper_user_agent: str = DEFAULT_USER_AGENT
    scraper_timeout_seconds: float = Field(default=15.0, gt=0)
    scraper_max_attempts: int = Field(default=3, ge=1)
    scraper_backoff_seconds: float = Field(default=1.0, ge=0)
    scraper_min_interval_seconds: float = Field(default=2.0, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
