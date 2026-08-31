"""FastAPI dependencies for authenticated routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ultimate_rag.auth.session import TokenError, decode_access_token
from ultimate_rag.db.connection import get_session
from ultimate_rag.db.models import User
from ultimate_rag.db.repositories.users import UserRepository

bearer = HTTPBearer(auto_error=False)


def extract_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),  # noqa: B008
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def get_current_user(
    token: str = Depends(extract_token),
    session=Depends(get_session),  # noqa: B008
) -> User:
    from ultimate_rag.auth.session import TokenPayload

    try:
        payload: TokenPayload = decode_access_token(token)
    except TokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    repo = UserRepository(session)
    user = await repo.get(payload.tenant_id, payload.sub)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
