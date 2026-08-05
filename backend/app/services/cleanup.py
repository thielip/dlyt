from __future__ import annotations

import asyncio
import logging
import shutil
import time
from pathlib import Path

from app.config import Settings, get_settings
from app.services.task_store import get_task_store

logger = logging.getLogger(__name__)


async def cleanup_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(_cleanup_once, get_settings())
        except Exception:  # noqa: BLE001
            logger.exception("cleanup failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=60)
        except asyncio.TimeoutError:
            continue


def _should_purge(task, now: float, settings: Settings) -> bool:
    if task.purge_after is not None and now >= task.purge_after:
        return True
    updated = task.updated_at or task.created_at or now
    return (now - updated) >= settings.file_ttl_seconds


def _cleanup_once(settings: Settings) -> None:
    store = get_task_store()
    now = time.time()
    tmp_root = Path(settings.tmp_dir)
    if not tmp_root.exists():
        return

    for task_id in store.list_ids():
        task = store.get(task_id)
        if not task:
            continue
        if not _should_purge(task, now, settings):
            continue
        task_dir = tmp_root / task_id
        if task_dir.exists():
            shutil.rmtree(task_dir, ignore_errors=True)
        if task.file_path:
            Path(task.file_path).unlink(missing_ok=True)
        store.delete(task_id)
        logger.info("purged task %s", task_id, extra={"task_id": task_id, "event": "purge"})

    ttl = settings.file_ttl_seconds
    for child in tmp_root.iterdir():
        if not child.is_dir():
            continue
        try:
            mtime = child.stat().st_mtime
        except OSError:
            continue
        if now - mtime > ttl and not store.get(child.name):
            shutil.rmtree(child, ignore_errors=True)
