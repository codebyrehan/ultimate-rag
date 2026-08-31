"""Authentication: password hashing and JWT token management.

Uses ``passlib`` (PBKDF2-SHA256 backend — no bcrypt binary required) for
password hashing and ``python-jose`` for HS256 JWT issuance/verification.
Both fall back gracefully: if a provider is misconfigured the operations
raise :class:`JWTError` / :class:`InvalidToken` which callers translate into
HTTP 401.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

_TOKEN_TTL_DEFAULT = 3600


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


@dataclass
class TokenPayload:
    """Decoded JWT claims."""

    sub: str  # user id
    tenant_id: str
    exp: int
    iat: int
    email: str | None = None
    is_superuser: bool = False


class TokenError(Exception):
    """Raised when a token is missing, malformed, or expired."""


def create_access_token(
    user_id: str,
    tenant_id: str,
    email: str | None = None,
    secret_key: str | None = None,
    algorithm: str | None = None,
    expires_seconds: int | None = None,
) -> str:
    from jose import jwt

    from ultimate_rag.core.config import get_settings

    settings = get_settings()
    if secret_key is None:
        secret_key = settings.secret_key.get_secret_value()
    if algorithm is None:
        algorithm = settings.jwt_algorithm
    if expires_seconds is None:
        expires_seconds = settings.jwt_expire_seconds

    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "is_superuser": False,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def create_refresh_token(
    user_id: str,
    tenant_id: str,
    secret_key: str | None = None,
    expires_seconds: int | None = None,
) -> str:
    """Create a long-lived refresh token with a ``refresh`` type claim."""
    from jose import jwt

    from ultimate_rag.core.config import get_settings

    settings = get_settings()
    if secret_key is None:
        secret_key = settings.secret_key.get_secret_value()
    if expires_seconds is None:
        expires_seconds = settings.refresh_expire_seconds

    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "token_type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(
    token: str, secret_key: str | None = None, algorithm: str | None = None
) -> TokenPayload:
    from jose import JWTError, jwt

    from ultimate_rag.core.config import get_settings

    settings = get_settings()
    if secret_key is None:
        secret_key = settings.secret_key.get_secret_value()
    if algorithm is None:
        algorithm = settings.jwt_algorithm
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError as exc:
        raise TokenError(str(exc)) from exc

    exp = payload.get("exp", 0)
    if int(time.time()) > int(exp):
        raise TokenError("token expired")

    return TokenPayload(
        sub=payload.get("sub", ""),
        tenant_id=payload.get("tenant_id", ""),
        exp=int(exp),
        iat=int(payload.get("iat", 0)),
        email=payload.get("email"),
        is_superuser=bool(payload.get("is_superuser", False)),
    )


def decode_refresh_token(
    token: str, secret_key: str | None = None, algorithm: str | None = None
) -> TokenPayload:
    """Decode a refresh token. Raises ``TokenError`` if the ``token_type`` claim is not ``refresh``."""
    from jose import JWTError, jwt

    from ultimate_rag.core.config import get_settings

    settings = get_settings()
    if secret_key is None:
        secret_key = settings.secret_key.get_secret_value()
    if algorithm is None:
        algorithm = settings.jwt_algorithm
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError as exc:
        raise TokenError(str(exc)) from exc

    token_type = payload.get("token_type", "access")
    if token_type != "refresh":
        raise TokenError("Not a refresh token")

    exp = payload.get("exp", 0)
    if int(time.time()) > int(exp):
        raise TokenError("token expired")

    return TokenPayload(
        sub=payload.get("sub", ""),
        tenant_id=payload.get("tenant_id", ""),
        exp=int(exp),
        iat=int(payload.get("iat", 0)),
        email=payload.get("email"),
        is_superuser=False,
    )
