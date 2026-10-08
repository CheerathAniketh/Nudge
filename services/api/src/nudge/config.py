"""All configuration lives here. Nothing else reads os.environ."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# services/api/.env, independent of the directory you run from
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    env: str = "local"  # local | staging | production
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]

    supabase_url: str
    supabase_anon_key: SecretStr
    supabase_service_role_key: SecretStr

    @property
    def supabase_auth_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
