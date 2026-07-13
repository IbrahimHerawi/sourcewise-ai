from __future__ import annotations

import httpx
import pytest

from app.main import app


def test_business_api_routes_are_versioned_only() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}

    assert any(path.startswith("/api/v1/collections") for path in paths)
    assert any(path.startswith("/api/v1/documents") for path in paths)
    assert any(path.startswith("/api/v1/questions") for path in paths)
    assert not any(path.startswith("/api/collections") for path in paths)
    assert not any(path.startswith("/api/documents") for path in paths)
    assert not any(path.startswith("/api/questions") for path in paths)


@pytest.mark.asyncio
async def test_v1_health_works_publicly() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_openapi_uses_versioned_business_paths() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    paths = set(response.json()["paths"])
    assert "/api/v1/health" in paths
    assert "/api/v1/collections" in paths
    assert "/api/v1/collections/{collection_id}" in paths
    assert "/api/v1/documents" in paths
    assert "/api/v1/documents/upload" in paths
    assert "/api/v1/questions/ask" in paths
    assert not any(path.startswith("/api/collections") for path in paths)
    assert not any(path.startswith("/api/documents") for path in paths)
    assert not any(path.startswith("/api/questions") for path in paths)
