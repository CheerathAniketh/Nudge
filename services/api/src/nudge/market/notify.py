"""Telegram delivery. Returns False (and the caller just prints) when not configured or failing."""
from __future__ import annotations

import logging
import os
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger("nudge.market")


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.warning("telegram not configured: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing")
        return False
    data = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    ).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as exc:
        log.warning("telegram send failed: HTTP %s", exc.code)
    except OSError as exc:  # connection resets, timeouts, DNS
        log.warning("telegram send failed: %s", type(exc).__name__)  # never log the URL: it holds the token
    return False
