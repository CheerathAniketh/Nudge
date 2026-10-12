import pytest

from nudge.errors import BudgetExceededError
from nudge.integrations.llm.adapters import to_anthropic_payload, to_openai_messages
from nudge.integrations.llm.client import LLMClient
from nudge.integrations.llm.types import LLMResponse, Message, ToolCall, Usage

CALLS = (
    ToolCall(id="a", name="add_position", arguments={"symbol": "TCS"}),
    ToolCall(id="b", name="set_rule", arguments={"threshold": 3500}),
)
HISTORY = [
    Message(role="system", content="be brief"),
    Message(role="user", content="I hold TCS"),
    Message(role="assistant", content="", tool_calls=CALLS),
    Message(role="tool", tool_call_id="a", content="ok"),
    Message(role="tool", tool_call_id="b", content="ok"),
]


def test_openai_conversion_keeps_tool_round_trip() -> None:
    out = to_openai_messages(HISTORY)
    assert out[0] == {"role": "system", "content": "be brief"}
    assert [c["id"] for c in out[2]["tool_calls"]] == ["a", "b"]
    assert out[2]["tool_calls"][0]["function"]["arguments"] == '{"symbol": "TCS"}'
    assert out[3]["tool_call_id"] == "a" and out[4]["tool_call_id"] == "b"


def test_anthropic_conversion_merges_tool_results() -> None:
    system, msgs = to_anthropic_payload(HISTORY)
    assert system == "be brief"
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert [b["type"] for b in msgs[1]["content"]] == ["tool_use", "tool_use"]
    assert [b["tool_use_id"] for b in msgs[2]["content"]] == ["a", "b"]


class _FakeAdapter:
    async def complete(self, **_: object) -> LLMResponse:
        return LLMResponse(
            text="hi", tool_calls=(), usage=Usage(60, 60), model="m", stop_reason="stop"
        )

    async def aclose(self) -> None: ...


async def test_daily_budget_blocks_further_calls() -> None:
    llm = LLMClient(
        provider="fake",
        adapter=_FakeAdapter(),
        models={"cheap": "m", "standard": "m", "reasoning": "m"},
        daily_token_budget=100,
    )
    await llm.complete([Message(role="user", content="x")])  # uses 120 tokens
    with pytest.raises(BudgetExceededError):
        await llm.complete([Message(role="user", content="x")])
