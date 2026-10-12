"""Builds the heads-up text. Never gives buy or sell advice."""
from __future__ import annotations

from nudge.market.rules import MATERIAL, Trigger, WatchItem, is_tip
from nudge.market.serpapi import NewsItem, Quote


def fmt_price(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def pick_news(quote: Quote, limit: int = 2) -> list[NewsItem]:
    """Headlines worth showing: no stock-tip clickbait, material ones first, newest first within each group."""
    clean = [n for n in quote.news if not is_tip(n.title)]
    clean.sort(key=lambda n: 0 if MATERIAL.search(n.title) else 1)
    return clean[:limit]


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
    shown = pick_news(quote)
    for n in shown:
        lines.append(f"  news: {n.title} ({n.source}, {n.when})")
    if shown and shown[0].link:
        lines.append(f"  read: {shown[0].link}")
    lines.append("Heads-up only, not buy or sell advice.")
    return "\n".join(lines)
