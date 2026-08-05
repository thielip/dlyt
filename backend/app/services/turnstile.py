from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException

from app.config import get_settings

logger = logging.getLogger(__name__)


async def verify_turnstile(token: str | None, ip: str) -> None:
    settings = get_settings()
    secret = settings.turnstile_secret_key
    if not secret:
        return
    if settings.turnstile_required and not token:
        raise HTTPException(status_code=400, detail="請完成人機驗證")
    if not token:
        # Secret configured but not required → still prefer token when present
        if settings.turnstile_required:
            raise HTTPException(status_code=400, detail="請完成人機驗證")
        return

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": secret, "response": token, "remoteip": ip},
            )
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("turnstile verify error: %s", exc)
        raise HTTPException(status_code=503, detail="人機驗證服務暫時不可用") from exc

    if not data.get("success"):
        raise HTTPException(status_code=400, detail="人機驗證失敗，請重試")
