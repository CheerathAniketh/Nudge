"""The only entry point agents use to call an LLM.

Switching provider = edit LLM_PROVIDER / LLM_API_KEY / LLM_MODEL_* in services/api/.env.
Nothing else in the codebase knows which provider is active.
"""

import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

from nudge.config import Settings
from nudge.errors import BudgetExceededError, ConfigError
from nudge.integrations.llm.adapters import AnthropicAdapter, LLMAdapter, OpenAICompatAdapter
from nudge.integrations.llm.types import LLMResponse, Message, Tier, ToolSpec

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderPreset:
    adapter: Literal["openai_compat", "anthropic"]
    base_url: str | None = None
    # OpenAI's newer models require max_completion_tokens; most others (and Sarvam) want max_tokens.
    # If a provider rejects the token-limit parameter, flip it here.
    max_tokens_param: str = "max_tokens"
    # Extra headers that should also carry the API key (Sarvam's docs use api-subscription-key).
    key_headers: tuple[str, ...] = ()


PRESETS: dict[str, ProviderPreset] = {
    "openai": ProviderPreset("openai_compat", None, max_tokens_param="max_completion_tokens"),
    "google": ProviderPreset(
        "openai_compat", "https://generativelanguage.googleapis.com/v1beta/openai/"
    ),
    "xai": ProviderPreset("openai_compat", "https://api.x.ai/v1"),
    "groq": ProviderPreset("openai_compat", "https://api.groq.com/openai/v1"),
    "sarvam": ProviderPreset(
        "openai_compat", "https://api.sarvam.ai/v1", key_headers=("api-subscription-key",)
    ),
    "anthropic": ProviderPreset("anthropic"),
    # OpenRouter, Ollama, vLLM, LM Studio...: any OpenAI-style endpoint. Requires LLM_BASE_URL.
    "custom": ProviderPreset("openai_compat"),
}


class LLMClient:
    def __init__(
        self,
        *,
        provider: str,
        adapter: LLMAdapter,
        models: Mapping[Tier, str],
        daily_token_budget: int,
    ) -> None:
        self.provider = provider
        self._adapter = adapter
        self._models = dict(models)
        self._budget = daily_token_budget
        self._budget_day: date = datetime.now(UTC).date()
        self._used_tokens = 0  # in-memory: resets on restart; move to the DB with the worker

    def model_for(self, tier: Tier) -> str:
        return self._models[tier]

    @property
    def tokens_used_today(self) -> int:
        self._roll_budget_day()
        return self._used_tokens

    def _roll_budget_day(self) -> None:
        today = datetime.now(UTC).date()
        if today != self._budget_day:
            self._budget_day, self._used_tokens = today, 0

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        tier: Tier = "standard",
        tools: Sequence[ToolSpec] | None = None,
        max_output_tokens: int = 2048,
        temperature: float | None = None,
        purpose: str = "",
    ) -> LLMResponse:
        self._roll_budget_day()
        if self._used_tokens >= self._budget:
            raise BudgetExceededError(
                f"Daily LLM token budget reached ({self._used_tokens}/{self._budget})"
            )

        model = self._models[tier]
        started = time.perf_counter()
        try:
            resp = await self._adapter.complete(
                model=model,
                messages=messages,
                tools=tools,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
            )
        except Exception:
            log.warning(
                "llm call failed",
                extra={"provider": self.provider, "model": model, "tier": tier, "purpose": purpose},
                exc_info=True,
            )
            raise

        self._used_tokens += resp.usage.total
        log.info(
            "llm call",
            extra={
                "provider": self.provider,
                "model": model,
                "tier": tier,
                "purpose": purpose,
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "tool_calls": len(resp.tool_calls),
            },
        )
        return resp

    async def aclose(self) -> None:
        await self._adapter.aclose()


def build_llm_client(settings: Settings) -> LLMClient:
    provider = settings.llm_provider.strip().lower()
    preset = PRESETS.get(provider)
    if preset is None:
        raise ConfigError(f"Unknown LLM_PROVIDER '{provider}'. Options: {', '.join(PRESETS)}")

    api_key = settings.llm_api_key.get_secret_value().strip() if settings.llm_api_key else ""
    if not api_key:
        raise ConfigError("LLM_API_KEY is not set in services/api/.env")

    standard = (settings.llm_model_standard or "").strip()
    if not standard:
        raise ConfigError("LLM_MODEL_STANDARD is not set in services/api/.env")
    models: dict[Tier, str] = {
        "standard": standard,
        "cheap": (settings.llm_model_cheap or "").strip() or standard,
        "reasoning": (settings.llm_model_reasoning or "").strip() or standard,
    }

    adapter: LLMAdapter
    if preset.adapter == "anthropic":
        adapter = AnthropicAdapter(api_key=api_key, timeout_s=settings.llm_timeout_s)
    else:
        base_url = (settings.llm_base_url or "").strip() or preset.base_url
        if provider == "custom" and not base_url:
            raise ConfigError("LLM_PROVIDER=custom requires LLM_BASE_URL")
        adapter = OpenAICompatAdapter(
            api_key=api_key,
            base_url=base_url,
            timeout_s=settings.llm_timeout_s,
            max_tokens_param=preset.max_tokens_param,
            key_headers=preset.key_headers,
        )

    log.info("llm configured", extra={"provider": provider, "models": models})
    return LLMClient(
        provider=provider,
        adapter=adapter,
        models=models,
        daily_token_budget=settings.llm_daily_token_budget,
    )
