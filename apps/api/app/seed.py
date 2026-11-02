"""Datos de referencia idempotentes. Ejecutar: `python -m app.seed`.

Los precios son EJEMPLOS para desarrollo: los paquetes se crean INACTIVOS para que no se vendan
hasta que el propietario defina precios reales y se habilite Wompi.
"""

import os
import uuid

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import CreditPackage, ProviderModel, Role, User, UserRole, Wallet

_MODELS = [
    {
        "provider": "mock",
        "model_key": "mock-music-small",
        "display_name": "Mock Music (desarrollo)",
        "enabled": True,
        "min_duration_s": 1,
        "max_duration_s": 120,
        "credits_per_generation": 1,
        "supports_seed": True,
        "supports_negative_prompt": True,
        "output_format": "wav",
    },
    {
        # Fila de referencia: deshabilitada hasta verificar la API oficial de fal.ai.
        "provider": "fal",
        "model_key": "stable-audio-3-small-music",
        "display_name": "Stable Audio 3 Small (fal.ai)",
        "enabled": False,
        "min_duration_s": 1,
        "max_duration_s": 120,
        "credits_per_generation": 10,
        "supports_seed": True,
        "supports_negative_prompt": False,
        "output_format": "mp3",
    },
]

_PACKAGES = [
    {"code": "ejemplo-100", "name": "Ejemplo 100 créditos", "credits": 100, "price_cop_cents": 1_000_000},
]


def seed_reference_data() -> None:
    with SessionLocal() as db:
        for role_name in ("user", "admin", "support"):
            if db.execute(select(Role).where(Role.name == role_name)).scalar_one_or_none() is None:
                db.add(Role(name=role_name))
        db.flush()
        for spec in _MODELS:
            exists = db.execute(
                select(ProviderModel).where(
                    ProviderModel.provider == spec["provider"], ProviderModel.model_key == spec["model_key"]
                )
            ).scalar_one_or_none()
            if exists is None:
                db.add(ProviderModel(id=uuid.uuid4(), **spec))
        for spec in _PACKAGES:
            if db.execute(select(CreditPackage).where(CreditPackage.code == spec["code"])).scalar_one_or_none() is None:
                db.add(CreditPackage(id=uuid.uuid4(), active=False, **spec))
        db.commit()


def create_admin_from_env() -> None:
    """Crea o promueve un administrador usando SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD."""
    email = os.environ.get("SEED_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("SEED_ADMIN_PASSWORD", "")
    if not email or not password:
        return
    if len(password) < 10:
        raise SystemExit("SEED_ADMIN_PASSWORD debe tener al menos 10 caracteres")
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            user = User(
                id=uuid.uuid4(),
                email=email,
                password_hash=hash_password(password),
                display_name="Administrador",
                locale="es",
            )
            db.add(user)
            db.flush()
            db.add(Wallet(id=uuid.uuid4(), user_id=user.id, available_credits=0, reserved_credits=0))
        admin_role = db.execute(select(Role).where(Role.name == "admin")).scalar_one()
        already = db.execute(
            select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == admin_role.id)
        ).scalar_one_or_none()
        if already is None:
            db.add(UserRole(user_id=user.id, role_id=admin_role.id))
        db.commit()


if __name__ == "__main__":
    seed_reference_data()
    create_admin_from_env()
    print("seed ok")
