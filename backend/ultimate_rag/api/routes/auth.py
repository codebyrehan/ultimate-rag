"""Authentication routes: tenant-scoped registration and login.

``POST /auth/register`` creates a new tenant + user (self-service onboarding)
and returns a JWT access token. ``POST /auth/login`` validates credentials and
returns a token. Passwords are hashed with PBKDF2-SHA256 (no bcrypt dependency).
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from ultimate_rag.auth.dependencies import CurrentUser
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

logger = logging.getLogger("ultimate_rag.api.routes.auth")
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


class MeResponse(BaseModel):
    user_id: str
    tenant_id: str
    email: str
    full_name: str | None = None


@router.get("/me", response_model=MeResponse)
async def get_current_user(current_user: CurrentUser) -> MeResponse:
    return MeResponse(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        email=current_user.email,
        full_name=getattr(current_user, "full_name", None),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session=Depends(get_session),  # noqa: B008
) -> TokenResponse:
    from sqlalchemy import select

    logger.info("Registration attempt for email=%s tenant=%s", payload.email, payload.tenant_name)
    t_repo = TenantRepository(session)
    stmt = select(Tenant).where(Tenant.name == payload.tenant_name)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = await t_repo.add(Tenant(id=new_id(), name=payload.tenant_name))
        logger.info("Created new tenant=%s", tenant.id)
    u_repo = UserRepository(session)
    existing = await u_repo.get_by_email(tenant.id, payload.email)
    if existing is not None:
        logger.warning(
            "Registration failed: user already exists email=%s tenant=%s",
            payload.email,
            tenant.id,
        )
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
    logger.info("Registration successful user=%s tenant=%s", user.id, tenant.id)
    return TokenResponse(access_token=token, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session=Depends(get_session),  # noqa: B008
) -> TokenResponse:
    from sqlalchemy import select

    logger.info(
        "Login attempt for email=%s tenant=%s",
        payload.email,
        payload.tenant_name,
    )
    stmt = select(Tenant).where(Tenant.name == payload.tenant_name)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()
    if tenant is None:
        logger.warning(
            "Login failed: tenant not found tenant=%s",
            payload.tenant_name,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    u_repo = UserRepository(session)
    user = await u_repo.get_by_email(tenant.id, payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        logger.warning(
            "Login failed: invalid credentials email=%s tenant=%s",
            payload.email,
            tenant.id,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user_id=user.id, tenant_id=tenant.id, email=user.email)
    refresh = create_refresh_token(user_id=user.id, tenant_id=tenant.id)
    logger.info("Login successful user=%s tenant=%s", user.id, tenant.id)
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
