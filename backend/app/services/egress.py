from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException

from app.config import get_settings
from app.services.ttl_cache import get_ttl_cache

logger = logging.getLogger(__name__)
_lock = threading.Lock()

OutboundPressure = Literal["ok", "soft", "hard"]


def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def get_monthly_outbound() -> int:
    cache = get_ttl_cache()
    raw = cache.get_json(f"egress:{_month_key()}")
    if isinstance(raw, dict):
        return int(raw.get("bytes") or 0)
    return 0


def add_outbound_bytes(n: int) -> None:
    if n <= 0:
        return
    cache = get_ttl_cache()
    key = f"egress:{_month_key()}"
    with _lock:
        used = get_monthly_outbound() + n
        cache.set_json(key, {"bytes": used}, ttl_seconds=40 * 24 * 3600)
    logger.info("outbound +%s total=%s", n, used, extra={"event": "egress"})


def outbound_pressure() -> OutboundPressure:
    """
    Pessimistic planning: treat proxy as the common path.
    soft ≈ hide high-quality proxy options; hard ≈ proxy blocked, direct/subtitle only.
    """
    settings = get_settings()
    limit = max(1, settings.max_monthly_outbound_bytes)
    used = get_monthly_outbound()
    ratio = used / limit
    if ratio >= settings.outbound_hard_ratio:
        return "hard"
    if ratio >= settings.outbound_soft_ratio:
        return "soft"
    return "ok"


def ensure_outbound_budget(extra: int = 0) -> None:
    settings = get_settings()
    used = get_monthly_outbound()
    if used + max(0, extra) >= settings.max_monthly_outbound_bytes:
        raise HTTPException(
            status_code=503,
            detail="免費流量已使用完畢。本月伺服器代理流量額度已用盡，請下個月再試",
        )


def ensure_proxy_allowed() -> None:
    """Block new proxy downloads under hard pressure (direct/subtitle still ok)."""
    if outbound_pressure() == "hard":
        raise HTTPException(
            status_code=503,
            detail="本月代理流量吃緊，已暫停需合併／代理的下載。請改選標示「直連」的畫質或字幕",
        )
