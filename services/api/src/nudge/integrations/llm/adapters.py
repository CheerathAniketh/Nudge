"""Provider adapters. Two wire formats cover every supported provider."""

import json
import re
from collections.abc import Sequence
from typing import Any, Protocol

import anthropic
import openai

from nudge.errors import ExternalServiceError
from nudge.integrations.llm.types import LLMResponse, Message, ToolCall, ToolSpec, Usage

# Some reasoning models inline their thinking; users must never see it.
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


class LLMAdapter(Protocol):
    async def complete(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None,
        max_output_tokens: int,
        temperature: float | None,
    ) -> LLMResponse: ...

    async def aclose(self) -> None: ...


# ---------------------------------------------------------------- OpenAI-compatible


def to_openai_messages(messages: Sequence[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "assistant" and m.tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                        }
                        for c in m.tool_calls
                    ],
                }
            )
        elif m.role == "tool":
            out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})
        else:
            out.append({"role": m.role, "content": m.content})
    return out


class OpenAICompatAdapter:
    """OpenAI, Google (Gemini), xAI (Grok), Groq, Sarvam, and any OpenAI-style endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None,
        timeout_s: float,
        max_tokens_param: str,
        key_headers: Sequence[str] = (),
    ) -> None:
        self._max_tokens_param = max_tokens_param
        # Typed Any on purpose: this class is the SDK boundary.
        self._client: Any = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_s,
            max_retries=2,
            default_headers={h: api_key for h in key_headers} or None,
        )

    async def complete(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None,
        max_output_tokens: int,
        temperature: float | None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": to_openai_messages(messages),
            self._max_tokens_param: max_output_tokens,
        }
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
                }
                for t in tools
            ]
        if temperature is not None:  # some reasoning models reject it, so never send by default
            kwargs["temperature"] = temperature

        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except openai.OpenAIError as exc:
            raise ExternalServiceError(
                f"LLM provider error ({type(exc).__name__}): {exc}"
            ) from exc
        if not resp.choices:
            raise ExternalServiceError("LLM returned no choices")

        choice = resp.choices[0]
        calls: list[ToolCall] = []
        for tc in choice.message.tool_calls or []:
            raw = tc.function.arguments or "{}"
            try:
                args = json.loads(raw)
                if not isinstance(args, dict):
                    raise ValueError("arguments must be a JSON object")
                calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
            except ValueError:
                calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments={},
                        error=f"unparseable tool arguments: {raw[:200]}",
                    )
                )
        usage = resp.usage
        return LLMResponse(
            text=_THINK.sub("", choice.message.content or "").strip(),
            tool_calls=tuple(calls),
            usage=Usage(
                input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            ),
            model=resp.model or model,
            stop_reason=choice.finish_reason or "",
        )

    async def aclose(self) -> None:
        await self._client.close()


# ---------------------------------------------------------------- Anthropic


def to_anthropic_payload(messages: Sequence[Message]) -> tuple[str, list[dict[str, Any]]]:
    """Returns (system_prompt, messages). Consecutive tool results become ONE user message."""
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            system_parts.append(m.content)
        elif m.role == "tool":
            block = {"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content}
            last = out[-1] if out else None
            if last and last["role"] == "user" and isinstance(last["content"], list):
                last["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        elif m.role == "assistant":
            blocks: list[dict[str, Any]] = []
            if m.content.strip():
                blocks.append({"type": "text", "text": m.content})
            for c in m.tool_calls:
                blocks.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments})
            if blocks:
                out.append({"role": "assistant", "content": blocks})
        else:
            out.append({"role": "user", "content": m.content})
    return "\n\n".join(system_parts), out


class AnthropicAdapter:
    def __init__(self, *, api_key: str, timeout_s: float) -> None:
        self._client: Any = anthropic.AsyncAnthropic(
            api_key=api_key, timeout=timeout_s, max_retries=2
        )

    async def complete(
        self,
        *,
        model: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None,
        max_output_tokens: int,
        temperature: float | None,
    ) -> LLMResponse:
        system, payload = to_anthropic_payload(messages)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_output_tokens,
            "messages": payload,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ]
        if temperature is not None:
            kwargs["temperature"] = temperature

        try:
            resp = await self._client.messages.create(**kwargs)
        except anthropic.AnthropicError as exc:
            raise ExternalServiceError(
                f"LLM provider error ({type(exc).__name__}): {exc}"
            ) from exc

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))
        return LLMResponse(
            text="".join(text_parts).strip(),
            tool_calls=tuple(calls),
            usage=Usage(
                input_tokens=resp.usage.input_tokens or 0,
                output_tokens=resp.usage.output_tokens or 0,
            ),
            model=resp.model or model,
            stop_reason=resp.stop_reason or "",
        )

    async def aclose(self) -> None:
        await self._client.close()
