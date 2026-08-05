from __future__ import annotations

import json
import threading
import time
from typing import Any

from app.config import Settings, get_settings
from app.services.redis_meter import note_redis_commands, redis_degraded


class TtlCache:
    def get_json(self, key: str) -> Any | None: ...
    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None: ...
    def delete(self, key: str) -> None: ...


class MemoryTtlCache(TtlCache):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, tuple[float, Any]] = {}

    def get_json(self, key: str) -> Any | None:
        now = time.time()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expires, value = item
            if expires < now:
                self._data.pop(key, None)
                return None
            return value

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        with self._lock:
            self._data[key] = (time.time() + ttl_seconds, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


class RedisTtlCache(TtlCache):
    def __init__(self, redis_url: str, memory: MemoryTtlCache) -> None:
        import redis

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._prefix = "dlyt:cache:"
        self._memory = memory

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get_json(self, key: str) -> Any | None:
        if redis_degraded():
            return self._memory.get_json(key)
        try:
            note_redis_commands(1)
            raw = self._client.get(self._key(key))
            if not raw:
                return self._memory.get_json(key)
            return json.loads(raw)
        except Exception:
            return self._memory.get_json(key)

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._memory.set_json(key, value, ttl_seconds)
        if redis_degraded():
            return
        try:
            note_redis_commands(1)
            self._client.set(self._key(key), json.dumps(value), ex=max(1, ttl_seconds))
        except Exception:
            pass

    def delete(self, key: str) -> None:
        self._memory.delete(key)
        if redis_degraded():
            return
        try:
            note_redis_commands(1)
            self._client.delete(self._key(key))
        except Exception:
            pass


_cache: TtlCache | None = None
_memory: MemoryTtlCache | None = None


def init_ttl_cache(settings: Settings | None = None) -> TtlCache:
    global _cache, _memory
    settings = settings or get_settings()
    _memory = MemoryTtlCache()
    if settings.redis_url:
        try:
            cache = RedisTtlCache(settings.redis_url, _memory)
            cache.set_json("__ping__", {"ok": True}, 5)
            _cache = cache
            return cache
        except Exception:
            pass
    _cache = _memory
    return _cache


def get_ttl_cache() -> TtlCache:
    global _cache
    if _cache is None:
        return init_ttl_cache()
    return _cache
