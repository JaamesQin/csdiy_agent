"""Error response helpers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def error_body(message: str, error_type: str, code: str | None = None) -> dict[str, Any]:
    return {
        "error": {
            "message": message,
            "type": error_type,
            "param": None,
            "code": code,
        }
    }


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    error_type = "authentication_error" if exc.status_code == 401 else "invalid_request_error"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(message, error_type),
        headers=exc.headers,
    )


async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    message = first_error.get("msg", "Invalid request")
    return JSONResponse(
        status_code=422,
        content=error_body(str(message), "invalid_request_error"),
    )


async def server_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled CoursePilot request error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=error_body(
            "The request failed because an internal error occurred.",
            "server_error",
        ),
    )
