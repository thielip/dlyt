import asyncio
import time
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.config import get_settings
from app.schemas import CreateDownloadRequest, CreateDownloadResponse
from app.services.concurrency import acquire_ip_slot
from app.services.disk import ensure_disk_space
from app.services.egress import ensure_outbound_budget, ensure_proxy_allowed
from app.services.executors import get_info_executor
from app.services.rate_limit import client_ip, enforce_rate_limit
from app.services.task_store import get_task_store
from app.services.turnstile import verify_turnstile
from app.services.worker import create_pending_task, run_download_job
from app.services.ytdlp_service import download_dedupe_key, extract_video_info, validate_url

router = APIRouter(prefix="/api", tags=["download"])

# Stuck jobs after OOM / deploy should not block retries forever.
_STALE_PENDING_SECONDS = 120
_STALE_PROCESSING_SECONDS = 600


def _task_still_reusable(existing) -> bool:
    if existing is None:
        return False
    if existing.status == "completed":
        return True
    if existing.status not in {"pending", "processing"}:
        return False
    now = time.time()
    updated = float(existing.updated_at or existing.created_at or 0)
    age = now - updated if updated else now
    if existing.status == "pending" and age > _STALE_PENDING_SECONDS:
        return False
    if existing.status == "processing" and age > _STALE_PROCESSING_SECONDS:
        return False
    return True


@router.post("/download", response_model=CreateDownloadResponse)
async def post_download(
    body: CreateDownloadRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> CreateDownloadResponse:
    enforce_rate_limit(request)
    ip = client_ip(request)
    await verify_turnstile(body.turnstileToken, ip)
    validate_url(body.url)

    settings = get_settings()
    ensure_outbound_budget(0)
    needs_proxy = not (
        settings.prefer_direct_download
        and body.mode == "video"
        and body.formatId
        and "+" not in body.formatId
        and body.formatId not in {"b", "bv*+ba/b", "audio-mp3", "bestaudio", "bestaudio/b"}
    )
    if body.mode in {"subtitle", "asr"} or needs_proxy:
        if needs_proxy and body.mode == "video":
            ensure_proxy_allowed()
        if body.mode == "asr":
            ensure_proxy_allowed()
        ensure_disk_space()

    if body.mode not in {"video", "subtitle", "asr"}:
        raise HTTPException(status_code=400, detail="不支援的下載模式")
    if body.mode == "video" and not body.formatId:
        raise HTTPException(status_code=400, detail="請選擇影片畫質")
    if body.mode == "subtitle" and (not body.subtitleLanguage or not body.subtitleFormat):
        raise HTTPException(status_code=400, detail="請選擇字幕語言與格式")
    if body.mode == "asr":
        if not (body.geminiApiKey or "").strip():
            raise HTTPException(status_code=400, detail="請填入 Gemini API Key")
        if not body.subtitleFormat:
            raise HTTPException(status_code=400, detail="請選擇字幕輸出格式")
        loop = asyncio.get_running_loop()
        preferred = body.containerFormat or "webm"
        info = await loop.run_in_executor(
            get_info_executor(),
            lambda: extract_video_info(body.url, preferred_container=preferred),
        )
        if info.subtitles:
            raise HTTPException(
                status_code=400,
                detail="此影片已有字幕，請改用「僅下載字幕」",
            )
        if info.duration and settings.max_asr_duration_seconds > 0 and info.duration > settings.max_asr_duration_seconds:
            minutes = settings.max_asr_duration_seconds // 60
            raise HTTPException(
                status_code=400,
                detail=f"語音辨識僅支援 {minutes} 分鐘以內的影片",
            )

    store = get_task_store()
    # ASR uses user API keys — never dedupe across requests
    if body.mode != "asr":
        fingerprint = download_dedupe_key(
            url=body.url,
            mode=body.mode,
            format_id=body.formatId,
            subtitle_language=body.subtitleLanguage,
            subtitle_format=body.subtitleFormat,
            container_format=body.containerFormat if body.mode == "video" else None,
        )
        existing_id = store.get_dedupe(fingerprint)
        if existing_id:
            existing = store.get(existing_id)
            if _task_still_reusable(existing):
                return CreateDownloadResponse(taskId=existing_id)
    else:
        fingerprint = None

    # Opaque public id (not guessable from url+format)
    task_id = str(uuid.uuid4())
    acquire_ip_slot(ip, task_id)

    hint = None
    if body.mode == "subtitle":
        hint = f"subtitle.{body.subtitleLanguage}.{body.subtitleFormat}"
    elif body.mode == "asr":
        hint = f"asr.{body.asrLanguage or 'zh'}.{body.subtitleFormat}"

    try:
        create_pending_task(task_id, filename_hint=hint, fingerprint=fingerprint)
        if fingerprint:
            store.set_dedupe(fingerprint, task_id, settings.task_ttl_seconds)
        # Strip key from anything that might get logged via repr of body later:
        # worker receives body in-memory only.
        background_tasks.add_task(run_download_job, task_id, body, ip)
    except Exception:
        from app.services.concurrency import release_ip_slot

        release_ip_slot(ip, task_id)
        raise

    return CreateDownloadResponse(taskId=task_id)
