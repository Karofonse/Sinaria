"""Presupuestos diarios (global y por usuario), medidos en créditos reservados por generaciones creadas hoy (UTC).

Se cuentan todas las generaciones del día, incluidas las fallidas: el coste del proveedor pudo haberse
incurrido. La comprobación se hace bajo un bloqueo consultivo para serializar las creaciones.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BudgetExceeded
from app.models import GenerationJob

_GLOBAL_BUDGET_LOCK = 718_201


def start_of_day_utc() -> datetime:
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def assert_within_budget(db: Session, user_id: uuid.UUID, cost: int) -> None:
    settings = get_settings()
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _GLOBAL_BUDGET_LOCK})
    since = start_of_day_utc()

    global_used = db.execute(
        select(func.coalesce(func.sum(GenerationJob.reserved_credits), 0)).where(GenerationJob.created_at >= since)
    ).scalar_one()
    if global_used + cost > settings.daily_global_credit_budget:
        raise BudgetExceeded("Presupuesto diario global agotado. Inténtalo mañana.")

    user_used = db.execute(
        select(func.coalesce(func.sum(GenerationJob.reserved_credits), 0)).where(
            GenerationJob.user_id == user_id, GenerationJob.created_at >= since
        )
    ).scalar_one()
    if user_used + cost > settings.user_daily_credit_limit:
        raise BudgetExceeded("Has alcanzado tu límite diario de generaciones.")
