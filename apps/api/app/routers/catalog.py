from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.deps import get_current_user
from app.models import CreditPackage, ProviderModel, User
from app.schemas import PackageOut, ProviderModelOut

router = APIRouter(tags=["catálogo"])


@router.get("/catalog/models", response_model=list[ProviderModelOut], summary="Modelos de generación habilitados")
def list_models(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[ProviderModelOut]:
    rows = (
        db.execute(select(ProviderModel).where(ProviderModel.enabled.is_(True)).order_by(ProviderModel.display_name))
        .scalars()
        .all()
    )
    return [ProviderModelOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/catalog/packages", response_model=list[PackageOut], summary="Paquetes de créditos a la venta")
def list_packages(db: Session = Depends(get_db)) -> list[PackageOut]:
    rows = (
        db.execute(select(CreditPackage).where(CreditPackage.active.is_(True)).order_by(CreditPackage.credits))
        .scalars()
        .all()
    )
    return [PackageOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/billing/checkout", summary="Iniciar compra de créditos (deshabilitado hasta autorización)")
def checkout(_: User = Depends(get_current_user)) -> None:
    if not get_settings().payments_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "payments_disabled", "message": "Los pagos aún no están habilitados."},
        )
    # Integración Wompi pendiente de credenciales sandbox y verificación de la documentación oficial.
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail={"code": "not_implemented", "message": "Pendiente."})
