from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.core.settings import get_settings
from app.db.models.auth import User
from app.db.models.collections import Collection
from app.db.models.documents import Document, DocumentStatus
from app.db.session import get_db_session
from app.main import app
from app.repositories.collection_repository import CollectionRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.user_repository import UserRepository

SAFE_DOCUMENT_FIELDS = {
    "id",
    "collection_id",
    "filename",
    "original_extension",
    "content_type",
    "size_bytes",
    "status",
    "error_message",
    "created_at",
    "updated_at",
}


@pytest.fixture
def document_list_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-enough-length")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def api_client(
    document_list_settings: None,
    db_session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient]:
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_session] = _override_get_db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
    app.dependency_overrides.update(original_overrides)


async def _create_user(session: AsyncSession, label: str) -> User:
    return await UserRepository(session).create_user(
        email=f"{label}-{uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Document",
        last_name="Tester",
        is_active=True,
        is_email_verified=True,
    )


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


async def _create_collection(
    session: AsyncSession,
    user: User,
    name: str,
) -> Collection:
    return await CollectionRepository(session).create_collection(user.id, name)


async def _create_document(
    session: AsyncSession,
    user: User,
    *,
    filename: str,
    size_bytes: int,
    collection_id: UUID | None = None,
    status: DocumentStatus = DocumentStatus.PENDING,
    error_message: str | None = None,
) -> Document:
    repository = DocumentRepository(session)
    return await repository.create_document(
        user.id,
        collection_id=collection_id,
        filename=filename,
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=size_bytes,
        storage_path=f"/private/{filename}",
        extracted_text=f"content for {filename}",
        status=status,
        error_message=error_message,
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


@pytest.mark.asyncio
async def test_list_documents_returns_owner_scoped_complete_safe_metadata(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "document-list-owner")
    collection = await _create_collection(db_session, owner, "Owner collection")
    other_user = await _create_user(db_session, "document-list-other")

    oldest = await _create_document(
        db_session,
        owner,
        filename="oldest.txt",
        size_bytes=100,
    )
    middle = await _create_document(
        db_session,
        owner,
        filename="middle.txt",
        size_bytes=200,
        collection_id=collection.id,
        status=DocumentStatus.FAILED,
        error_message="Extraction failed.",
    )
    newest = await _create_document(
        db_session,
        owner,
        filename="newest.txt",
        size_bytes=300,
    )
    foreign = await _create_document(
        db_session,
        other_user,
        filename="foreign.txt",
        size_bytes=400,
    )

    await _set_created_at(db_session, oldest, datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    await _set_created_at(db_session, middle, datetime(2026, 1, 2, 12, 0, tzinfo=UTC))
    await _set_created_at(db_session, newest, datetime(2026, 1, 3, 12, 0, tzinfo=UTC))
    await _set_created_at(db_session, foreign, datetime(2026, 1, 4, 12, 0, tzinfo=UTC))

    response = await api_client.get(
        "/api/v1/documents",
        headers=_auth_headers(owner),
        params={"limit": 2, "offset": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 2
    assert payload["offset"] == 1
    assert payload["total"] == 3
    assert [item["id"] for item in payload["items"]] == [str(middle.id), str(oldest.id)]

    item = payload["items"][0]
    assert set(item) == SAFE_DOCUMENT_FIELDS
    assert item["collection_id"] == str(collection.id)
    assert item["filename"] == "middle.txt"
    assert item["original_extension"] == ".txt"
    assert item["content_type"] == "text/plain"
    assert item["size_bytes"] == 200
    assert item["status"] == DocumentStatus.FAILED.value
    assert item["error_message"] == "Extraction failed."
    assert item["created_at"]
    assert item["updated_at"]


@pytest.mark.asyncio
async def test_list_documents_filters_by_owned_collection_and_hides_foreign_collections(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "document-filter-owner")
    selected_collection = await _create_collection(db_session, owner, "Selected")
    empty_collection = await _create_collection(db_session, owner, "Empty")
    other_user = await _create_user(db_session, "document-filter-other")
    foreign_collection = await _create_collection(db_session, other_user, "Foreign")

    selected_document = await _create_document(
        db_session,
        owner,
        filename="selected.txt",
        size_bytes=10,
        collection_id=selected_collection.id,
    )
    await _create_document(
        db_session,
        owner,
        filename="uncollected.txt",
        size_bytes=20,
    )
    await _create_document(
        db_session,
        other_user,
        filename="foreign.txt",
        size_bytes=30,
        collection_id=foreign_collection.id,
    )

    filtered_response = await api_client.get(
        "/api/v1/documents",
        headers=_auth_headers(owner),
        params={"collection_id": str(selected_collection.id)},
    )
    empty_response = await api_client.get(
        "/api/v1/documents",
        headers=_auth_headers(owner),
        params={"collection_id": str(empty_collection.id)},
    )
    foreign_response = await api_client.get(
        "/api/v1/documents",
        headers=_auth_headers(owner),
        params={"collection_id": str(foreign_collection.id)},
    )
    missing_response = await api_client.get(
        "/api/v1/documents",
        headers=_auth_headers(owner),
        params={"collection_id": str(uuid4())},
    )

    assert filtered_response.status_code == 200
    assert filtered_response.json()["total"] == 1
    assert [item["id"] for item in filtered_response.json()["items"]] == [
        str(selected_document.id)
    ]
    assert empty_response.status_code == 200
    assert empty_response.json()["items"] == []
    assert empty_response.json()["total"] == 0
    assert foreign_response.status_code == 404
    assert foreign_response.json() == missing_response.json() == {
        "error": {
            "code": "not_found",
            "message": "Collection not found.",
        }
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (101, 0), (1, -1)],
)
async def test_list_documents_validates_pagination_bounds(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    limit: int,
    offset: int,
) -> None:
    user = await _create_user(db_session, "document-pagination-bounds")

    response = await api_client.get(
        "/api/v1/documents",
        headers=_auth_headers(user),
        params={"limit": limit, "offset": offset},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
