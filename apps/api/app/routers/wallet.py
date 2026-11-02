from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.domain import credits
from app.models import CreditTransaction, User, Wallet
from app.schemas import BalanceOut, LedgerEntryOut

router = APIRouter(prefix="/wallet", tags=["créditos"])


@router.get("", response_model=BalanceOut, summary="Saldo disponible y reservado")
def balance(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> BalanceOut:
    available, reserved = credits.get_balance(db, user.id)
    return BalanceOut(available_credits=available, reserved_credits=reserved)


@router.get("/transactions", response_model=list[LedgerEntryOut], summary="Historial de movimientos")
def transactions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[LedgerEntryOut]:
    rows = (
        db.execute(
            select(CreditTransaction)
            .join(Wallet, Wallet.id == CreditTransaction.wallet_id)
            .where(Wallet.user_id == user.id)
            .order_by(CreditTransaction.created_at.desc(), CreditTransaction.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return [
        LedgerEntryOut(
            id=r.id,
            kind=r.kind,
            available_delta=r.available_delta,
            reserved_delta=r.reserved_delta,
            reference_type=r.reference_type,
            reference_id=r.reference_id,
            created_at=r.created_at,
        )
        for r in rows
    ]
