"""Builds the heads-up text. Never gives buy or sell advice."""
from __future__ import annotations

from nudge.market.rules import Trigger, WatchItem
from nudge.market.serpapi import Quote


def fmt_price(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def compose_message(
    item: WatchItem, quote: Quote, triggers: list[Trigger], summary: str | None = None
) -> str:
    label = "your holding" if item.kind == "holding" else "on your watchlist"
    lines = [
        f"Nudge: {quote.name} ({item.symbol}) is {label}",
        f"{quote.currency} {fmt_price(quote.price)} ({quote.change_pct:+.2f}% vs previous close)",
    ]
    if summary:
        lines.append(summary)
    if triggers:
        lines += [f"- {t.detail}" for t in triggers]
    else:
        lines.append("- no alert rule fired (demo mode)")
    for n in quote.news[:2]:
        lines.append(f"  news: {n.title} ({n.source}, {n.when})")
    if quote.news and quote.news[0].link:
        lines.append(f"  read: {quote.news[0].link}")
    lines.append("Heads-up only, not buy or sell advice.")
    return "\n".join(lines)
