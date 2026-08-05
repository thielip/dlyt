from __future__ import annotations

import threading
import time
from datetime import date
from typing import Any

from app.services.ttl_cache import get_ttl_cache

ONLINE_TTL_SECONDS = 50
_TOTAL_KEY = "stats:pv_total"
_DAY_PREFIX = "stats:pv_day:"

_lock = threading.Lock()
_online: dict[str, float] = {}


def _prune_online(now: float) -> None:
    stale = [vid for vid, seen in _online.items() if now - seen > ONLINE_TTL_SECONDS]
    for vid in stale:
        del _online[vid]


def _day_key() -> str:
    return f"{_DAY_PREFIX}{date.today().isoformat()}"


def _read_counter(key: str) -> int:
    raw = get_ttl_cache().get_json(key)
    if isinstance(raw, dict) and "n" in raw:
        try:
            return max(0, int(raw["n"]))
        except (TypeError, ValueError):
            return 0
    return 0


def _write_counter(key: str, value: int, ttl: int) -> None:
    get_ttl_cache().set_json(key, {"n": int(value)}, ttl)


def heartbeat(visitor_id: str, *, page_hit: bool = False) -> dict[str, Any]:
    """Refresh online presence; optionally count one page view for this session."""
    vid = (visitor_id or "").strip()[:64]
    if not vid:
        raise ValueError("缺少 visitorId")

    now = time.time()
    with _lock:
        _prune_online(now)
        _online[vid] = now
        online = len(_online)

    total = _read_counter(_TOTAL_KEY)
    today = _read_counter(_day_key())
    if page_hit:
        total += 1
        today += 1
        _write_counter(_TOTAL_KEY, total, 400 * 24 * 3600)
        _write_counter(_day_key(), today, 3 * 24 * 3600)

    return {
        "onlineNow": online,
        "pageViewsToday": today,
        "pageViewsTotal": total,
    }


def snapshot() -> dict[str, Any]:
    now = time.time()
    with _lock:
        _prune_online(now)
        online = len(_online)
    return {
        "onlineNow": online,
        "pageViewsToday": _read_counter(_day_key()),
        "pageViewsTotal": _read_counter(_TOTAL_KEY),
    }
