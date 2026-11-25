"""Configurações da aplicação, lidas de variáveis de ambiente ou do arquivo `.env`."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    cors_origins: list[str] = ["http://localhost:5173"]

    scraper_user_agent: str = DEFAULT_USER_AGENT
    scraper_timeout_seconds: float = Field(default=15.0, gt=0)
    scraper_max_attempts: int = Field(default=3, ge=1)
    scraper_backoff_seconds: float = Field(default=1.0, ge=0)
    scraper_min_interval_seconds: float = Field(default=2.0, ge=0)


class SupabaseSettings(BaseSettings):
    """Separada de `Settings` para o CLI funcionar sem credenciais do Supabase."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="SUPABASE_", extra="ignore"
    )

    url: str = Field(pattern=r"^https?://")
    publishable_key: str = Field(min_length=1)
    # Ignora RLS: uso exclusivo do job, nunca no front-end.
    secret_key: SecretStr = Field(min_length=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
