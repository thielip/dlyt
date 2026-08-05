import os

from fastapi import APIRouter

from app.config import get_settings
from app.schemas import HealthResponse
from app.services.canary import get_canary_status
from app.services.egress import get_monthly_outbound
from app.services.task_store import get_task_store

router = APIRouter(tags=["health"])


def _warp_status(settings) -> str:
    flag = (os.environ.get("WARP_STATUS") or "").strip()
    if flag == "1":
        return "on"
    if flag == "0":
        return "off"
    if (settings.ytdlp_proxy or "").strip():
        return "proxy"
    return "off"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    store = get_task_store()
    ytdlp, detail = get_canary_status()
    used = get_monthly_outbound()
    limit = settings.max_monthly_outbound_bytes
    proxy = (settings.ytdlp_proxy or "").strip() or None
    return HealthResponse(
        status="maintenance" if settings.maintenance_mode else "ok",
        redis=store.ping(),
        ytdlp=ytdlp,
        ytdlpDetail=detail or None,
        outboundUsedBytes=used,
        outboundLimitBytes=limit,
        egressExhausted=used >= limit,
        maintenance=settings.maintenance_mode,
        warp=_warp_status(settings),
        ytdlpProxy=proxy,
    )
