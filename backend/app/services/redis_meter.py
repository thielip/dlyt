from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from app.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_commands_today = 0
_day_key = ""
_degraded = False


def _roll_day() -> None:
    global _commands_today, _day_key
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if today != _day_key:
        _day_key = today
        _commands_today = 0


def note_redis_commands(n: int = 1) -> None:
    """In-process soft meter for Upstash command budget."""
    global _commands_today, _degraded
    settings = get_settings()
    limit = settings.redis_max_commands_per_day
    with _lock:
        _roll_day()
        _commands_today += n
        if _commands_today >= limit and not _degraded:
            _degraded = True
            logger.warning(
                "Redis command soft-limit reached (%s); cache will prefer memory",
                limit,
            )


def redis_degraded() -> bool:
    with _lock:
        _roll_day()
        return _degraded or _commands_today >= get_settings().redis_max_commands_per_day


def redis_command_count() -> int:
    with _lock:
        _roll_day()
        return _commands_today


def reset_redis_meter_for_tests() -> None:
    global _commands_today, _degraded, _day_key
    with _lock:
        _commands_today = 0
        _degraded = False
        _day_key = ""
