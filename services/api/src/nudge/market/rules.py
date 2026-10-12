"""Deterministic alert rules. Code decides whether to nudge; nothing here calls an LLM."""
from __future__ import annotations

import re
from dataclasses import dataclass

from nudge.market.serpapi import Quote


@dataclass(frozen=True)
class WatchItem:
    symbol: str
    exchange: str
    kind: str = "watching"  # "holding" or "watching"
    alert_above: float | None = None
    alert_below: float | None = None


@dataclass(frozen=True)
class Trigger:
    code: str  # target_above | target_below | big_move | fresh_news
    detail: str


_AGO = re.compile(r"(\d+)\s*(minute|min|hour|hr|day)s?\s+ago", re.I)


def hours_ago(text: str) -> float | None:
    """Parse Google-style relative times such as '16 hours ago'. None if unparseable."""
    m = _AGO.search(text or "")
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    if unit.startswith("min"):
        return n / 60
    if unit.startswith(("hour", "hr")):
        return float(n)
    return n * 24.0


def evaluate(
    item: WatchItem,
    quote: Quote,
    *,
    min_move_pct: float = 2.0,
    news_max_age_h: float = 24.0,
) -> list[Trigger]:
    triggers: list[Trigger] = []

    if item.alert_above is not None and quote.price >= item.alert_above:
        triggers.append(
            Trigger("target_above", f"price {quote.price:g} is at or above your {item.alert_above:g} level")
        )
    if item.alert_below is not None and quote.price <= item.alert_below:
        triggers.append(
            Trigger("target_below", f"price {quote.price:g} is at or below your {item.alert_below:g} level")
        )

    if abs(quote.change_pct) >= min_move_pct:
        direction = "down" if quote.change_pct < 0 else "up"
        triggers.append(Trigger("big_move", f"{direction} {abs(quote.change_pct):.2f}% vs previous close"))

    fresh = [n for n in quote.news if (h := hours_ago(n.when)) is not None and h <= news_max_age_h]
    if fresh:
        triggers.append(
            Trigger("fresh_news", f"{len(fresh)} news item(s) in the last {news_max_age_h:g}h: {fresh[0].title}")
        )
    return triggers
