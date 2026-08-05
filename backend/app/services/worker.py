from __future__ import annotations

import asyncio
import logging
import threading
import time
from pathlib import Path

from app.config import get_settings
from app.schemas import CreateDownloadRequest, TaskProgress
from app.services.url_utils import strip_ansi
from app.services import asr_service, ytdlp_service
from app.services.concurrency import get_download_semaphore, release_ip_slot
from app.services.disk import ensure_disk_space
from app.services.egress import ensure_outbound_budget, ensure_proxy_allowed
from app.services.executors import get_download_executor
from app.services.task_store import get_task_store

logger = logging.getLogger(__name__)


def _public_download_url(task_id: str) -> str:
    settings = get_settings()
    base = settings.public_base_url.rstrip("/")
    path = f"/api/files/{task_id}"
    return f"{base}{path}" if base else path


class ProgressThrottler:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self._last_ts = 0.0
        self._last_progress = -1.0
        self._store = get_task_store()

    def update(self, progress: float, message: str, *, force: bool = False) -> None:
        now = time.time()
        if (
            not force
            and (now - self._last_ts) < 0.5
            and abs(progress - self._last_progress) < 2.0
        ):
            return
        self._last_ts = now
        self._last_progress = progress
        self._store.update(
            self.task_id,
            status="processing",
            progress=progress,
            message=message,
        )


def _complete_redirect(
    task_id: str,
    *,
    direct_url: str,
    filename: str,
) -> None:
    store = get_task_store()
    store.update(
        task_id,
        status="completed",
        progress=100,
        message="已取得直連網址（流量不經本伺服器）。若瀏覽器無法下載，請改選非直連畫質。",
        filename=filename,
        delivery="redirect",
        direct_url=direct_url,
        file_path=None,
        downloadUrl=_public_download_url(task_id),
        error=None,
    )


def _run_asr_task(task_id: str, payload: CreateDownloadRequest) -> None:
    store = get_task_store()
    settings = get_settings()
    ensure_proxy_allowed()
    ensure_outbound_budget(0)
    ensure_disk_space()

    task_dir = Path(settings.tmp_dir) / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(task_dir / "%(title).80B [%(id)s].%(ext)s")
    throttler = ProgressThrottler(task_id)
    api_key = (payload.geminiApiKey or "").strip()

    def hook(d: dict) -> None:
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            progress = 5.0
            if total:
                progress = max(5.0, min(42.0, 5.0 + downloaded / total * 37))
            throttler.update(progress, "正在下載音訊以供語音辨識…")
        elif status == "finished":
            throttler.update(45.0, "音訊下載完成，準備辨識…", force=True)

    audio_path: Path | None = None
    heartbeat_stop = threading.Event()
    heartbeat_thread: threading.Thread | None = None

    def _start_heartbeat(base: float, label: str) -> None:
        nonlocal heartbeat_thread
        heartbeat_stop.clear()
        started = time.time()

        def run() -> None:
            while not heartbeat_stop.wait(2.5):
                elapsed = int(time.time() - started)
                progress = min(86.0, base + elapsed * 0.22)
                m, s = divmod(elapsed, 60)
                wait = f"{m}:{s:02d}" if m else f"{s} 秒"
                throttler.update(
                    progress,
                    f"{label}（已等待 {wait}，雲端辨識可能需 1–3 分鐘，請勿關閉）",
                    force=True,
                )

        heartbeat_thread = threading.Thread(
            target=run, daemon=True, name=f"asr-hb-{task_id[:8]}"
        )
        heartbeat_thread.start()

    def _stop_heartbeat() -> None:
        heartbeat_stop.set()
        if heartbeat_thread and heartbeat_thread.is_alive():
            heartbeat_thread.join(timeout=1.0)

    try:
        store.update(task_id, status="processing", progress=8, message="開始下載音訊…")
        audio_file = ytdlp_service.download_audio_only(
            url=payload.url,
            outtmpl=outtmpl,
            progress_hook=hook,
        )
        audio_path = Path(audio_file)

        stage_progress = {
            "prepare": (50.0, "正在壓縮／準備音訊…"),
            "encode": (56.0, "正在編碼音訊…"),
            "upload": (60.0, "正在上傳音訊至 Gemini…"),
            "waiting": (65.0, "Gemini 雲端語音辨識中"),
            "parse": (88.0, "正在整理字幕…"),
        }

        def on_stage(name: str, detail: str = "") -> None:
            prog, default_msg = stage_progress.get(name, (70.0, "處理中…"))
            msg = detail or default_msg
            throttler.update(prog, msg, force=True)
            if name == "waiting":
                _stop_heartbeat()
                _start_heartbeat(prog, "Gemini 雲端語音辨識中")
            elif name in {"prepare", "encode", "upload"}:
                _stop_heartbeat()
                _start_heartbeat(prog, msg.rstrip("…") or default_msg)

        throttler.update(48.0, "準備呼叫 Gemini…", force=True)
        _start_heartbeat(48.0, "準備音訊中")
        segments = asr_service.transcribe_with_gemini(
            api_key=api_key,
            audio_path=audio_path,
            language=payload.asrLanguage or "zh",
            on_stage=on_stage,
        )
        _stop_heartbeat()
        throttler.update(92.0, "正在寫入字幕檔…", force=True)
        fmt = payload.subtitleFormat or "srt"
        stem = audio_path.stem
        out_path = task_dir / f"{stem}.{fmt}"
        asr_service.write_subtitle_file(segments, dest=out_path, fmt=fmt)

        try:
            if audio_path.exists():
                audio_path.unlink(missing_ok=True)
            for leftover in task_dir.glob("*.asr.mp3"):
                leftover.unlink(missing_ok=True)
        except OSError:
            pass

        size = out_path.stat().st_size
        ensure_outbound_budget(size)
        store.update(
            task_id,
            status="completed",
            progress=100,
            message="語音辨識完成，可下載字幕",
            filename=out_path.name,
            file_path=str(out_path),
            delivery="proxy",
            direct_url=None,
            downloadUrl=_public_download_url(task_id),
            error=None,
        )
        logger.info("asr completed", extra={"task_id": task_id, "event": "asr_ok"})
    except Exception as exc:  # noqa: BLE001
        _stop_heartbeat()
        store.update(
            task_id,
            status="failed",
            progress=100,
            message="語音辨識失敗",
            error=strip_ansi(str(exc)),
            updated_at=time.time(),
        )
        logger.warning("asr failed: %s", exc, extra={"task_id": task_id, "event": "asr_fail"})
        if audio_path and audio_path.exists():
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                pass


