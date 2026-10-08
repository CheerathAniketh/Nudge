"""Supabase client factory. Uses the service-role key: it bypasses RLS, so only
repositories may use it, and every query must be scoped by user_id."""

from fastapi import Request
from supabase import AsyncClient, acreate_client

from nudge.config import Settings, get_settings


async def create_db(settings: Settings) -> AsyncClient:
    return await acreate_client(
        settings.supabase_url,
        settings.supabase_service_role_key.get_secret_value(),
    )


async def get_db(request: Request) -> AsyncClient:
    """FastAPI dependency: one shared client per process."""
    db = getattr(request.app.state, "db", None)
    if db is None:
        db = await create_db(get_settings())
        request.app.state.db = db
    return db
