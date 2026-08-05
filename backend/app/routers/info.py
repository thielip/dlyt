import asyncio

from fastapi import APIRouter, Request

from app.schemas import InfoRequest, VideoInfo
from app.services.executors import get_info_executor
from app.services.rate_limit import client_ip, enforce_rate_limit
from app.services.turnstile import verify_turnstile
from app.services.ytdlp_service import extract_video_info

router = APIRouter(prefix="/api", tags=["info"])


@router.post("/info", response_model=VideoInfo)
async def post_info(body: InfoRequest, request: Request) -> VideoInfo:
    enforce_rate_limit(request)
    await verify_turnstile(body.turnstileToken, client_ip(request))
    loop = asyncio.get_running_loop()
    preferred = body.preferredContainer or "webm"
    return await loop.run_in_executor(
        get_info_executor(),
        lambda: extract_video_info(body.url, preferred_container=preferred),
    )
