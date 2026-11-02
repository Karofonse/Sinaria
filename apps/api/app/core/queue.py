"""Cola de trabajos sobre Redis (LPUSH / BRPOP)."""

import uuid
from functools import lru_cache

import redis

from app.core.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    # socket_timeout debe superar el timeout de BRPOP (5 s), o el worker se cae en espera normal.
    return redis.Redis.from_url(
        get_settings().redis_url, socket_timeout=15, socket_connect_timeout=5, decode_responses=True
    )


def enqueue_job(job_id: uuid.UUID) -> None:
    get_redis().lpush(get_settings().queue_name, str(job_id))


def dequeue_job(timeout_s: int = 5) -> uuid.UUID | None:
    item = get_redis().brpop(get_settings().queue_name, timeout=timeout_s)
    if item is None:
        return None
    return uuid.UUID(item[1])
