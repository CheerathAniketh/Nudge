from decimal import Decimal
from typing import Any

from supabase import AsyncClient

from nudge.errors import ExternalServiceError
from nudge.models import Intent, Position, Source


class PositionsRepository:
    _SELECT = "*, instrument:instruments(*)"

    def __init__(self, db: AsyncClient) -> None:
        self._db = db

    async def list_for_user(self, user_id: str, intent: Intent | None = None) -> list[Position]:
        query = self._db.table("positions").select(self._SELECT).eq("user_id", user_id)
        if intent:
            query = query.eq("intent", intent)
        resp = await query.order("created_at").execute()
        return [Position(**row) for row in resp.data]

    async def get_by_instrument(self, user_id: str, instrument_id: int) -> Position | None:
        resp = await (
            self._db.table("positions")
            .select(self._SELECT)
            .eq("user_id", user_id)
            .eq("instrument_id", instrument_id)
            .limit(1)
            .execute()
        )
        return Position(**resp.data[0]) if resp.data else None

    async def upsert(
        self,
        user_id: str,
        instrument_id: int,
        intent: Intent,
        *,
        quantity: Decimal | None = None,
        avg_price: Decimal | None = None,
        thesis: str | None = None,
        source: Source = "chat",
    ) -> Position:
        """Create or update. Optional fields left as None are NOT overwritten."""
        row: dict[str, Any] = {
            "user_id": user_id,
            "instrument_id": instrument_id,
            "intent": intent,
            "source": source,
        }
        if quantity is not None:
            row["quantity"] = str(quantity)
        if avg_price is not None:
            row["avg_price"] = str(avg_price)
        if thesis is not None:
            row["thesis"] = thesis

        await self._db.table("positions").upsert(row, on_conflict="user_id,instrument_id").execute()
        position = await self.get_by_instrument(user_id, instrument_id)
        if position is None:
            raise ExternalServiceError("Position missing right after upsert")
        return position

    async def delete(self, user_id: str, position_id: str) -> bool:
        resp = await (
            self._db.table("positions")
            .delete()
            .eq("id", position_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(resp.data)
