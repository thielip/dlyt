from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request

from app.config import get_settings


def client_ip(request: Request) -> str:
    # Prefer proxy-forwarded client (Render / Vercel → Render)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "unknown"


class TokenBucket:
    """Per-key token bucket; expose retry-after seconds when empty."""

    def __init__(self, rate_per_minute: float, burst: float | None = None) -> None:
        self.rate = max(rate_per_minute, 1.0) / 60.0
        self.burst = burst if burst is not None else max(rate_per_minute, 1.0)
        self._tokens: dict[str, float] = defaultdict(lambda: self.burst)
        self._updated: dict[str, float] = defaultdict(time.time)

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.time()
        last = self._updated[key]
        elapsed = max(0.0, now - last)
        tokens = min(self.burst, self._tokens[key] + elapsed * self.rate)
        if tokens < 1.0:
            self._tokens[key] = tokens
            self._updated[key] = now
            need = 1.0 - tokens
            retry_after = max(1, int(need / self.rate + 0.999))
            return False, retry_after
        self._tokens[key] = tokens - 1.0
        self._updated[key] = now
        return True, 0


_bucket: TokenBucket | None = None


def _get_bucket() -> TokenBucket:
    global _bucket
    if _bucket is None:
        rate = float(get_settings().rate_limit_per_minute)
        _bucket = TokenBucket(rate_per_minute=rate, burst=min(rate, 10.0))
    return _bucket


def enforce_rate_limit(request: Request) -> None:
    ip = client_ip(request)
    ok, retry_after = _get_bucket().allow(ip)
    if not ok:
        raise HTTPException(
            status_code=429,
            detail=f"請求過於頻繁，請 {retry_after} 秒後再試",
            headers={"Retry-After": str(retry_after)},
        )
