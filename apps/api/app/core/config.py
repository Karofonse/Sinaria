from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    """Configuración cargada desde variables de entorno (ver .env.example).

    Ningún secreto tiene valor útil en producción: `_check_production` rechaza el arranque.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "sandbox", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://sonaria:sonaria_dev@127.0.0.1:5432/sonaria_dev"
    redis_url: str = "redis://127.0.0.1:6379/0"
    queue_name: str = "sonaria:jobs"

    jwt_secret: str = _INSECURE_DEFAULT_SECRET
    jwt_ttl_minutes: int = 15
    session_cookie_name: str = "sonaria_session"
    cookie_secure: bool = False

    cors_origins: str = "http://localhost:3000"

    storage_backend: Literal["local", "s3"] = "local"
    storage_local_dir: str = "./.data/storage"
    download_url_secret: str = _INSECURE_DEFAULT_SECRET
    download_url_ttl_s: int = 300

    default_provider: str = "mock"
    fal_enabled: bool = False
    fal_api_key: str | None = None
    stability_enabled: bool = False
    stability_api_key: str | None = None

    payments_enabled: bool = False

    max_prompt_chars: int = 2000
    daily_global_credit_budget: int = 100_000
    user_daily_credit_limit: int = 1_000

    job_max_attempts: int = 3
    job_stuck_after_s: int = 600
    provider_poll_interval_s: float = 1.0
    provider_timeout_s: float = 300.0

    rate_limit_enabled: bool = True
    rate_limit_auth_per_minute: int = 20
    rate_limit_generation_per_minute: int = 10

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        if self.app_env == "production":
            problems = []
            if self.debug:
                problems.append("DEBUG debe ser false")
            if "*" in self.cors_origin_list:
                problems.append("CORS_ORIGINS no puede contener '*'")
            if self.jwt_secret == _INSECURE_DEFAULT_SECRET or len(self.jwt_secret) < 32:
                problems.append("JWT_SECRET debe tener al menos 32 caracteres y no ser el valor por defecto")
            if self.download_url_secret == _INSECURE_DEFAULT_SECRET or len(self.download_url_secret) < 32:
                problems.append("DOWNLOAD_URL_SECRET debe tener al menos 32 caracteres")
            if not self.cookie_secure:
                problems.append("COOKIE_SECURE debe ser true")
            if problems:
                raise ValueError("Configuración insegura para producción: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
