from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "dlyt"
    redis_url: str | None = None
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    tmp_dir: str = str(Path.cwd() / "tmp" / "dlyt")
    task_ttl_seconds: int = 3600
    file_ttl_seconds: int = 1800
    file_grace_seconds: int = 300
    max_filesize_bytes: int = 0  # 0 = unlimited (single-file cap disabled)
    max_duration_seconds: int = 0  # 0 = unlimited
    min_free_disk_bytes: int = 200 * 1024 * 1024
    rate_limit_per_minute: int = 30
    public_base_url: str = ""

    max_concurrent_downloads: int = 2
    max_active_tasks_per_ip: int = 2
    download_timeout_seconds: int = 1200  # large proxy merges (4K) need longer
    # MP3 jobs: 0 = wait indefinitely (user prefers long wait over timeout fail).
    mp3_job_timeout_seconds: int = 0
    # ffmpeg convert: 0 = no subprocess timeout (heartbeat still updates UI).
    mp3_convert_timeout_seconds: int = 0
    # Keep downloaded audio / partial MP3 for resume across retries.
    mp3_resume_ttl_seconds: int = 24 * 3600
    info_workers: int = 4

    info_cache_ttl_seconds: int = 300  # reuse extract for download start (URLs stay valid)
    fail_cache_ttl_seconds: int = 45
    # Stop probing extra player clients for captions once this many seconds elapsed.
    # Proxied egress (WARP) makes each client attempt ~15-20s; 0 = no budget.
    extract_budget_seconds: int = 20

    canary_url: str = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    sentry_dsn: str | None = None
    log_json: bool = True

    # yt-dlp egress: socks5://127.0.0.1:1080 when Cloudflare WARP (wireproxy) is up.
    # Empty = direct (datacenter IP; YouTube often bot-blocks). Set by start.sh or override.
    ytdlp_proxy: str | None = None
    enable_warp: bool = True

    # Zero-cost / ops guards
    maintenance_mode: bool = False
    prefer_direct_download: bool = True
    allow_proxy_fallback: bool = True
    # Monthly proxy egress budget — show exhausted modal when used >= this
    max_monthly_outbound_bytes: int = 90 * 1024 * 1024 * 1024  # 90GB
    outbound_soft_ratio: float = 0.70
    outbound_hard_ratio: float = 0.92
    max_proxy_height: int = 1080  # never list 1440/2160 for free tier
    redis_max_commands_per_day: int = 8_000
    turnstile_secret_key: str | None = None
    turnstile_required: bool = False

    # Gemini ASR (user-supplied API key; server has no shared key)
    max_asr_duration_seconds: int = 0  # 0 = unlimited
    asr_timeout_seconds: int = 1800
    gemini_asr_model: str = "gemini-2.5-flash"
    gemini_inline_max_bytes: int = 18 * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def model_post_init(self, __context: object) -> None:
        if self.redis_url is not None and not self.redis_url.strip():
            self.redis_url = None
        if self.sentry_dsn is not None and not self.sentry_dsn.strip():
            self.sentry_dsn = None
        if self.turnstile_secret_key is not None and not self.turnstile_secret_key.strip():
            self.turnstile_secret_key = None
        # Prefer explicit env; start.sh also exports YTDLP_PROXY for the process.
        if self.ytdlp_proxy is not None and not self.ytdlp_proxy.strip():
            self.ytdlp_proxy = None
        if self.ytdlp_proxy is None:
            import os

            env_proxy = (os.environ.get("YTDLP_PROXY") or "").strip()
            if env_proxy:
                self.ytdlp_proxy = env_proxy


@lru_cache
def get_settings() -> Settings:
    return Settings()
