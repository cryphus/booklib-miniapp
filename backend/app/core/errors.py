from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import logger


class APIError(Exception):
    """Base class for every error the API returns in the unified envelope."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "BAD_REQUEST"
    message: str = "Bad request"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details
        super().__init__(self.message)


class UnauthorizedError(APIError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORIZED"
    message = "Authentication required"


class ForbiddenError(APIError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
    message = "Access denied"


class NotFoundError(APIError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    message = "Resource not found"


class ConflictError(APIError):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"
    message = "Conflict"


class ValidationError(APIError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"
    message = "Validation failed"


class RateLimitError(APIError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests, try again later"


class AILimitReachedError(APIError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "AI_LIMIT_REACHED"
    message = "Monthly AI request limit reached"


class NotEnoughContextError(APIError):
    status_code = status.HTTP_200_OK  # handled explicitly, never raised to client
    code = "NOT_ENOUGH_CONTEXT"
    message = "Not enough information found in your library"


class ProviderError(APIError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "PROVIDER_ERROR"
    message = "Upstream provider is unavailable"


class PaymentProviderNotConfiguredError(APIError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "PAYMENT_PROVIDER_NOT_CONFIGURED"
    message = "This payment provider is not available yet"


def _envelope(code: str, message: str, details: Any = None) -> dict:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 429: "RATE_LIMIT_EXCEEDED"}
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(codes.get(exc.status_code, "HTTP_ERROR"), str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in e.get("loc", [])[1:]), "message": e.get("msg", "")}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope("VALIDATION_ERROR", "Validation failed", details),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Never leak a traceback to the client.
        logger.exception("unhandled_error path=%s type=%s", request.url.path, type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=_envelope("INTERNAL_ERROR", "Internal server error"),
        )
