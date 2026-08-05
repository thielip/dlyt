from __future__ import annotations

from datetime import date
from typing import Any

from app.services.ttl_cache import get_ttl_cache

ONLINE_TTL_SECONDS = 50
_TOTAL_KEY = "stats:pv_total"
_DAY_PREFIX = "stats:pv_day:"
_ONLINE_PREFIX = "stats:online:"
_SEEN_PREFIX = "stats:pv_seen:"


def _day_key() -> str:
    return f"{_DAY_PREFIX}{date.today().isoformat()}"


def _seen_key(visitor_id: str) -> str:
    return f"{_SEEN_PREFIX}{date.today().isoformat()}:{visitor_id}"


def _online_key(visitor_id: str) -> str:
    return f"{_ONLINE_PREFIX}{visitor_id}"


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
    """Refresh online presence; count at most one page view per visitor per day."""
    vid = (visitor_id or "").strip()[:64]
    if not vid:
        raise ValueError("缺少 visitorId")

    cache = get_ttl_cache()
    seen_key = _seen_key(vid)
    already_seen = cache.get_json(seen_key) is not None

    total = _read_counter(_TOTAL_KEY)
    today = _read_counter(_day_key())

    # Dedupe: one page view per visitorId per calendar day (fixes Strict Mode /
    # multi-tab double posts). Only visitors who actually viewed the page today
    # appear in "online" — prevents phantom IDs from inflating the counter.
    if page_hit and not already_seen:
        cache.set_json(seen_key, {"ok": 1}, 3 * 24 * 3600)
        total += 1
        today += 1
        _write_counter(_TOTAL_KEY, total, 400 * 24 * 3600)
        _write_counter(_day_key(), today, 3 * 24 * 3600)
        already_seen = True

    if already_seen:
        cache.set_json(_online_key(vid), {"ok": 1}, ONLINE_TTL_SECONDS)

    return {
        "onlineNow": cache.count_keys_with_prefix(_ONLINE_PREFIX),
        "pageViewsToday": today,
        "pageViewsTotal": total,
    }


def snapshot() -> dict[str, Any]:
    cache = get_ttl_cache()
    return {
        "onlineNow": cache.count_keys_with_prefix(_ONLINE_PREFIX),
        "pageViewsToday": _read_counter(_day_key()),
        "pageViewsTotal": _read_counter(_TOTAL_KEY),
    }
