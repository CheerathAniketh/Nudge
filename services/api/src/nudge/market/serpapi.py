"""Live quote and news for a watchlist symbol, via SerpApi's Google Finance engine."""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

API_URL = "https://serpapi.com/search.json"
CACHE_DIR = Path(os.environ.get("NUDGE_CACHE_DIR") or Path(__file__).resolve().parents[3] / ".cache" / "serpapi")
CACHE_TTL_S = int(os.environ.get("NUDGE_CACHE_TTL_S", "1800"))


class SerpApiError(RuntimeError):
    pass


_SAFE = re.compile(r"[A-Z0-9][A-Z0-9.&_-]{0,19}")


def validate_symbol(symbol: str, exchange: str) -> tuple[str, str]:
    """Symbols end up in a cache file name and a query string: allow only plain tickers."""
    sym, exch = (symbol or "").strip().upper(), (exchange or "").strip().upper()
    if not _SAFE.fullmatch(sym) or not _SAFE.fullmatch(exch):
        raise SerpApiError("invalid symbol or exchange (letters, digits, . & _ - only)")
    return sym, exch


def _redact(text: object, secret: str) -> str:
    return str(text).replace(secret, "***")[:200]


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
    except (OSError, ValueError) as exc:  # network errors, timeouts, non-JSON bodies
        raise SerpApiError(f"request failed for {symbol}:{exchange}: {_redact(exc, api_key)}") from exc

    if data.get("error"):
        raise SerpApiError(f"{symbol}:{exchange}: {_redact(data['error'], api_key)}")

    # cache only what we use, so nothing sensitive or bulky lands on disk
    trimmed = {k: data.get(k) for k in ("summary", "news_results")}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trimmed))
    return trimmed


def fetch_quote(symbol: str, exchange: str, *, use_cache: bool = True) -> Quote:
    symbol, exchange = validate_symbol(symbol, exchange)
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        raise SerpApiError("SERPAPI_API_KEY is not set")

    raw = _get_raw(symbol, exchange, api_key, use_cache)
    summary = raw.get("summary") or {}
    try:
        price = float(summary.get("extracted_price"))
    except (TypeError, ValueError):
        raise SerpApiError(f"no usable price in response for {symbol}:{exchange}") from None

    move = summary.get("price_movement") or {}
    try:
        pct = float(str(move.get("percentage") or 0).replace("%", "").strip() or 0)
    except ValueError:
        raise SerpApiError(f"unreadable price movement for {symbol}:{exchange}") from None
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
