"""Check a watchlist CSV against live SerpApi data and send heads-up nudges."""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nudge.market.envload import load_env  # noqa: E402

load_env()

from nudge.market.compose import compose_message  # noqa: E402
from nudge.market.narrate import narrate  # noqa: E402
from nudge.market.notify import send_telegram  # noqa: E402
from nudge.market.rules import WatchItem, evaluate  # noqa: E402
from nudge.market.serpapi import SerpApiError, fetch_quote  # noqa: E402


def _num(value: str | None) -> float | None:
    value = (value or "").strip()
    return float(value) if value else None


def load_watchlist(path: str) -> list[WatchItem]:
    with open(path, newline="") as fh:
        return [
            WatchItem(
                symbol=row["symbol"].strip().upper(),
                exchange=row["exchange"].strip().upper(),
                kind=(row.get("kind") or "watching").strip().lower(),
                alert_above=_num(row.get("alert_above")),
                alert_below=_num(row.get("alert_below")),
            )
            for row in csv.DictReader(fh)
        ]


async def amain(args: argparse.Namespace) -> None:
    items = load_watchlist(args.watchlist)

    llm = None
    if args.llm:
        try:
            from nudge.config import get_settings
            from nudge.integrations.llm.client import build_llm_client

            llm = build_llm_client(get_settings())
            print(f"[llm] provider={llm.provider} model={llm.model_for('cheap')}")
        except Exception as exc:  # config or provider problem: keep going with templates
            print(f"[llm] unavailable ({type(exc).__name__}); using template text")

    sent = 0
    try:
        for item in items:
            try:
                quote = fetch_quote(item.symbol, item.exchange, use_cache=not args.no_cache)
            except SerpApiError as exc:
                print(f"[skip] {item.symbol}:{item.exchange} {exc}")
                continue

            triggers = evaluate(item, quote, min_move_pct=args.min_move)
            if not triggers and not args.always:
                print(f"[quiet] {item.symbol}: {quote.price:g} ({quote.change_pct:+.2f}%), nothing worth a nudge")
                continue

            summary = None
            if llm is not None:
                try:
                    summary = await narrate(llm, item, quote, triggers)
                except Exception as exc:
                    print(f"[llm] {item.symbol} call failed ({type(exc).__name__})")
                if summary is None:
                    print(f"[llm] {item.symbol}: using template text")

            message = compose_message(item, quote, triggers, summary)
            print("\n" + message + "\n")
            if not args.dry_run and send_telegram(message):
                sent += 1
                print("[telegram] sent")
    finally:
        if llm is not None:
            await llm.aclose()

    print(f"done: {len(items)} symbols checked, {sent} Telegram messages sent")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("watchlist", nargs="?", default=str(Path(__file__).with_name("watchlist.sample.csv")))
    ap.add_argument("--min-move", type=float, default=2.0, help="percent move that counts as big")
    ap.add_argument("--no-cache", action="store_true", help="force fresh SerpApi calls (uses credits)")
    ap.add_argument("--dry-run", action="store_true", help="print only, do not send Telegram")
    ap.add_argument("--always", action="store_true", help="demo mode: report every symbol even if no rule fired")
    ap.add_argument("--llm", action="store_true", help="write the heads-up with the configured LLM provider")
    asyncio.run(amain(ap.parse_args()))


if __name__ == "__main__":
    main()
