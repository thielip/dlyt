from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import HTTPException

from app.config import get_settings


def ensure_disk_space() -> None:
    settings = get_settings()
    path = Path(settings.tmp_dir)
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    if usage.free < settings.min_free_disk_bytes:
        raise HTTPException(
            status_code=503,
            detail="伺服器暫存空間不足，請稍後再試",
        )


def free_bytes() -> int:
    settings = get_settings()
    path = Path(settings.tmp_dir)
    path.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(path).free
