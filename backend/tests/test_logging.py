from __future__ import annotations

import logging
import sys

from app.core.logging import SensitiveDataFilter


def test_sensitive_data_filter_redacts_exception_tracebacks() -> None:
    try:
        raise RuntimeError("password=raw-diagnostic-secret")
    except RuntimeError:
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=12,
            msg="Ingestion diagnostic failure.",
            args=(),
            exc_info=sys.exc_info(),
        )

    SensitiveDataFilter().filter(record)
    rendered = logging.Formatter("%(message)s").format(record)

    assert "raw-diagnostic-secret" not in rendered
    assert "password=<redacted>" in rendered
