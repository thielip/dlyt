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
    info_workers: int = 4

    info_cache_ttl_seconds: int = 300  # reuse extract for download start (URLs stay valid)
    fail_cache_ttl_seconds: int = 45

    canary_url: str = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    sentry_dsn: str | None = None
    log_json: bool = True

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
