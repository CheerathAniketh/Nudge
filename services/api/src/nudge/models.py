"""Domain models shared across layers. Repositories return these, never raw dicts."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Intent = Literal["holding", "considering_buy", "considering_sell"]
RuleType = Literal["price_above", "price_below", "day_drop_pct", "day_gain_pct"]
Source = Literal["chat", "manual", "csv"]


class Instrument(BaseModel):
    id: int
    symbol: str
    exchange: str
    name: str | None = None
    instrument_type: str = "equity"


class Position(BaseModel):
    id: UUID
    user_id: UUID
    instrument: Instrument
    intent: Intent
    quantity: Decimal | None = None
    avg_price: Decimal | None = None
    thesis: str | None = None
    source: Source
    created_at: datetime
    updated_at: datetime


class AlertRule(BaseModel):
    id: UUID
    user_id: UUID
    position_id: UUID
    rule_type: RuleType
    threshold: Decimal
    active: bool
    last_triggered_at: datetime | None = None
    created_at: datetime
