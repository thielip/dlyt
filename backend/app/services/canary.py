from __future__ import annotations

import asyncio
import logging
import time

from app.config import get_settings
from app.services import ytdlp_service
from app.services.task_store import get_task_store

logger = logging.getLogger(__name__)

_canary_status: str = "unknown"
_canary_detail: str = ""


def get_canary_status() -> tuple[str, str]:
    return _canary_status, _canary_detail


def recover_interrupted_tasks() -> int:
    """Mark orphan pending/processing tasks as failed after process restart."""
    store = get_task_store()
    count = 0
    for task_id in store.list_ids():
        task = store.get(task_id)
        if not task:
            continue
        if task.status in {"pending", "processing"}:
            store.update(
                task_id,
                status="failed",
                progress=100,
                message="任務中斷",
                error="服務重啟，任務已中斷，請重新下載",
                updated_at=time.time(),
            )
            count += 1
    return count


def run_canary_probe() -> None:
    global _canary_status, _canary_detail
    settings = get_settings()
    url = (settings.canary_url or "").strip()
    if not url:
        _canary_status = "skipped"
        _canary_detail = "未設定 CANARY_URL"
        return
    try:
        info = ytdlp_service.extract_video_info(url, use_cache=False)
        _canary_status = "ok"
        _canary_detail = f"{info.id}:{info.title[:40]}"
        logger.info("yt-dlp canary ok: %s", _canary_detail)
    except Exception as exc:  # noqa: BLE001
        _canary_status = "degraded"
        _canary_detail = str(exc)[:200]
        logger.warning("yt-dlp canary failed: %s", _canary_detail)


async def warmup_canary() -> None:
    await asyncio.to_thread(run_canary_probe)
