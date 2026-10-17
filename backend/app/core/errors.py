"""Application errors and FastAPI exception handlers.

Every error response uses the shared envelope so the frontend has one shape to
parse (PRD section 9.2).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.envelope import error_envelope

logger = logging.getLogger("bloodbridge")


class ApiError(Exception):
    """A controlled, client-safe error."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


# --- Convenience constructors -------------------------------------------------

def bad_request(message: str, details: Any = None) -> ApiError:
    return ApiError(status.HTTP_400_BAD_REQUEST, "BAD_REQUEST", message, details)


def validation_error(message: str, details: Any = None) -> ApiError:
    return ApiError(status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", message, details)


def unauthorized(message: str = "Authentication required.") -> ApiError:
    return ApiError(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", message)


def forbidden(message: str = "You do not have access to this resource.") -> ApiError:
    return ApiError(status.HTTP_403_FORBIDDEN, "FORBIDDEN", message)


def not_found(message: str = "Resource not found.") -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", message)


def conflict(message: str, details: Any = None) -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, "CONFLICT", message, details)


def rate_limited(message: str = "Too many requests. Please slow down.") -> ApiError:
    return ApiError(status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMITED", message)


_STATUS_TO_CODE = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
    status.HTTP_409_CONFLICT: "CONFLICT",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
    status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(error_envelope(exc.code, exc.message, exc.details)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo raw input back: pydantic errors can carry the submitted
        # body (including password fields) in `input`, and a `ValueError` object
        # in `ctx` that is not JSON serializable. Keep only safe, scalar fields.
        details = [
            {
                "loc": [str(part) for part in err.get("loc", ())],
                "msg": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder(
                error_envelope("VALIDATION_ERROR", "Invalid input.", details)
            ),
        )

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError) -> JSONResponse:
        # A uniqueness/constraint violation (e.g. a rare concurrent code
        # collision) is a conflict, not a server fault.
        logger.warning("Integrity error: %s", exc.orig)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_envelope(
                "CONFLICT", "The operation conflicts with existing data. Please retry."
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_TO_CODE.get(exc.status_code, "HTTP_ERROR")
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(code, detail),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_envelope("INTERNAL_ERROR", "An unexpected error occurred."),
        )
