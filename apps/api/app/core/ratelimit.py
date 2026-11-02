"""Límite de peticiones por ventana fija sobre Redis.

Si Redis no responde se permite la petición y se registra un aviso: la disponibilidad
de la API no depende de la protección anti-abuso, pero el incidente queda registrado.
"""

import logging
import time

from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.queue import get_redis

logger = logging.getLogger(__name__)


def _hit(bucket: str, identity: str, limit: int, window_s: int = 60) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    window = int(time.time()) // window_s
    key = f"rl:{bucket}:{identity}:{window}"
    try:
        r = get_redis()
        count = r.incr(key)
        if count == 1:
            r.expire(key, window_s + 5)
    except Exception:  # noqa: BLE001 - fallo de infraestructura: se permite y se registra
        logger.warning("rate_limit_backend_unavailable", extra={"bucket": bucket})
        return
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Inténtalo de nuevo en un minuto.",
            headers={"Retry-After": str(window_s)},
        )


def limit_by_ip(bucket: str, limit: int):
    def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        _hit(bucket, ip, limit)

    return dependency


def limit_by_user(bucket: str, limit: int, user_id: str) -> None:
    _hit(bucket, user_id, limit)
