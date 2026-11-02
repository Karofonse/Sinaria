"""Libro mayor de créditos.

Reglas:
- Toda operación de saldo toma un bloqueo de fila sobre la billetera (SELECT ... FOR UPDATE)
  antes de leer o escribir. Dos operaciones sobre el mismo usuario se serializan.
- Cada movimiento tiene una clave de idempotencia única. Repetir una operación ya aplicada
  no cambia nada y devuelve `False`.
- La BD rechaza saldos negativos (CHECK) y movimientos mal formados (CHECK por tipo).
  Estas comprobaciones en Python son una validación previa, no la única barrera.
- Nunca se modifica ni borra un movimiento: las correcciones son movimientos nuevos.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import InsufficientCredits, LedgerInvariantError
from app.models import CreditTransaction, Wallet


def _lock_wallet(db: Session, user_id: uuid.UUID) -> Wallet:
    """Obtiene la billetera del usuario con bloqueo de fila, creándola si no existe."""
    db.execute(
        insert(Wallet)
        .values(id=uuid.uuid4(), user_id=user_id, available_credits=0, reserved_credits=0)
        .on_conflict_do_nothing(index_elements=[Wallet.user_id])
    )
    wallet = db.execute(select(Wallet).where(Wallet.user_id == user_id).with_for_update()).scalar_one()
    return wallet


def get_balance(db: Session, user_id: uuid.UUID) -> tuple[int, int]:
    wallet = db.execute(select(Wallet).where(Wallet.user_id == user_id)).scalar_one_or_none()
    if wallet is None:
        return 0, 0
    return wallet.available_credits, wallet.reserved_credits


def _post(
    db: Session,
    user_id: uuid.UUID,
    *,
    kind: str,
    available_delta: int,
    reserved_delta: int,
    idempotency_key: str,
    reference_type: str | None = None,
    reference_id: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Aplica un movimiento. Devuelve True si se aplicó, False si ya existía (reintento idempotente)."""
    wallet = _lock_wallet(db, user_id)

    already = db.execute(
        select(CreditTransaction.id).where(CreditTransaction.idempotency_key == idempotency_key)
    ).scalar_one_or_none()
    if already is not None:
        return False

    new_available = wallet.available_credits + available_delta
    new_reserved = wallet.reserved_credits + reserved_delta
    if new_available < 0:
        raise InsufficientCredits("Saldo insuficiente para completar la operación.")
    if new_reserved < 0:
        # Un consumo o liberación sin reserva previa indica un error de flujo, no del usuario.
        raise LedgerInvariantError(f"Reserva insuficiente para {kind} ({idempotency_key})")

    wallet.available_credits = new_available
    wallet.reserved_credits = new_reserved
    db.add(
        CreditTransaction(
            wallet_id=wallet.id,
            kind=kind,
            available_delta=available_delta,
            reserved_delta=reserved_delta,
            idempotency_key=idempotency_key,
            reference_type=reference_type,
            reference_id=reference_id,
            actor_user_id=actor_user_id,
            reason=reason,
            metadata_=metadata or {},
        )
    )
    db.flush()
    return True


def grant_purchase(db: Session, user_id: uuid.UUID, credits: int, idempotency_key: str, reference_id: str) -> bool:
    """Acredita créditos comprados. Solo debe llamarse desde el webhook verificado de pagos."""
    return _post(
        db,
        user_id,
        kind="purchase",
        available_delta=credits,
        reserved_delta=0,
        idempotency_key=idempotency_key,
        reference_type="payment",
        reference_id=reference_id,
    )


def reserve(db: Session, user_id: uuid.UUID, amount: int, job_id: uuid.UUID) -> bool:
    return _post(
        db,
        user_id,
        kind="reserve",
        available_delta=-amount,
        reserved_delta=amount,
        idempotency_key=f"reserve:{job_id}",
        reference_type="generation_job",
        reference_id=str(job_id),
    )


def consume(db: Session, user_id: uuid.UUID, amount: int, job_id: uuid.UUID) -> bool:
    return _post(
        db,
        user_id,
        kind="consume",
        available_delta=0,
        reserved_delta=-amount,
        idempotency_key=f"consume:{job_id}",
        reference_type="generation_job",
        reference_id=str(job_id),
    )


def release(db: Session, user_id: uuid.UUID, amount: int, job_id: uuid.UUID) -> bool:
    return _post(
        db,
        user_id,
        kind="release",
        available_delta=amount,
        reserved_delta=-amount,
        idempotency_key=f"release:{job_id}",
        reference_type="generation_job",
        reference_id=str(job_id),
    )


def admin_adjust(
    db: Session,
    user_id: uuid.UUID,
    delta: int,
    *,
    idempotency_key: str,
    actor_user_id: uuid.UUID,
    reason: str,
) -> bool:
    if delta == 0:
        raise LedgerInvariantError("El ajuste no puede ser cero")
    return _post(
        db,
        user_id,
        kind="adjustment",
        available_delta=delta,
        reserved_delta=0,
        idempotency_key=idempotency_key,
        reference_type="admin",
        reference_id=str(actor_user_id),
        actor_user_id=actor_user_id,
        reason=reason,
    )


def is_duplicate_error(exc: IntegrityError) -> bool:
    """Un error de unicidad sobre idempotency_key significa que otra petición ganó la carrera."""
    text = str(exc.orig) if exc.orig else str(exc)
    return "idempotency_key" in text or "uq_" in text or "unique" in text.lower()
