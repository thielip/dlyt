import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, RedirectResponse

from app.config import get_settings
from app.services.egress import add_outbound_bytes
from app.services.task_store import get_task_store

router = APIRouter(prefix="/api", tags=["files"])


def _get_completed(task_id: str):
    task = get_task_store().get(task_id)
    if not task or task.status != "completed":
        raise HTTPException(status_code=404, detail="檔案尚未就緒")
    return task


def _mark_grace_purge(task_id: str) -> None:
    settings = get_settings()
    store = get_task_store()
    task = store.get(task_id)
    if not task or task.purge_after is not None:
        return
    store.update(task_id, purge_after=time.time() + settings.file_grace_seconds)


@router.head("/files/{task_id}")
def head_file(task_id: str) -> Response:
    task = _get_completed(task_id)
    if task.delivery == "redirect" and task.direct_url:
        return Response(
            status_code=200,
            headers={
                "Accept-Ranges": "bytes",
                "X-Delivery": "redirect",
            },
        )
    if not task.file_path:
        raise HTTPException(status_code=404, detail="檔案不存在或已過期")
    path = Path(task.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="檔案不存在或已過期")
    filename = task.filename or path.name
    media_type = "application/octet-stream"
    if path.suffix.lower() in {".srt", ".vtt", ".txt"}:
        media_type = "text/plain; charset=utf-8"
    return Response(
        status_code=200,
        media_type=media_type,
        headers={
            "Content-Length": str(path.stat().st_size),
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Accept-Ranges": "bytes",
            "X-Delivery": "proxy",
        },
    )


@router.get("/files/{task_id}")
def get_file(task_id: str):
    task = _get_completed(task_id)

    # Direct CDN/googlevideo URL — zero Render egress for payload
    if task.delivery == "redirect" and task.direct_url:
        _mark_grace_purge(task_id)
        return RedirectResponse(url=task.direct_url, status_code=302)

    if not task.file_path:
        raise HTTPException(status_code=404, detail="檔案不存在或已過期")
    path = Path(task.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="檔案不存在或已過期")

    filename = task.filename or path.name
    media_type = "application/octet-stream"
    if path.suffix.lower() in {".srt", ".vtt", ".txt"}:
        media_type = "text/plain; charset=utf-8"

    size = path.stat().st_size
    add_outbound_bytes(size)
    _mark_grace_purge(task_id)

    return FileResponse(
        path=path,
        media_type=media_type,
        filename=filename,
    )
