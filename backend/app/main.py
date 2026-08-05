from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import get_settings
from app.logging_config import setup_logging
from app.middleware import MaintenanceMiddleware, SecurityHeadersMiddleware
from app.routers import download, files, health, info, stats, tasks
from app.services.canary import recover_interrupted_tasks, warmup_canary
from app.services.cleanup import cleanup_loop
from app.services.concurrency import init_download_semaphore
from app.services.executors import init_executors, shutdown_executors
from app.services.task_store import init_task_store
from app.services.ttl_cache import init_ttl_cache

logger = logging.getLogger(__name__)


def _init_sentry(dsn: str | None) -> None:
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(dsn=dsn, integrations=[FastApiIntegration()], traces_sample_rate=0.0)
        logger.info("Sentry enabled")
    except Exception:  # noqa: BLE001
        logger.warning("Sentry init failed; continuing without it")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(json_logs=settings.log_json)
    _init_sentry(settings.sentry_dsn)

    Path(settings.tmp_dir).mkdir(parents=True, exist_ok=True)
    init_task_store(settings)
    init_ttl_cache(settings)
    init_download_semaphore()
    init_executors()

    recovered = recover_interrupted_tasks()
    if recovered:
        logger.info("Marked %s interrupted tasks as failed", recovered)

    stop_event = asyncio.Event()
    cleanup_task = asyncio.create_task(cleanup_loop(stop_event))
    canary_task = asyncio.create_task(warmup_canary())
    app.state.cleanup_stop = stop_event
    app.state.cleanup_task = cleanup_task
    app.state.canary_task = canary_task
    try:
        yield
    finally:
        stop_event.set()
        cleanup_task.cancel()
        canary_task.cancel()
        for t in (cleanup_task, canary_task):
            try:
                await t
            except asyncio.CancelledError:
                pass
        shutdown_executors()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MaintenanceMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

    origins = settings.cors_origin_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["*"],
        allow_credentials=bool(origins),
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Retry-After", "X-Delivery"],
    )

    app.include_router(health.router)
    app.include_router(info.router)
    app.include_router(download.router)
    app.include_router(tasks.router)
    app.include_router(files.router)
    app.include_router(stats.router)
    return app


app = create_app()
