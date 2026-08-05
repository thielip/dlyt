from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.config import get_settings

_info_pool: ThreadPoolExecutor | None = None
_download_pool: ThreadPoolExecutor | None = None


def init_executors() -> None:
    global _info_pool, _download_pool
    settings = get_settings()
    if _info_pool is None:
        _info_pool = ThreadPoolExecutor(
            max_workers=max(2, settings.info_workers),
            thread_name_prefix="dlyt-info",
        )
    if _download_pool is None:
        _download_pool = ThreadPoolExecutor(
            max_workers=max(2, settings.max_concurrent_downloads + 1),
            thread_name_prefix="dlyt-dl",
        )


def get_info_executor() -> ThreadPoolExecutor:
    if _info_pool is None:
        init_executors()
    assert _info_pool is not None
    return _info_pool


def get_download_executor() -> ThreadPoolExecutor:
    if _download_pool is None:
        init_executors()
    assert _download_pool is not None
    return _download_pool


def shutdown_executors() -> None:
    global _info_pool, _download_pool
    if _info_pool is not None:
        _info_pool.shutdown(wait=False, cancel_futures=True)
        _info_pool = None
    if _download_pool is not None:
        _download_pool.shutdown(wait=False, cancel_futures=True)
        _download_pool = None
