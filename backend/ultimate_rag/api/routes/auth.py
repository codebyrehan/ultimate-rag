"""Authentication routes: tenant-scoped registration and login.

``POST /auth/register`` creates a new tenant + user (self-service onboarding)
and returns a JWT access token. ``POST /auth/login`` validates credentials and
returns a token. Passwords are hashed with PBKDF2-SHA256 (no bcrypt dependency).
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from ultimate_rag.auth.session import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from ultimate_rag.core.ids import new_id
from ultimate_rag.db.connection import get_session
from ultimate_rag.db.models import Tenant, User
from ultimate_rag.db.repositories.tenants import TenantRepository
from ultimate_rag.db.repositories.users import UserRepository

router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = None
    tenant_name: str = Field(..., min_length=2, max_length=128)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str
    tenant_name: str = Field(..., min_length=2, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session=Depends(get_session),  # noqa: B008
) -> TokenResponse:
    from sqlalchemy import select

    t_repo = TenantRepository(session)
    stmt = select(Tenant).where(Tenant.name == payload.tenant_name)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = await t_repo.add(Tenant(id=new_id(), name=payload.tenant_name))
    u_repo = UserRepository(session)
    existing = await u_repo.get_by_email(tenant.id, payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists for this tenant",
        )
    user = User(
        id=new_id(),
        tenant_id=tenant.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        is_active=True,
        is_superuser=False,
    )
    await u_repo.add(user)
    await session.commit()
    token = create_access_token(user_id=user.id, tenant_id=tenant.id, email=user.email)
    refresh = create_refresh_token(user_id=user.id, tenant_id=tenant.id)
    return TokenResponse(access_token=token, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session=Depends(get_session),  # noqa: B008
) -> TokenResponse:
    from sqlalchemy import select

    stmt = select(Tenant).where(Tenant.name == payload.tenant_name)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    u_repo = UserRepository(session)
    user = await u_repo.get_by_email(tenant.id, payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user_id=user.id, tenant_id=tenant.id, email=user.email)
    refresh = create_refresh_token(user_id=user.id, tenant_id=tenant.id)
    return TokenResponse(access_token=token, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest) -> TokenResponse:
    try:
        claims = decode_refresh_token(payload.refresh_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc
    token = create_access_token(user_id=claims.sub, tenant_id=claims.tenant_id, email=claims.email)
    new_refresh = create_refresh_token(user_id=claims.sub, tenant_id=claims.tenant_id)
    return TokenResponse(access_token=token, refresh_token=new_refresh)
