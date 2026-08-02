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


def test_sensitive_data_filter_redacts_every_secret_category() -> None:
    sentinels = {
        "openai_api_key": "SENTINEL_OPENAI_API_KEY_27",
        "resend_api_key": "SENTINEL_RESEND_KEY_27",
        "smtp_password": "SENTINEL_SMTP_PASSWORD_27",
        "secret_key": "SENTINEL_JWT_SIGNING_KEY_27",
        "postgres_password": "SENTINEL_POSTGRES_PASSWORD_27",
        "authorization": "Bearer SENTINEL_BEARER_TOKEN_27",
        "verification_token": "SENTINEL_VERIFICATION_TOKEN_27",
        "reset_token": "SENTINEL_RESET_TOKEN_27",
        "refresh_token": "SENTINEL_REFRESH_TOKEN_27",
        "token_hash": "SENTINEL_TOKEN_HASH_27",
    }
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=40,
        msg="Provider failure metadata=%s",
        args=(sentinels,),
        exc_info=None,
    )

    SensitiveDataFilter().filter(record)
    rendered = logging.Formatter("%(message)s").format(record)

    for sentinel in sentinels.values():
        assert sentinel not in rendered
    assert rendered.count("<redacted>") == len(sentinels)


def test_sensitive_data_filter_redacts_refresh_assignments_in_strings() -> None:
    refresh_token = "SENTINEL_REFRESH_TOKEN_STRING_27"
    token_hash = "SENTINEL_TOKEN_HASH_STRING_27"
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=60,
        msg=f"refresh_token={refresh_token} token_hash={token_hash}",
        args=(),
        exc_info=None,
    )

    SensitiveDataFilter().filter(record)
    rendered = logging.Formatter("%(message)s").format(record)

    assert refresh_token not in rendered
    assert token_hash not in rendered
    assert rendered == "refresh_token=<redacted> token_hash=<redacted>"
