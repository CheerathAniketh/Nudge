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

    # --- LLM (provider-agnostic, see integrations/llm/client.py) ---
    llm_provider: str = "anthropic"  # openai | anthropic | google | xai | groq | sarvam | custom
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None  # only for "custom", or to override a preset
    llm_model_standard: str | None = None
    llm_model_cheap: str | None = None  # falls back to standard
    llm_model_reasoning: str | None = None  # falls back to standard
    llm_daily_token_budget: int = 2_000_000
    llm_timeout_s: float = 60.0

    @property
    def supabase_auth_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
