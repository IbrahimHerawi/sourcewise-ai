from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.main import app

PROTECTED_REQUESTS = [
    pytest.param(
        "POST", "/api/v1/collections", {"json": {"name": "Private"}}, id="collection-create"
    ),
    pytest.param("GET", "/api/v1/collections", {}, id="collection-list"),
    pytest.param("GET", f"/api/v1/collections/{uuid4()}", {}, id="collection-detail"),
    pytest.param(
        "PATCH",
        f"/api/v1/collections/{uuid4()}",
        {"json": {"name": "Private"}},
        id="collection-update",
    ),
    pytest.param("DELETE", f"/api/v1/collections/{uuid4()}", {}, id="collection-delete"),
    pytest.param("GET", "/api/v1/documents", {}, id="document-list"),
    pytest.param("GET", f"/api/v1/documents/{uuid4()}", {}, id="document-detail"),
    pytest.param(
        "POST",
        "/api/v1/documents/upload",
        {"files": {"files": ("private.txt", b"private", "text/plain")}},
        id="document-upload",
    ),
    pytest.param("DELETE", f"/api/v1/documents/{uuid4()}", {}, id="document-delete"),
    pytest.param(
        "POST",
        "/api/v1/questions/ask",
        {"json": {"question": "What is private?"}},
        id="question-ask",
    ),
    pytest.param("GET", "/api/v1/questions/history", {}, id="history-list"),
    pytest.param(
        "GET",
        f"/api/v1/questions/history/{uuid4()}",
        {},
        id="history-detail",
    ),
    pytest.param(
        "DELETE",
        f"/api/v1/questions/history/{uuid4()}",
        {},
        id="history-delete",
    ),
]

PUBLIC_REQUESTS = [
    pytest.param("POST", "/api/v1/auth/register", id="register"),
    pytest.param("POST", "/api/v1/auth/verify-email", id="verify-email"),
    pytest.param("POST", "/api/v1/auth/resend-verification", id="resend-verification"),
    pytest.param("POST", "/api/v1/auth/login", id="login"),
    pytest.param("POST", "/api/v1/auth/forgot-password", id="forgot-password"),
    pytest.param("POST", "/api/v1/auth/reset-password", id="reset-password"),
]

PRIVATE_RESOURCE_FIELDS = {
    "user_id",
    "storage_path",
    "extracted_text",
    "question_embedding",
    "embedding",
    "prompt",
    "context",
    "chunk_content",
}

SECRET_CONFIGURATION_FIELDS = {
    "openai_api_key",
    "openai_api_key_file",
    "resend_api_key",
    "resend_api_key_file",
    "smtp_password",
    "smtp_password_file",
    "secret_key",
    "secret_key_file",
    "postgres_password",
    "postgres_password_file",
}

SECRET_SENTINELS = {
    "SENTINEL_OPENAI_API_KEY_27",
    "SENTINEL_RESEND_KEY_27",
    "SENTINEL_SMTP_PASSWORD_27",
    "SENTINEL_JWT_SIGNING_KEY_27",
    "SENTINEL_POSTGRES_PASSWORD_27",
    "SENTINEL_BEARER_TOKEN_27",
    "SENTINEL_VERIFICATION_TOKEN_27",
    "SENTINEL_RESET_TOKEN_27",
    "SENTINEL_PROVIDER_SECRET_TEXT_27",
}


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[httpx.AsyncClient]:
    session = AsyncSession()

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield session

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_session] = _override_get_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        await session.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path", "request_kwargs"), PROTECTED_REQUESTS)
async def test_complete_owned_route_matrix_requires_bearer_authentication(
    api_client: httpx.AsyncClient,
    method: str,
    path: str,
    request_kwargs: dict[str, Any],
) -> None:
    response = await api_client.request(method, path, **request_kwargs)

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Authentication credentials could not be validated.",
        }
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path"), PUBLIC_REQUESTS)
async def test_authentication_lifecycle_endpoints_remain_public(
    api_client: httpx.AsyncClient,
    method: str,
    path: str,
) -> None:
    response = await api_client.request(method, path, json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_health_endpoint_remains_public(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_bearer_token_is_absent_from_error_response_headers_and_logs(
    api_client: httpx.AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bearer_token = "SENTINEL_BEARER_TOKEN_27"

    with caplog.at_level(logging.INFO):
        response = await api_client.get(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {bearer_token}"},
        )

    rendered_response = response.text + json.dumps(dict(response.headers))
    assert response.status_code == 401
    assert bearer_token not in rendered_response
    assert bearer_token not in caplog.text


def test_openapi_contains_no_private_resource_or_settings_configuration_fields() -> None:
    schema = app.openapi()
    schemas = schema["components"]["schemas"]
    properties = {
        property_name
        for component in schemas.values()
        for property_name in component.get("properties", {})
    }

    assert PRIVATE_RESOURCE_FIELDS.isdisjoint(properties)
    assert SECRET_CONFIGURATION_FIELDS.isdisjoint(properties)
    assert not any("settings" in component_name.lower() for component_name in schemas)
    assert not any("/chunks" in path or path.endswith("/chunks") for path in schema["paths"])

    rendered_schema = json.dumps(schema, sort_keys=True)
    for sentinel in SECRET_SENTINELS:
        assert sentinel not in rendered_schema
