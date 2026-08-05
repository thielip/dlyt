from __future__ import annotations

import asyncio
import threading
from collections import defaultdict

from fastapi import HTTPException

from app.config import get_settings

_lock = threading.Lock()
_active_by_ip: dict[str, set[str]] = defaultdict(set)
_download_sem: asyncio.Semaphore | None = None


def init_download_semaphore() -> asyncio.Semaphore:
    global _download_sem
    settings = get_settings()
    _download_sem = asyncio.Semaphore(max(1, settings.max_concurrent_downloads))
    return _download_sem


def get_download_semaphore() -> asyncio.Semaphore:
    global _download_sem
    if _download_sem is None:
        return init_download_semaphore()
    return _download_sem


def count_active_for_ip(ip: str) -> int:
    with _lock:
        return len(_active_by_ip.get(ip, set()))


def acquire_ip_slot(ip: str, task_id: str) -> None:
    settings = get_settings()
    limit = max(1, settings.max_active_tasks_per_ip)
    with _lock:
        active = _active_by_ip[ip]
        if task_id in active:
            return
        if len(active) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"此連線尚有進行中的下載（上限 {limit}），請完成後再試",
            )
        active.add(task_id)


def release_ip_slot(ip: str, task_id: str) -> None:
    with _lock:
        active = _active_by_ip.get(ip)
        if not active:
            return
        active.discard(task_id)
        if not active:
            _active_by_ip.pop(ip, None)
