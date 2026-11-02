from fastapi import APIRouter
from sqlalchemy import text

from app.core.queue import get_redis
from app.db.session import SessionLocal

router = APIRouter(tags=["salud"])


@router.get("/health", summary="Liveness: el proceso responde")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness: BD y Redis disponibles")
def ready() -> dict[str, object]:
    checks: dict[str, str] = {}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001
        checks["database"] = "error"
    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except Exception:  # noqa: BLE001
        checks["redis"] = "error"
    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
