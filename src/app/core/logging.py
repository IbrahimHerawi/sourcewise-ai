"""Logging setup and request correlation id middleware."""

import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_correlation_id_ctx_var: ContextVar[str] = ContextVar(
    "correlation_id",
    default="-",
)


class CorrelationIdFilter(logging.Filter):
    """Inject the request correlation id into each log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id_ctx_var.get()
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Configure application logging."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(correlation_id)s] %(name)s: %(message)s"
        )
    )
    handler.addFilter(CorrelationIdFilter())

    root_logger.handlers.clear()
    root_logger.addHandler(handler)


class RequestCorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach a correlation id to request context and response header."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = _correlation_id_ctx_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            _correlation_id_ctx_var.reset(token)
