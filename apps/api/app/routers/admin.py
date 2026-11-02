import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError, LedgerInvariantError
from app.db.session import get_db
from app.deps import parse_uuid, require_role
from app.domain import credits
from app.domain.budget import start_of_day_utc
from app.models import (
    AdminAuditLog,
    CreditTransaction,
    GenerationJob,
    Payment,
    ProviderModel,
    ProviderUsage,
    User,
    Wallet,
)
from app.schemas import AdminUserOut, CreditAdjustIn, ProviderModelUpdate, SuspendIn

router = APIRouter(prefix="/admin", tags=["administración"])
AdminDep = Depends(require_role("admin"))


def _audit(
    db: Session, actor: User, action: str, target_type: str, target_id: str, before: Any, after: Any, reason: str | None
) -> None:
    db.add(
        AdminAuditLog(
            id=uuid.uuid4(),
            actor_user_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
            reason=reason,
        )
    )


def _user_or_404(db: Session, user_id: str) -> User:
    user = db.get(User, parse_uuid(user_id))
    if user is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Usuario no encontrado."}
        )
    return user


@router.get("/users", response_model=list[AdminUserOut], dependencies=[AdminDep], summary="Listar usuarios")
def list_users(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[AdminUserOut]:
    stmt = select(User)
    if q:
        stmt = stmt.where(User.email.ilike(f"%{q.strip().lower()}%"))
    rows = db.execute(stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return [AdminUserOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/users/{user_id}/wallet", dependencies=[AdminDep], summary="Saldo y movimientos de un usuario")
def user_wallet(user_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = _user_or_404(db, user_id)
    available, reserved = credits.get_balance(db, user.id)
    rows = (
        db.execute(
            select(CreditTransaction)
            .join(Wallet, Wallet.id == CreditTransaction.wallet_id)
            .where(Wallet.user_id == user.id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )
    return {
        "available_credits": available,
        "reserved_credits": reserved,
        "transactions": [
            {
                "id": str(r.id),
                "kind": r.kind,
                "available_delta": r.available_delta,
                "reserved_delta": r.reserved_delta,
                "reason": r.reason,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.post(
    "/users/{user_id}/suspend", response_model=AdminUserOut, dependencies=[AdminDep], summary="Suspender usuario"
)
def suspend_user(
    user_id: str, payload: SuspendIn, db: Session = Depends(get_db), actor: User = Depends(require_role("admin"))
) -> AdminUserOut:
    user = _user_or_404(db, user_id)
    before = {"status": user.status}
    user.status = "suspended"
    _audit(db, actor, "user.suspend", "user", str(user.id), before, {"status": "suspended"}, payload.reason)
    db.commit()
    return AdminUserOut.model_validate(user, from_attributes=True)


@router.post(
    "/users/{user_id}/activate", response_model=AdminUserOut, dependencies=[AdminDep], summary="Reactivar usuario"
)
def activate_user(
    user_id: str, payload: SuspendIn, db: Session = Depends(get_db), actor: User = Depends(require_role("admin"))
) -> AdminUserOut:
    user = _user_or_404(db, user_id)
    before = {"status": user.status}
    user.status = "active"
    _audit(db, actor, "user.activate", "user", str(user.id), before, {"status": "active"}, payload.reason)
    db.commit()
    return AdminUserOut.model_validate(user, from_attributes=True)


@router.post(
    "/users/{user_id}/credit-adjustments", dependencies=[AdminDep], summary="Ajustar créditos (auditado, idempotente)"
)
def adjust_credits(
    user_id: str, payload: CreditAdjustIn, db: Session = Depends(get_db), actor: User = Depends(require_role("admin"))
) -> dict[str, Any]:
    user = _user_or_404(db, user_id)
    key = f"admin-adjust:{payload.idempotency_key}"
    try:
        applied = credits.admin_adjust(
            db,
            user.id,
            payload.delta,
            idempotency_key=key,
            actor_user_id=actor.id,
            reason=payload.reason,
        )
    except LedgerInvariantError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "invalid_request", "message": str(exc)}
        )
    except DomainError as exc:
        db.rollback()
        raise exc.to_http()
    if applied:
        _audit(db, actor, "credits.adjust", "user", str(user.id), None, {"delta": payload.delta}, payload.reason)
    db.commit()
    available, reserved = credits.get_balance(db, user.id)
    return {"applied": applied, "available_credits": available, "reserved_credits": reserved}


@router.get("/generations", dependencies=[AdminDep], summary="Consultar generaciones")
def admin_generations(
    status_filter: str | None = Query(default=None, alias="status", pattern="^(pending|processing|completed|failed)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(GenerationJob)
    if status_filter:
        stmt = stmt.where(GenerationJob.status == status_filter)
    rows = db.execute(stmt.order_by(GenerationJob.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return [
        {
            "id": str(j.id),
            "user_id": str(j.user_id),
            "status": j.status,
            "attempts": j.attempts,
            "reserved_credits": j.reserved_credits,
            "error_code": j.error_code,
            "created_at": j.created_at.isoformat(),
        }
        for j in rows
    ]


@router.get("/payments", dependencies=[AdminDep], summary="Consultar pagos")
def admin_payments(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.execute(select(Payment).order_by(Payment.created_at.desc()).limit(limit)).scalars().all()
    return [
        {
            "id": str(p.id),
            "user_id": str(p.user_id),
            "status": p.status,
            "amount_cop_cents": p.amount_cop_cents,
            "created_at": p.created_at.isoformat(),
        }
        for p in rows
    ]


@router.get("/metrics", dependencies=[AdminDep], summary="Métricas de créditos, costes y fallos")
def metrics(db: Session = Depends(get_db)) -> dict[str, Any]:
    since = start_of_day_utc()
    jobs_by_status = dict(db.execute(select(GenerationJob.status, func.count()).group_by(GenerationJob.status)).all())
    credits_issued = db.execute(
        select(func.coalesce(func.sum(CreditTransaction.available_delta), 0)).where(
            CreditTransaction.kind.in_(["purchase", "grant", "refund"])
            | ((CreditTransaction.kind == "adjustment") & (CreditTransaction.available_delta > 0))
        )
    ).scalar_one()
    credits_consumed = db.execute(
        select(func.coalesce(func.sum(-CreditTransaction.reserved_delta), 0)).where(CreditTransaction.kind == "consume")
    ).scalar_one()
    reserved_now = db.execute(select(func.coalesce(func.sum(Wallet.reserved_credits), 0))).scalar_one()
    usage_by_provider = [
        {
            "provider": row.provider,
            "model_key": row.model_key,
            "completed": row.completed,
            "failed": row.failed,
            "credits_charged": int(row.credits_charged),
            "estimated_cost_micros": int(row.cost),
        }
        for row in db.execute(
            select(
                ProviderUsage.provider,
                ProviderUsage.model_key,
                func.count().filter(ProviderUsage.outcome == "completed").label("completed"),
                func.count().filter(ProviderUsage.outcome == "failed").label("failed"),
                func.sum(ProviderUsage.credits_charged).label("credits_charged"),
                func.sum(ProviderUsage.estimated_cost_micros).label("cost"),
            ).group_by(ProviderUsage.provider, ProviderUsage.model_key)
        ).all()
    ]
    failures = [
        {"error_code": code, "count": n}
        for code, n in db.execute(
            select(GenerationJob.error_code, func.count())
            .where(GenerationJob.status == "failed")
            .group_by(GenerationJob.error_code)
        ).all()
    ]
    today_jobs = db.execute(
        select(func.count(), func.coalesce(func.sum(GenerationJob.reserved_credits), 0)).where(
            GenerationJob.created_at >= since
        )
    ).one()
    return {
        "jobs_by_status": jobs_by_status,
        "credits_issued": int(credits_issued),
        "credits_consumed": int(credits_consumed),
        "credits_reserved_now": int(reserved_now),
        "today": {"jobs": today_jobs[0], "credits_reserved": int(today_jobs[1])},
        "usage_by_provider": usage_by_provider,
        "failures_by_code": failures,
    }


@router.patch(
    "/provider-models/{model_key}", dependencies=[AdminDep], summary="Habilitar/deshabilitar modelo y ajustar precio"
)
def update_model(
    model_key: str,
    payload: ProviderModelUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    model = db.execute(select(ProviderModel).where(ProviderModel.model_key == model_key)).scalar_one_or_none()
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Modelo no encontrado."})
    before = {"enabled": model.enabled, "credits_per_generation": model.credits_per_generation}
    if payload.enabled is not None:
        model.enabled = payload.enabled
    if payload.credits_per_generation is not None:
        model.credits_per_generation = payload.credits_per_generation
    after = {"enabled": model.enabled, "credits_per_generation": model.credits_per_generation}
    _audit(db, actor, "provider_model.update", "provider_model", model.model_key, before, after, payload.reason)
    db.commit()
    return {"model_key": model.model_key, **after}