def run_download_task(task_id: str, payload: CreateDownloadRequest) -> None:
    store = get_task_store()
    settings = get_settings()

    if payload.mode == "asr":
        _run_asr_task(task_id, payload)
        return

    # Prefer direct URL for progressive/audio to avoid Render egress burn
    if settings.prefer_direct_download and ytdlp_service.can_try_direct_delivery(
        payload.mode, payload.formatId
    ):
        try:
            store.update(task_id, status="processing", progress=10, message="解析直連網址…")
            media_url, ext, _size, stem = ytdlp_service.resolve_direct_media_url(
                payload.url, payload.formatId or ""
            )
            _complete_redirect(task_id, direct_url=media_url, filename=f"{stem}.{ext}")
            logger.info("direct redirect ready", extra={"task_id": task_id, "event": "direct_ok"})
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("direct resolve failed: %s", exc, extra={"task_id": task_id})
            if not settings.allow_proxy_fallback:
                store.update(
                    task_id,
                    status="failed",
                    progress=100,
                    message="直連失敗",
                    error=strip_ansi(str(exc)),
                )
                return
            store.update(task_id, message="直連失敗，改走伺服器代理下載…", progress=15)

    # Proxy path — counts toward monthly outbound budget (pessimistic common case)
    ensure_proxy_allowed()
    ensure_outbound_budget(0)
    ensure_disk_space()
    task_dir = Path(settings.tmp_dir) / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(task_dir / "%(title).80B [%(id)s].%(ext)s")
    throttler = ProgressThrottler(task_id)

    def hook(d: dict) -> None:
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            progress = 5.0
            if total:
                progress = max(5.0, min(95.0, downloaded / total * 100))
            throttler.update(progress, "正在經伺服器代理下載…")
        elif status == "finished":
            throttler.update(96.0, "正在處理檔案…", force=True)

    try:
        store.update(
            task_id,
            status="processing",
            progress=18,
            message="正在準備串流（沿用已解析資訊）…",
        )
        filepath = ytdlp_service.download_media(
            url=payload.url,
            outtmpl=outtmpl,
            mode=payload.mode,
            format_id=payload.formatId,
            subtitle_language=payload.subtitleLanguage,
            subtitle_format=payload.subtitleFormat,
            container_format=payload.containerFormat or "webm",
            progress_hook=hook,
        )
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError("下載完成但找不到檔案")

        size = path.stat().st_size
        if settings.max_filesize_bytes > 0 and size > settings.max_filesize_bytes:
            path.unlink(missing_ok=True)
            raise ValueError("檔案超過大小限制")

        # Reserve budget for upcoming user download (egress)
        ensure_outbound_budget(size)

        store.update(
            task_id,
            status="completed",
            progress=100,
            message="下載完成（經伺服器代理，會消耗免費頻寬額度）",
            filename=path.name,
            file_path=str(path),
            delivery="proxy",
            direct_url=None,
            downloadUrl=_public_download_url(task_id),
            error=None,
        )
        logger.info("proxy download completed", extra={"task_id": task_id, "event": "proxy_ok"})
    except Exception as exc:  # noqa: BLE001
        store.update(
            task_id,
            status="failed",
            progress=100,
            message="下載失敗",
            error=strip_ansi(str(exc)),
            updated_at=time.time(),
        )
        logger.warning("download failed: %s", exc, extra={"task_id": task_id, "event": "download_fail"})


async def run_download_job(task_id: str, payload: CreateDownloadRequest, ip: str) -> None:
    store = get_task_store()
    settings = get_settings()
    store.update(task_id, status="pending", message="等待下載名額…")
    sem = get_download_semaphore()
    loop = asyncio.get_running_loop()
    timeout = (
        settings.asr_timeout_seconds
        if payload.mode == "asr"
        else settings.download_timeout_seconds
    )
    async with sem:
        try:
            await asyncio.wait_for(
                loop.run_in_executor(get_download_executor(), run_download_task, task_id, payload),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            store.update(
                task_id,
                status="failed",
                progress=100,
                message="下載逾時",
                error=f"超過 {timeout} 秒仍未完成，請稍後再試或選直連／較低畫質",
            )
            logger.warning("download timeout", extra={"task_id": task_id, "event": "download_timeout"})
        finally:
            release_ip_slot(ip, task_id)


def create_pending_task(
    task_id: str,
    *,
    filename_hint: str | None = None,
    fingerprint: str | None = None,
) -> TaskProgress:
    store = get_task_store()
    task = TaskProgress(
        taskId=task_id,
        status="pending",
        progress=0,
        message="任務已建立，等待處理…",
        filename=filename_hint,
        fingerprint=fingerprint,
    )
    return store.create(task)
