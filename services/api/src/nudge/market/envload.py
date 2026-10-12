"""Minimal .env loader so the market scripts see keys without exporting them by hand."""
from __future__ import annotations

import os
from pathlib import Path


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
