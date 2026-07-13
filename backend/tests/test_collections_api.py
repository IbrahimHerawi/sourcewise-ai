from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Generator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.core.settings import get_settings
from app.db.models.auth import User
from app.db.models.documents import Document, DocumentStatus
from app.db.models.questions import Question
from app.db.session import get_db_session
from app.main import app
from app.repositories.user_repository import UserRepository

COLLECTIONS_PATH = "/api/v1/collections"
NOT_FOUND_PAYLOAD = {
    "error": {
        "code": "not_found",
        "message": "Collection not found.",
    }
}


@pytest.fixture
def collection_api_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-enough-length")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def api_client(
    collection_api_settings: None,
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


async def _create_user(
    session: AsyncSession,
    label: str,
    *,
    is_active: bool = True,
    is_email_verified: bool = True,
) -> User:
    return await UserRepository(session).create_user(
        email=f"{label}-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Collection",
        last_name="Tester",
        is_active=is_active,
        is_email_verified=is_email_verified,
    )


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


async def _create_collection(
    client: httpx.AsyncClient,
    user: User,
    name: str,
    description: str | None = None,
) -> httpx.Response:
    return await client.post(
        COLLECTIONS_PATH,
        headers=_auth_headers(user),
        json={"name": name, "description": description},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("POST", COLLECTIONS_PATH, {"name": "Research"}),
        ("GET", COLLECTIONS_PATH, None),
        ("GET", f"{COLLECTIONS_PATH}/{uuid.uuid4()}", None),
        ("PATCH", f"{COLLECTIONS_PATH}/{uuid.uuid4()}", {"name": "Updated"}),
        ("DELETE", f"{COLLECTIONS_PATH}/{uuid.uuid4()}", None),
    ],
)
async def test_collection_endpoints_require_authentication(
    api_client: httpx.AsyncClient,
    method: str,
    path: str,
    json_body: dict[str, str] | None,
) -> None:
    kwargs = {"json": json_body} if json_body is not None else {}
    response = await api_client.request(method, path, **kwargs)

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Authentication credentials could not be validated.",
        }
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("is_active", "is_email_verified", "expected_message"),
    [
        (False, True, "User account is inactive."),
        (True, False, "User email is not verified."),
    ],
)
async def test_collection_endpoints_require_active_verified_users(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    is_active: bool,
    is_email_verified: bool,
    expected_message: str,
) -> None:
    user = await _create_user(
        db_session,
        "ineligible-collection-user",
        is_active=is_active,
        is_email_verified=is_email_verified,
    )

    response = await api_client.get(COLLECTIONS_PATH, headers=_auth_headers(user))

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "forbidden",
            "message": expected_message,
        }
    }


