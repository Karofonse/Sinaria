"""Dependencias FastAPI: autenticación y autorización por rol. Todas las comprobaciones son del servidor."""

import uuid
from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    settings = get_settings()
    token = creds.credentials if creds else request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail={"code": "unauthenticated", "message": "Inicia sesión."}
        )
    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail={"code": "unauthenticated", "message": "Sesión no válida."}
        )

    user = db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == claims.user_id)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail={"code": "unauthenticated", "message": "Sesión no válida."}
        )
    if user.status != "active":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail={"code": "account_suspended", "message": "Cuenta suspendida."}
        )
    return user


def user_role_names(user: User) -> list[str]:
    return sorted(ur.role.name for ur in user.roles)


def require_role(role: str) -> Callable[..., User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if role not in user_role_names(user):
            # 403 genérico: no revela qué rol existe ni cuál falta.
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "forbidden", "message": "Sin permiso."})
        return user

    return dependency


def parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "No encontrado."}
        ) from exc
