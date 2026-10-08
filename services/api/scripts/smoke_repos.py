"""Manual smoke test of the repository layer against your real Supabase project.

Usage:  uv run python scripts/smoke_repos.py <user_uuid>
"""

import asyncio
import sys
from decimal import Decimal

from nudge.config import get_settings
from nudge.db import create_db
from nudge.repositories.instruments import InstrumentsRepository
from nudge.repositories.positions import PositionsRepository
from nudge.repositories.rules import RulesRepository


async def main(user_id: str) -> None:
    db = await create_db(get_settings())
    instruments = InstrumentsRepository(db)
    positions = PositionsRepository(db)
    rules = RulesRepository(db)

    await instruments.upsert_many(
        [
            {"symbol": "TCS", "exchange": "NSE", "name": "Tata Consultancy Services"},
            {"symbol": "INFY", "exchange": "NSE", "name": "Infosys"},
            {"symbol": "RELIANCE", "exchange": "NSE", "name": "Reliance Industries"},
        ]
    )
    print("search 'tata':", [i.symbol for i in await instruments.search("tata")])

    tcs = await instruments.get_by_symbol("tcs")
    assert tcs is not None
    pos = await positions.upsert(
        user_id,
        tcs.id,
        "holding",
        quantity=Decimal("20"),
        avg_price=Decimal("3800"),
        thesis="long-term IT exposure",
    )
    print("position:", pos.instrument.symbol, pos.quantity, pos.avg_price, pos.thesis)

    # update only the thesis; quantity must stay 20
    pos = await positions.upsert(user_id, tcs.id, "holding", thesis="changed")
    assert pos.quantity == Decimal("20"), "partial upsert overwrote quantity"

    r1 = await rules.upsert_rule(user_id, str(pos.id), "price_below", Decimal("3500"))
    r2 = await rules.upsert_rule(user_id, str(pos.id), "price_below", Decimal("3400"))
    assert r1.id == r2.id and r2.threshold == Decimal("3400"), "rule should update in place"
    print("rules:", [(r.rule_type, r.threshold) for r in await rules.list_for_user(user_id)])

    assert await positions.delete(user_id, str(pos.id))  # rules cascade-delete
    print("OK: all repository checks passed")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
