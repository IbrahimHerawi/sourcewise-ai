"""Central application exceptions and FastAPI error handlers."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

_SENSITIVE_KEY_RE = re.compile(
    r"(?:api[_-]?key|authorization|token|password|secret)",
    re.IGNORECASE,
)

_STATUS_CODE_TO_ERROR_CODE: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_413_CONTENT_TOO_LARGE: "payload_too_large",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "validation_error",
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_server_error",
    status.HTTP_502_BAD_GATEWAY: "bad_gateway",
    status.HTTP_503_SERVICE_UNAVAILABLE: "service_unavailable",
    status.HTTP_504_GATEWAY_TIMEOUT: "gateway_timeout",
}


class AppError(Exception):
    """Base class for application exceptions with API-safe metadata."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = dict(details) if details is not None else None


class ValidationError(AppError):
    """Raised when request or domain validation fails."""

    def __init__(
        self,
        message: str = "Validation failed.",
        *,
        code: str = "validation_error",
        details: Mapping[str, Any] | None = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status_code=status_code,
            details=details,
        )


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(
        self,
        message: str = "Resource not found.",
        *,
        code: str = "not_found",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class IngestionError(AppError):
    """Raised for ingestion pipeline availability/processing failures."""

    def __init__(
        self,
        message: str = "Ingestion failed.",
        *,
        code: str = "ingestion_error",
        details: Mapping[str, Any] | None = None,
        status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status_code=status_code,
            details=details,
        )


class ExternalServiceError(AppError):
    """Raised when an upstream provider fails."""

    def __init__(
        self,
        message: str = "External service call failed.",
        *,
        code: str = "external_service_error",
        details: Mapping[str, Any] | None = None,
        status_code: int = status.HTTP_502_BAD_GATEWAY,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status_code=status_code,
            details=details,
        )


def _is_sensitive_key(key: Any) -> bool:
    return isinstance(key, str) and _SENSITIVE_KEY_RE.search(key) is not None


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key)
            if _is_sensitive_key(normalized_key):
                sanitized[normalized_key] = "<redacted>"
            else:
                sanitized[normalized_key] = _sanitize_value(item)
        return sanitized

    if isinstance(value, tuple):
        return [_sanitize_value(item) for item in value]

    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]

    if isinstance(value, bytes | bytearray | memoryview):
        return "<redacted-bytes>"

    return value


def _error_payload(
    *,
    code: str,
    message: str,
    details: Any = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = _sanitize_value(details)
    return payload


def _json_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=_error_payload(
            code=code,
            message=message,
            details=details,
        ),
    )


def _status_code_to_error_code(status_code: int) -> str:
    return _STATUS_CODE_TO_ERROR_CODE.get(status_code, "request_error")


def _normalize_http_exception_detail(
    detail: Any,
    *,
    status_code: int,
) -> tuple[str, str, Any]:
    code = _status_code_to_error_code(status_code)
    fallback_message = "Request failed."

    if isinstance(detail, str):
        return code, detail, None

    if isinstance(detail, Mapping):
        detail_code = detail.get("code")
        detail_message = detail.get("message")
        detail_details = detail.get("details")
        if isinstance(detail_code, str) and isinstance(detail_message, str):
            return detail_code, detail_message, detail_details
        if isinstance(detail_message, str):
            return code, detail_message, detail_details
        return code, fallback_message, dict(detail)

    if isinstance(detail, list):
        return code, fallback_message, {"errors": detail}

    if detail is None:
        return code, fallback_message, None

    return code, fallback_message, {"detail": str(detail)}


async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return _json_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def _request_validation_error_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return _json_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="validation_error",
        message="Request validation failed.",
        details={"errors": exc.errors()},
    )


async def _pydantic_validation_error_handler(
    _: Request,
    exc: PydanticValidationError,
) -> JSONResponse:
    return _json_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="validation_error",
        message="Validation failed.",
        details={"errors": exc.errors()},
    )


async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    code, message, details = _normalize_http_exception_detail(
        exc.detail,
        status_code=exc.status_code,
    )
    return _json_error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        details=details,
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled exception while processing %s %s.",
        request.method,
        request.url.path,
    )
    return _json_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_server_error",
        message="An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register app-wide exception handlers with a consistent API error shape."""
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _request_validation_error_handler)
    app.add_exception_handler(PydanticValidationError, _pydantic_validation_error_handler)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)


__all__ = [
    "AppError",
    "ExternalServiceError",
    "IngestionError",
    "NotFoundError",
    "ValidationError",
    "register_exception_handlers",
]
