import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.ratelimit import limit_by_ip
from app.core.security import DUMMY_PASSWORD_HASH, create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.deps import get_current_user, user_role_names
from app.models import Role, User, UserRole, Wallet
from app.schemas import LoginIn, RegisterIn, UserOut

router = APIRouter(prefix="/auth", tags=["autenticación"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        locale=user.locale,
        status=user.status,
        roles=user_role_names(user),
        created_at=user.created_at,
    )


def _set_session(response: Response, user_id: uuid.UUID) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=create_access_token(user_id),
        max_age=settings.jwt_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserOut,
    dependencies=[Depends(limit_by_ip("auth", get_settings().rate_limit_auth_per_minute))],
    summary="Crear cuenta y sesión",
)
def register(payload: RegisterIn, response: Response, db: Session = Depends(get_db)) -> UserOut:
    role = db.execute(select(Role).where(Role.name == "user")).scalar_one()
    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        locale=payload.locale,
        status="active",
    )
    db.add(user)
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.add(Wallet(id=uuid.uuid4(), user_id=user.id, available_credits=0, reserved_credits=0))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "email_taken", "message": "No se pudo crear la cuenta con ese correo."},
        )
    user = db.execute(
        select(User).options(selectinload(User.roles).selectinload(UserRole.role)).where(User.id == user.id)
    ).scalar_one()
    _set_session(response, user.id)
    return _user_out(user)


@router.post(
    "/login",
    response_model=UserOut,
    dependencies=[Depends(limit_by_ip("auth", get_settings().rate_limit_auth_per_minute))],
    summary="Iniciar sesión",
)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)) -> UserOut:
    user = db.execute(
        select(User).options(selectinload(User.roles).selectinload(UserRole.role)).where(User.email == payload.email)
    ).scalar_one_or_none()
    # Se verifica siempre una contraseña para no revelar por tiempo si el correo existe.
    valid = verify_password(payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if user is None or not valid:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Correo o contraseña incorrectos."},
        )
    if user.status != "active":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail={"code": "account_suspended", "message": "Cuenta suspendida."}
        )
    _set_session(response, user.id)
    return _user_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Cerrar sesión")
def logout(response: Response) -> Response:
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut, summary="Usuario actual")
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)
