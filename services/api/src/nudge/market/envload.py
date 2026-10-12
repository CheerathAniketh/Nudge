"""Minimal .env loader so the market scripts see keys without exporting them by hand."""
from __future__ import annotations

import os
from pathlib import Path

# The market slice never touches Supabase, but the shared Settings model requires these three.
# Placeholders let a fresh clone run with only the SerpApi, LLM and Telegram keys; real values win.
_UNUSED_BY_MARKET = {
    "SUPABASE_URL": "https://unused.invalid",
    "SUPABASE_ANON_KEY": "unused",
    "SUPABASE_SERVICE_ROLE_KEY": "unused",
}


def load_env() -> None:
    here = Path(__file__).resolve()
    for base in (here.parents[3], here.parents[5]):  # services/api, then repo root
        path = base / ".env"
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip("'\"")
            if value:
                os.environ.setdefault(key.strip(), value)
    for key, value in _UNUSED_BY_MARKET.items():
        os.environ.setdefault(key, value)
