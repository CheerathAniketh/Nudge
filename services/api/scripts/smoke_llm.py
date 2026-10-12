"""Live smoke test of the LLM layer with whatever provider .env points at.

Usage:  uv run python scripts/smoke_llm.py [cheap|standard|reasoning]
"""

import asyncio
import sys
from typing import cast

from nudge.config import get_settings
from nudge.integrations.llm.client import build_llm_client
from nudge.integrations.llm.types import Message, Tier, ToolSpec

TOOLS = [
    ToolSpec(
        name="add_position",
        description="Save a stock position the user told us about.",
        parameters={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "quantity": {"type": "number"},
                "avg_price": {"type": "number"},
            },
            "required": ["symbol", "quantity", "avg_price"],
        },
    )
]


async def main(tier: Tier) -> None:
    llm = build_llm_client(get_settings())
    print(f"provider={llm.provider} model={llm.model_for(tier)}")

    history = [
        Message(
            role="system",
            content="You are a portfolio assistant. When the user states a holding, call add_position.",
        ),
        Message(role="user", content="I hold 20 TCS shares, bought around 3800"),
    ]
    r1 = await llm.complete(history, tier=tier, tools=TOOLS, purpose="smoke")
    print(f"call 1: tokens={r1.usage.total} text={r1.text[:100]!r}")

    if not r1.tool_calls:
        print("WARN: model did not call the tool. Tool calling may be weak on this model.")
        await llm.aclose()
        return
    for call in r1.tool_calls:
        print("tool call:", call.name, call.arguments, call.error or "")

    history.append(r1.as_message())
    for call in r1.tool_calls:
        history.append(Message(role="tool", tool_call_id=call.id, content='{"status": "saved"}'))
    r2 = await llm.complete(history, tier=tier, tools=TOOLS, purpose="smoke")
    print(f"call 2: tokens={r2.usage.total} text={r2.text[:200]!r}")
    print(f"OK: tool round trip works. Tokens used today: {llm.tokens_used_today}")
    await llm.aclose()


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "standard"
    if arg not in ("cheap", "standard", "reasoning"):
        sys.exit("tier must be cheap, standard or reasoning")
    asyncio.run(main(cast(Tier, arg)))
