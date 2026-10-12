"""Nudge market-check API: live SerpApi data -> rules -> optional LLM text -> optional Telegram."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from dataclasses import asdict

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from nudge.market.envload import load_env

load_env()

from nudge.market.compose import compose_message  # noqa: E402
from nudge.market.narrate import narrate  # noqa: E402
from nudge.market.notify import send_telegram  # noqa: E402
from nudge.market.rules import WatchItem, evaluate  # noqa: E402
from nudge.market.serpapi import SerpApiError, fetch_quote  # noqa: E402

log = logging.getLogger("nudge.market")

app = FastAPI(title="Nudge", description="Heads-up alerts from live SerpApi finance data")


class WatchIn(BaseModel):
    symbol: str
    exchange: str = "NSE"
    kind: str = "watching"
    alert_above: float | None = None
    alert_below: float | None = None


class CheckIn(BaseModel):
    watchlist: list[WatchIn] = Field(min_length=1, max_length=10)
    min_move_pct: float = 2.0
    use_llm: bool = True
    send_telegram: bool = False
    always: bool = False  # demo mode: report every symbol even if no rule fired
    refresh: bool = False  # bypass the 30-minute cache (uses SerpApi credits)


_INDEX = Path(__file__).with_name("index.html")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(_INDEX)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.post("/v1/check")
async def check(body: CheckIn) -> dict:
    llm = None
    if body.use_llm:
        try:
            from nudge.config import get_settings
            from nudge.integrations.llm.client import build_llm_client

            llm = build_llm_client(get_settings())
        except Exception as exc:
            log.warning("llm unavailable, using template text (%s)", type(exc).__name__)
            llm = None  # fall back to template text

    results: list[dict] = []
    try:
        for w in body.watchlist:
            item = WatchItem(
                symbol=w.symbol.strip().upper(),
                exchange=w.exchange.strip().upper(),
                kind=w.kind.strip().lower(),
                alert_above=w.alert_above,
                alert_below=w.alert_below,
            )
            try:
                quote = await asyncio.to_thread(
                    fetch_quote, item.symbol, item.exchange, use_cache=not body.refresh
                )
            except SerpApiError as exc:
                results.append({"symbol": item.symbol, "status": "error", "error": str(exc)})
                continue
            except Exception:  # one bad symbol must not drop the others
                log.exception("unexpected failure fetching %s", item.symbol)
                results.append({"symbol": item.symbol, "status": "error", "error": "unexpected error"})
                continue

            triggers = evaluate(item, quote, min_move_pct=body.min_move_pct)
            base = {
                "symbol": item.symbol,
                "price": quote.price,
                "currency": quote.currency,
                "change_pct": round(quote.change_pct, 2),
            }
            if not triggers and not body.always:
                results.append({**base, "status": "quiet"})
                continue

            summary = None
            if llm is not None:
                try:
                    summary = await narrate(llm, item, quote, triggers)
                except Exception as exc:
                    log.warning("llm call failed for %s (%s)", item.symbol, type(exc).__name__)
                    summary = None

            message = compose_message(item, quote, triggers, summary)
            sent = await asyncio.to_thread(send_telegram, message) if body.send_telegram else False
            results.append(
                {
                    **base,
                    "status": "nudge",
                    "triggers": [asdict(t) for t in triggers],
                    "llm_used": summary is not None,
                    "telegram_sent": sent,
                    "message": message,
                }
            )
    finally:
        if llm is not None:
            await llm.aclose()
    return {"count": len(results), "results": results}
