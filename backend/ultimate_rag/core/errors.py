from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse


class RAGError(Exception):
    """Base error for the platform."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str = "", details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFound(RAGError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class Conflict(RAGError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class Forbidden(RAGError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class Unauthorized(RAGError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class ValidationError(RAGError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"


class ProviderError(RAGError):
    """Raised when a pluggable provider (LLM/embedding/vector) fails."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "provider_error"


class RateLimitExceeded(RAGError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limit_exceeded"


async def rag_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map platform errors to structured JSON responses with a request id."""
    from ultimate_rag.core.logging import get_request_id

    err = exc if isinstance(exc, RAGError) else RAGError(str(exc))
    status_code = getattr(err, "status_code", 500)
    code = getattr(err, "code", "error")
    message = getattr(err, "message", None) or err.__class__.__name__
    details = getattr(err, "details", None) or {}
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": get_request_id(),
            }
        },
        headers={"X-Request-ID": get_request_id()},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    from ultimate_rag.core.logging import get_request_id, logger

    logger.exception(
        "Unhandled exception at %s", str(request.url.path), extra={"path": str(request.url.path)}
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "internal_error",
                "message": "Internal server error",
                "request_id": get_request_id(),
            }
        },
    )
