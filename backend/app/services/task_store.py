from __future__ import annotations

import json
import threading
import time
from typing import Any

from app.config import Settings, get_settings
from app.schemas import TaskProgress
from app.services.redis_meter import note_redis_commands, redis_degraded


class TaskStore:
    def create(self, task: TaskProgress) -> TaskProgress: ...
    def get(self, task_id: str) -> TaskProgress | None: ...
    def update(self, task_id: str, **fields: Any) -> TaskProgress | None: ...
    def delete(self, task_id: str) -> None: ...
    def list_ids(self) -> list[str]: ...
    def ping(self) -> str: ...
    def get_dedupe(self, fingerprint: str) -> str | None: ...
    def set_dedupe(self, fingerprint: str, task_id: str, ttl: int) -> None: ...


class MemoryTaskStore(TaskStore):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, dict[str, Any]] = {}
        self._dedupe: dict[str, str] = {}

    def create(self, task: TaskProgress) -> TaskProgress:
        now = time.time()
        data = task.model_dump()
        data["created_at"] = now
        data["updated_at"] = now
        with self._lock:
            self._tasks[task.taskId] = data
        return TaskProgress.model_validate(data)

    def get(self, task_id: str) -> TaskProgress | None:
        with self._lock:
            data = self._tasks.get(task_id)
        return TaskProgress.model_validate(data) if data else None

    def update(self, task_id: str, **fields: Any) -> TaskProgress | None:
        with self._lock:
            data = self._tasks.get(task_id)
            if not data:
                return None
            data.update(fields)
            data["updated_at"] = time.time()
            self._tasks[task_id] = data
            return TaskProgress.model_validate(data)

    def delete(self, task_id: str) -> None:
        with self._lock:
            self._tasks.pop(task_id, None)

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._tasks.keys())

    def ping(self) -> str:
        return "memory"

    def get_dedupe(self, fingerprint: str) -> str | None:
        with self._lock:
            return self._dedupe.get(fingerprint)

    def set_dedupe(self, fingerprint: str, task_id: str, ttl: int) -> None:
        with self._lock:
            self._dedupe[fingerprint] = task_id


class RedisTaskStore(TaskStore):
    def __init__(self, redis_url: str, ttl_seconds: int) -> None:
        import redis

        self._ttl = ttl_seconds
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._prefix = "dlyt:task:"
        self._dedupe_prefix = "dlyt:dedupe:"

    def _key(self, task_id: str) -> str:
        return f"{self._prefix}{task_id}"

    def _touch(self, n: int = 1) -> None:
        note_redis_commands(n)

    def create(self, task: TaskProgress) -> TaskProgress:
        now = time.time()
        data = task.model_dump()
        data["created_at"] = now
        data["updated_at"] = now
        self._touch()
        self._client.set(self._key(task.taskId), json.dumps(data), ex=self._ttl)
        return TaskProgress.model_validate(data)

    def get(self, task_id: str) -> TaskProgress | None:
        self._touch()
        raw = self._client.get(self._key(task_id))
        if not raw:
            return None
        return TaskProgress.model_validate(json.loads(raw))

    def update(self, task_id: str, **fields: Any) -> TaskProgress | None:
        self._touch()
        raw = self._client.get(self._key(task_id))
        if not raw:
            return None
        data = json.loads(raw)
        data.update(fields)
        data["updated_at"] = time.time()
        self._touch()
        self._client.set(self._key(task_id), json.dumps(data), ex=self._ttl)
        return TaskProgress.model_validate(data)

    def delete(self, task_id: str) -> None:
        self._touch()
        self._client.delete(self._key(task_id))

    def list_ids(self) -> list[str]:
        self._touch()
        keys = self._client.keys(f"{self._prefix}*")
        return [k.removeprefix(self._prefix) for k in keys]

    def ping(self) -> str:
        self._touch()
        self._client.ping()
        if redis_degraded():
            return "redis-degraded"
        return "redis"

    def get_dedupe(self, fingerprint: str) -> str | None:
        self._touch()
        return self._client.get(f"{self._dedupe_prefix}{fingerprint}")

    def set_dedupe(self, fingerprint: str, task_id: str, ttl: int) -> None:
        self._touch()
        self._client.set(f"{self._dedupe_prefix}{fingerprint}", task_id, ex=ttl)


_store: TaskStore | None = None
_memory_fallback: MemoryTaskStore | None = None


def init_task_store(settings: Settings | None = None) -> TaskStore:
    global _store, _memory_fallback
    settings = settings or get_settings()
    _memory_fallback = MemoryTaskStore()
    if settings.redis_url:
        try:
            store = RedisTaskStore(settings.redis_url, settings.task_ttl_seconds)
            store.ping()
            _store = store
            return store
        except Exception:
            pass
    _store = _memory_fallback
    return _store


def get_task_store() -> TaskStore:
    global _store
    if _store is None:
        return init_task_store()
    return _store
