import re
from typing import Any

from supabase import AsyncClient

from nudge.models import Instrument

_UNSAFE = re.compile(r"[^A-Za-z0-9 &.\-]")


class InstrumentsRepository:
    """Shared reference data (not user-scoped)."""

    def __init__(self, db: AsyncClient) -> None:
        self._db = db

    async def get_by_symbol(self, symbol: str, exchange: str = "NSE") -> Instrument | None:
        resp = await (
            self._db.table("instruments")
            .select("*")
            .eq("symbol", symbol.strip().upper())
            .eq("exchange", exchange)
            .limit(1)
            .execute()
        )
        return Instrument(**resp.data[0]) if resp.data else None

    async def search(self, query: str, limit: int = 5) -> list[Instrument]:
        """Symbol-prefix or name-contains match, exact symbol first."""
        q = _UNSAFE.sub("", query).strip()  # keeps the filter string injection-safe
        if not q:
            return []
        resp = await (
            self._db.table("instruments")
            .select("*")
            .or_(f"symbol.ilike.{q}*,name.ilike.*{q}*")
            .limit(limit * 3)
            .execute()
        )
        found = [Instrument(**row) for row in resp.data]
        found.sort(key=lambda i: (i.symbol.upper() != q.upper(), len(i.symbol)))
        return found[:limit]

    async def upsert_many(self, rows: list[dict[str, Any]]) -> None:
        if rows:
            await (
                self._db.table("instruments").upsert(rows, on_conflict="symbol,exchange").execute()
            )
