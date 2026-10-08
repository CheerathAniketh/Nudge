from decimal import Decimal

from supabase import AsyncClient

from nudge.models import AlertRule, RuleType


class RulesRepository:
    def __init__(self, db: AsyncClient) -> None:
        self._db = db

    async def list_for_user(self, user_id: str, *, active_only: bool = True) -> list[AlertRule]:
        query = self._db.table("alert_rules").select("*").eq("user_id", user_id)
        if active_only:
            query = query.eq("active", True)
        resp = await query.order("created_at").execute()
        return [AlertRule(**row) for row in resp.data]

    async def list_for_position(
        self, user_id: str, position_id: str, *, active_only: bool = True
    ) -> list[AlertRule]:
        query = (
            self._db.table("alert_rules")
            .select("*")
            .eq("user_id", user_id)
            .eq("position_id", position_id)
        )
        if active_only:
            query = query.eq("active", True)
        resp = await query.order("created_at").execute()
        return [AlertRule(**row) for row in resp.data]

    async def upsert_rule(
        self, user_id: str, position_id: str, rule_type: RuleType, threshold: Decimal
    ) -> AlertRule:
        """One active rule per (position, type): setting it again updates the threshold."""
        existing = await (
            self._db.table("alert_rules")
            .select("id")
            .eq("user_id", user_id)
            .eq("position_id", position_id)
            .eq("rule_type", rule_type)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        if existing.data:
            resp = await (
                self._db.table("alert_rules")
                .update({"threshold": str(threshold), "last_triggered_at": None})
                .eq("id", existing.data[0]["id"])
                .eq("user_id", user_id)
                .execute()
            )
        else:
            resp = await (
                self._db.table("alert_rules")
                .insert(
                    {
                        "user_id": user_id,
                        "position_id": position_id,
                        "rule_type": rule_type,
                        "threshold": str(threshold),
                    }
                )
                .execute()
            )
        return AlertRule(**resp.data[0])

    async def deactivate(self, user_id: str, rule_id: str) -> bool:
        resp = await (
            self._db.table("alert_rules")
            .update({"active": False})
            .eq("id", rule_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(resp.data)
