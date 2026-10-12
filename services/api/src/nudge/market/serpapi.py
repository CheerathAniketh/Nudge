"""Live quote and news for a watchlist symbol, via SerpApi's Google Finance engine."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

API_URL = "https://serpapi.com/search.json"
CACHE_DIR = Path(os.environ.get("NUDGE_CACHE_DIR", ".cache/serpapi"))
CACHE_TTL_S = int(os.environ.get("NUDGE_CACHE_TTL_S", "1800"))


class SerpApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    when: str
    link: str


@dataclass(frozen=True)
class Quote:
    symbol: str
    exchange: str
    name: str
    price: float
    currency: str
    change_pct: float  # signed: negative means down vs previous close
    as_of: str
    news: list[NewsItem] = field(default_factory=list)


def _get_raw(symbol: str, exchange: str, api_key: str, use_cache: bool) -> dict:
    path = CACHE_DIR / f"{symbol}_{exchange}.json"
    if use_cache and path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL_S:
        return json.loads(path.read_text())

    query = urllib.parse.urlencode(
        {"engine": "google_finance", "q": f"{symbol}:{exchange}", "hl": "en", "api_key": api_key}
    )
    try:
        with urllib.request.urlopen(f"{API_URL}?{query}", timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SerpApiError(f"request failed for {symbol}:{exchange}: {exc}") from exc

    if data.get("error"):
        raise SerpApiError(f"{symbol}:{exchange}: {data['error']}")

    # cache only what we use, so nothing sensitive or bulky lands on disk
    trimmed = {k: data.get(k) for k in ("summary", "news_results")}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trimmed))
    return trimmed


def fetch_quote(symbol: str, exchange: str, *, use_cache: bool = True) -> Quote:
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        raise SerpApiError("SERPAPI_API_KEY is not set")

    raw = _get_raw(symbol, exchange, api_key, use_cache)
    summary = raw.get("summary") or {}
    price = summary.get("extracted_price")
    if price is None:
        raise SerpApiError(f"no price in response for {symbol}:{exchange}")

    move = summary.get("price_movement") or {}
    pct = float(move.get("percentage") or 0.0)
    if move.get("movement") == "Down":
        pct = -pct

    news = [
        NewsItem(
            title=n.get("snippet", ""),
            source=n.get("source", ""),
            when=n.get("date", ""),
            link=n.get("link", ""),
        )
        for n in (raw.get("news_results") or [])
        if isinstance(n, dict)
    ]
    return Quote(
        symbol=symbol,
        exchange=exchange,
        name=summary.get("title") or symbol,
        price=float(price),
        currency=summary.get("currency") or "",
        change_pct=pct,
        as_of=summary.get("date") or "",
        news=news,
    )
