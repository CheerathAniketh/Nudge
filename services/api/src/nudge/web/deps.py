"""Auth dependency: verifies the Supabase access token and returns the current user.

We ask Supabase Auth to validate the token (works with any key setup, no secrets needed)
and cache the result for 30s so we don't make a network call on every request.
Can be swapped for local JWKS verification later without touching any route.
"""

import hashlib
import time
from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from nudge.config import Settings, get_settings
from nudge.errors import AuthError, ExternalServiceError

_bearer = HTTPBearer(auto_error=False)
_CACHE_TTL_S = 30
_CACHE_MAX = 1024


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None


_cache: dict[str, tuple[float, CurrentUser]] = {}


def _cache_get(key: str) -> CurrentUser | None:
    hit = _cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    _cache.pop(key, None)
    return None


def _cache_put(key: str, user: CurrentUser) -> None:
    if len(_cache) >= _CACHE_MAX:
        _cache.clear()
    _cache[key] = (time.monotonic() + _CACHE_TTL_S, user)


async def get_current_user(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    if creds is None:
        raise AuthError("Missing bearer token")

    token = creds.credentials
    key = hashlib.sha256(token.encode()).hexdigest()
    if cached := _cache_get(key):
        return cached

    http: httpx.AsyncClient = request.app.state.http
    try:
        resp = await http.get(
            f"{settings.supabase_auth_url}/user",
            headers={
                "apikey": settings.supabase_anon_key.get_secret_value(),
                "Authorization": f"Bearer {token}",
            },
        )
    except httpx.HTTPError as exc:
        raise ExternalServiceError("Auth service unreachable") from exc

    if resp.status_code in (401, 403):
        raise AuthError("Invalid or expired token")
    if resp.status_code != 200:
        raise ExternalServiceError(f"Auth service returned {resp.status_code}")

    data = resp.json()
    user = CurrentUser(id=data["id"], email=data.get("email"))
    _cache_put(key, user)
    return user


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