@pytest.mark.asyncio
async def test_collection_crud_uses_safe_response_fields(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "collection-crud-api")

    create_response = await _create_collection(
        api_client,
        user,
        "  Research Sources  ",
        "  Primary material  ",
    )

    assert create_response.status_code == 201
    created = create_response.json()
    collection_id = created["id"]
    assert set(created) == {"id", "name", "description", "created_at", "updated_at"}
    assert created["name"] == "Research Sources"
    assert created["description"] == "Primary material"

    get_response = await api_client.get(
        f"{COLLECTIONS_PATH}/{collection_id}",
        headers=_auth_headers(user),
    )
    assert get_response.status_code == 200
    assert get_response.json() == created

    update_response = await api_client.patch(
        f"{COLLECTIONS_PATH}/{collection_id}",
        headers=_auth_headers(user),
        json={"name": "  Updated Research  ", "description": "   "},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert set(updated) == set(created)
    assert updated["id"] == collection_id
    assert updated["name"] == "Updated Research"
    assert updated["description"] is None

    delete_response = await api_client.delete(
        f"{COLLECTIONS_PATH}/{collection_id}",
        headers=_auth_headers(user),
    )
    assert delete_response.status_code == 204
    assert delete_response.content == b""

    missing_response = await api_client.get(
        f"{COLLECTIONS_PATH}/{collection_id}",
        headers=_auth_headers(user),
    )
    assert missing_response.status_code == 404
    assert missing_response.json() == NOT_FOUND_PAYLOAD


@pytest.mark.asyncio
async def test_collection_list_paginates_and_excludes_other_users(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "collection-pagination-owner")
    for name in ("First", "Second", "Third"):
        response = await _create_collection(api_client, owner, name)
        assert response.status_code == 201

    other_user = await _create_user(db_session, "collection-pagination-other")
    other_response = await _create_collection(api_client, other_user, "Other")
    assert other_response.status_code == 201

    first_page = await api_client.get(
        COLLECTIONS_PATH,
        headers=_auth_headers(owner),
        params={"limit": 2, "offset": 0},
    )
    second_page = await api_client.get(
        COLLECTIONS_PATH,
        headers=_auth_headers(owner),
        params={"limit": 2, "offset": 2},
    )

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    first_payload = first_page.json()
    second_payload = second_page.json()
    assert first_payload["limit"] == 2
    assert first_payload["offset"] == 0
    assert first_payload["total"] == 3
    assert second_payload["limit"] == 2
    assert second_payload["offset"] == 2
    assert second_payload["total"] == 3
    items = first_payload["items"] + second_payload["items"]
    assert {item["name"] for item in items} == {"First", "Second", "Third"}
    assert all("user_id" not in item for item in items)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (101, 0), (1, -1)],
)
async def test_collection_list_validates_pagination_bounds(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    limit: int,
    offset: int,
) -> None:
    user = await _create_user(db_session, "collection-invalid-pagination")

    response = await api_client.get(
        COLLECTIONS_PATH,
        headers=_auth_headers(user),
        params={"limit": limit, "offset": offset},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_collection_duplicate_names_return_conflict(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "collection-duplicate-api")
    original_response = await _create_collection(api_client, user, "Research")
    assert original_response.status_code == 201

    duplicate_create = await _create_collection(api_client, user, "  RESEARCH  ")
    assert duplicate_create.status_code == 409
    assert duplicate_create.json() == {
        "error": {
            "code": "conflict",
            "message": "A collection with this name already exists.",
        }
    }

    second_response = await _create_collection(api_client, user, "Second")
    assert second_response.status_code == 201
    second_id = second_response.json()["id"]

    duplicate_update = await api_client.patch(
        f"{COLLECTIONS_PATH}/{second_id}",
        headers=_auth_headers(user),
        json={"name": "research"},
    )
    assert duplicate_update.status_code == 409
    assert duplicate_update.json() == duplicate_create.json()

    unchanged_response = await api_client.get(
        f"{COLLECTIONS_PATH}/{second_id}",
        headers=_auth_headers(user),
    )
    assert unchanged_response.status_code == 200
    assert unchanged_response.json()["name"] == "Second"


@pytest.mark.asyncio
async def test_collection_ids_are_isolated_between_users(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "collection-isolation-owner")
    create_response = await _create_collection(api_client, owner, "Private")
    assert create_response.status_code == 201
    collection_id = create_response.json()["id"]

    other_user = await _create_user(db_session, "collection-isolation-other")
    missing_response = await api_client.get(
        f"{COLLECTIONS_PATH}/{uuid.uuid4()}",
        headers=_auth_headers(other_user),
    )
    assert missing_response.status_code == 404
    assert missing_response.json() == NOT_FOUND_PAYLOAD

    foreign_get = await api_client.get(
        f"{COLLECTIONS_PATH}/{collection_id}",
        headers=_auth_headers(other_user),
    )
    foreign_patch = await api_client.patch(
        f"{COLLECTIONS_PATH}/{collection_id}",
        headers=_auth_headers(other_user),
        json={"name": "Hijacked"},
    )
    foreign_delete = await api_client.delete(
        f"{COLLECTIONS_PATH}/{collection_id}",
        headers=_auth_headers(other_user),
    )

    for response in (foreign_get, foreign_patch, foreign_delete):
        assert response.status_code == missing_response.status_code
        assert response.json() == missing_response.json()

    other_list = await api_client.get(COLLECTIONS_PATH, headers=_auth_headers(other_user))
    assert other_list.status_code == 200
    assert other_list.json()["items"] == []
    assert other_list.json()["total"] == 0

    owner_get = await api_client.get(
        f"{COLLECTIONS_PATH}/{collection_id}",
        headers=_auth_headers(owner),
    )
    assert owner_get.status_code == 200
    assert owner_get.json()["name"] == "Private"


@pytest.mark.asyncio
async def test_deleting_collection_keeps_content_and_clears_collection_ids(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "collection-delete-content-api")
    create_response = await _create_collection(api_client, user, "Sources")
    collection_id = uuid.UUID(create_response.json()["id"])
    settings = get_settings()

    document = Document(
        user_id=user.id,
        collection_id=collection_id,
        filename="source.txt",
        original_extension=".txt",
        content_type="text/plain",
        size_bytes=12,
        storage_path="/tmp/source.txt",
        extracted_text="source text",
        status=DocumentStatus.READY,
    )
    question = Question(
        user_id=user.id,
        collection_id=collection_id,
        question_text="What is the source?",
        question_embedding=[0.0] * settings.embedding_dim,
        answer_text="A test source.",
        ai_provider="ollama",
        model_used="test-model",
    )
    db_session.add_all([document, question])
    await db_session.flush()

    response = await api_client.delete(
        f"{COLLECTIONS_PATH}/{collection_id}",
        headers=_auth_headers(user),
    )

    assert response.status_code == 204
    await db_session.refresh(document)
    await db_session.refresh(question)
    assert document.collection_id is None
    assert question.collection_id is None
    assert await db_session.get(Document, document.id) is not None
    assert await db_session.get(Question, question.id) is not None
