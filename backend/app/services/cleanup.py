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
            fp = Path(task.file_path)
            # Leave MP3 resume cache intact so retries can reuse the file
            resume_root = (tmp_root / "resume").resolve()
            try:
                under_resume = resume_root in fp.resolve().parents
            except OSError:
                under_resume = False
            if not under_resume:
                fp.unlink(missing_ok=True)
        store.delete(task_id)
        logger.info("purged task %s", task_id, extra={"task_id": task_id, "event": "purge"})

    ttl = settings.file_ttl_seconds
    resume_ttl = max(ttl, settings.mp3_resume_ttl_seconds)
    for child in tmp_root.iterdir():
        if not child.is_dir():
            continue
        # Stable MP3 resume cache — keep longer so retries can skip re-download
        if child.name == "resume":
            for resume_child in child.iterdir():
                if not resume_child.is_dir():
                    continue
                try:
                    mtime = resume_child.stat().st_mtime
                except OSError:
                    continue
                if now - mtime > resume_ttl:
                    shutil.rmtree(resume_child, ignore_errors=True)
            continue
        try:
            mtime = child.stat().st_mtime
        except OSError:
            continue
        if now - mtime > ttl and not store.get(child.name):
            shutil.rmtree(child, ignore_errors=True)
