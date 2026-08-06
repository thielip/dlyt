from __future__ import annotations

from typing import Any

from app.services.ttl_cache import get_ttl_cache

ONLINE_TTL_SECONDS = 50
_TOTAL_KEY = "stats:pv_total"
_ONLINE_PREFIX = "stats:online:"


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
    """Refresh online presence; each page_hit increments cumulative page views (e-aboard style)."""
    vid = (visitor_id or "").strip()[:64]
    if not vid:
        raise ValueError("缺少 visitorId")

    cache = get_ttl_cache()
    total = _read_counter(_TOTAL_KEY)

    # Every page load / F5 with page_hit=True counts +1 (no per-day dedupe).
    if page_hit:
        total += 1
        _write_counter(_TOTAL_KEY, total, 400 * 24 * 3600)

    # Any heartbeat marks the visitor online (distinct visitorId within TTL).
    cache.set_json(_online_key(vid), {"ok": 1}, ONLINE_TTL_SECONDS)

    return {
        "onlineNow": cache.count_keys_with_prefix(_ONLINE_PREFIX),
        "pageViewsTotal": total,
    }


def snapshot() -> dict[str, Any]:
    cache = get_ttl_cache()
    return {
        "onlineNow": cache.count_keys_with_prefix(_ONLINE_PREFIX),
        "pageViewsTotal": _read_counter(_TOTAL_KEY),
    }
