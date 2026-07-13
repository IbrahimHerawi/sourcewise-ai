"""Logging setup with request-id context and sensitive data redaction."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from contextvars import ContextVar, Token
from typing import Any

_request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="-")
_SENSITIVE_KEY_RE = re.compile(
    r"(?:api[_-]?key|authorization|token|password|secret)",
    re.IGNORECASE,
)
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|token|password|secret)\b\s*[:=]\s*([^\s,;]+)"
)
_BEARER_TOKEN_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]+")


def get_request_id() -> str:
    """Return the current request id from context."""
    return _request_id_ctx_var.get()


def set_request_id(request_id: str) -> Token[str]:
    """Store the request id in the current execution context."""
    return _request_id_ctx_var.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    """Restore the previous request id context state."""
    _request_id_ctx_var.reset(token)


def _sanitize_string(value: str) -> str:
    redacted = _SENSITIVE_ASSIGNMENT_RE.sub(r"\1=<redacted>", value)
    redacted = _BEARER_TOKEN_RE.sub("Bearer <redacted>", redacted)
    return redacted


def _is_sensitive_key(key: Any) -> bool:
    return isinstance(key, str) and _SENSITIVE_KEY_RE.search(key) is not None


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, bytes | bytearray | memoryview):
        return "<redacted-bytes>"

    if isinstance(value, str):
        return _sanitize_string(value)

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
        return tuple(_sanitize_value(item) for item in value)

    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]

    if isinstance(value, set):
        return {_sanitize_value(item) for item in value}

    return value


class RequestIdFilter(logging.Filter):
    """Inject the request id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class SensitiveDataFilter(logging.Filter):
    """Redact sensitive values from log messages and arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _sanitize_string(record.msg)

        if record.exc_info:
            # Format the traceback before the handler does so exception messages pass
            # through the same redaction used for ordinary log messages and arguments.
            traceback_text = logging.Formatter().formatException(record.exc_info)
            record.exc_text = _sanitize_string(traceback_text)

        args = record.args
        if not args:
            return True

        if isinstance(args, Mapping):
            record.args = {key: _sanitize_value(value) for key, value in args.items()}
            return True

        if isinstance(args, tuple):
            record.args = tuple(_sanitize_value(value) for value in args)
            return True

        if isinstance(args, Sequence) and not isinstance(args, str):
            record.args = tuple(_sanitize_value(value) for value in args)
            return True

        record.args = _sanitize_value(args)
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Configure application logging."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
    )
    handler.addFilter(RequestIdFilter())
    handler.addFilter(SensitiveDataFilter())

    root_logger.handlers.clear()
    root_logger.addHandler(handler)


__all__ = [
    "get_request_id",
    "reset_request_id",
    "set_request_id",
    "setup_logging",
]
