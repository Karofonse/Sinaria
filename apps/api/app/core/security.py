"""Hash de contraseñas (scrypt, stdlib), JWT de sesión y firmas de URL de descarga."""

import base64
import hashlib
import hmac
import secrets
import time
import uuid
from dataclasses import dataclass

import jwt

from app.core.config import get_settings

# Parámetros scrypt explícitos (OWASP: N=2^17 es el recomendado; 2^14 es el mínimo aceptable para
# un entorno con latencia de login controlada). Se sube en la fase de hardening.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Hash ficticio para igualar el coste de tiempo cuando el usuario no existe.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    jti: str


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + settings.jwt_ttl_minutes * 60,
        "jti": secrets.token_urlsafe(12),
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> TokenClaims:
    """Lanza jwt.PyJWTError si el token no es válido o ha expirado."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],
        options={"require": ["exp", "sub", "iat"]},
    )
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("tipo de token inesperado")
    return TokenClaims(user_id=uuid.UUID(payload["sub"]), jti=payload.get("jti", ""))


def sign_download(track_id: uuid.UUID, owner_id: uuid.UUID, expires_at: int) -> str:
    """Firma HMAC que liga pista, propietario y caducidad."""
    settings = get_settings()
    message = f"{track_id}:{owner_id}:{expires_at}".encode()
    return hmac.new(settings.download_url_secret.encode(), message, hashlib.sha256).hexdigest()


def verify_download(track_id: uuid.UUID, owner_id: uuid.UUID, expires_at: int, signature: str) -> bool:
    if expires_at < int(time.time()):
        return False
    expected = sign_download(track_id, owner_id, expires_at)
    return hmac.compare_digest(expected, signature)
