from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.documents import Document, DocumentStatus
from app.db.session import get_db_session
from app.main import app
from app.repositories.document_repository import DocumentRepository


async def _create_document(
    session: AsyncSession,
    *,
    filename: str,
    size_bytes: int,
) -> Document:
    repository = DocumentRepository(session)
    return await repository.create_document(
        filename=filename,
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=size_bytes,
        storage_path=f"/tmp/{filename}",
        extracted_text=f"content for {filename}",
        status=DocumentStatus.PENDING,
    )


async def _set_created_at(
    session: AsyncSession,
    document: Document,
    created_at: datetime,
) -> None:
    await session.execute(
        update(Document).where(Document.id == document.id).values(created_at=created_at)
    )
    await session.flush()
    await session.refresh(document)


@pytest.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient]:
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_session] = _override_get_db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


@pytest.mark.asyncio
async def test_list_documents_returns_paginated_summaries(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    oldest = await _create_document(db_session, filename="oldest.txt", size_bytes=100)
    middle = await _create_document(db_session, filename="middle.txt", size_bytes=200)
    newest = await _create_document(db_session, filename="newest.txt", size_bytes=300)

    await _set_created_at(db_session, oldest, datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    await _set_created_at(db_session, middle, datetime(2026, 1, 2, 12, 0, tzinfo=UTC))
    await _set_created_at(db_session, newest, datetime(2026, 1, 3, 12, 0, tzinfo=UTC))

    response = await api_client.get(
        "/api/v1/documents",
        params={"limit": 2, "offset": 1},
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["limit"] == 2
    assert payload["offset"] == 1
    assert payload["total"] == 3
    assert [item["id"] for item in payload["items"]] == [str(middle.id), str(oldest.id)]
    assert payload["items"][0]["filename"] == "middle.txt"
    assert payload["items"][0]["original_extension"] == ".txt"
    assert payload["items"][0]["size_bytes"] == 200
    assert payload["items"][0]["status"] == DocumentStatus.PENDING.value
    assert set(payload["items"][0]) == {
        "id",
        "filename",
        "original_extension",
        "size_bytes",
        "status",
        "created_at",
    }
