from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, generate_secure_token, hash_token
from app.core.settings import get_settings
from app.db.models import DocumentStatus, User
from app.db.session import get_db_session
from app.main import app
from app.repositories import (
    CollectionRepository,
    DocumentRepository,
    QuestionRepository,
    UserRepository,
)

OVERVIEW_PATH = "/api/v1/auth/overview"
EXPECTED_FIELDS = {
    "total_documents",
    "total_questions",
    "total_collections",
}


@pytest.fixture
def overview_api_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-enough-length")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def overview_client(
    overview_api_settings: None,
    db_session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient]:
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

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
        first_name="Overview",
        last_name="API Tester",
        is_active=is_active,
        is_email_verified=is_email_verified,
    )


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


async def _create_resources(
    session: AsyncSession,
    user: User,
    *,
    document_count: int,
    question_count: int,
    collection_count: int,
) -> None:
    collection_repository = CollectionRepository(session)
    collections = [
        await collection_repository.create_collection(user.id, f"Collection {index}")
        for index in range(collection_count)
    ]
    for index in range(document_count):
        await DocumentRepository(session).create_document(
            user.id,
            collection_id=collections[0].id if collections and index % 2 == 0 else None,
            filename=f"document-{index}.txt",
            original_extension=".txt",
            content_type="text/plain",
            size_bytes=index + 1,
            storage_path=f"/tmp/document-{index}.txt",
            status=list(DocumentStatus)[index % len(DocumentStatus)],
        )
    for index in range(question_count):
        grounded = index % 2 == 0
        await QuestionRepository(session).create_question(
            user.id,
            collection_id=collections[0].id if collections and grounded else None,
            question_text=f"Question {index}?",
            embedding=[0.0] * get_settings().embedding_dim,
            answer_text="Answer.",
            ai_provider="ollama" if grounded else None,
            model_used="test-model" if grounded else None,
        )


@pytest.mark.asyncio
async def test_overview_requires_authentication(
    overview_client: httpx.AsyncClient,
) -> None:
    response = await overview_client.get(OVERVIEW_PATH)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
@pytest.mark.parametrize("token_kind", ["invalid", "expired"])
async def test_overview_rejects_invalid_and_expired_access_tokens(
    overview_client: httpx.AsyncClient,
    db_session: AsyncSession,
    token_kind: str,
) -> None:
    user = await _create_user(db_session, f"overview-{token_kind}")
    token = "not-a-valid-jwt"
    if token_kind == "expired":
        settings = get_settings()
        assert settings.secret_key is not None
        token = jwt.encode(
            {
                "sub": str(user.id),
                "exp": datetime.now(UTC) - timedelta(minutes=1),
            },
            settings.secret_key.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )

    response = await overview_client.get(
        OVERVIEW_PATH,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("is_active", "is_email_verified", "message"),
    [
        (False, True, "User account is inactive."),
        (True, False, "User email is not verified."),
    ],
)
async def test_overview_requires_active_verified_user(
    overview_client: httpx.AsyncClient,
    db_session: AsyncSession,
    is_active: bool,
    is_email_verified: bool,
    message: str,
) -> None:
    user = await _create_user(
        db_session,
        "overview-ineligible",
        is_active=is_active,
        is_email_verified=is_email_verified,
    )

    response = await overview_client.get(OVERVIEW_PATH, headers=_auth_headers(user))

    assert response.status_code == 403
    assert response.json()["error"]["message"] == message


@pytest.mark.asyncio
async def test_overview_returns_zeroes_and_private_no_store(
    overview_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "overview-empty-api")

    response = await overview_client.get(OVERVIEW_PATH, headers=_auth_headers(user))

    assert response.status_code == 200
    assert response.json() == {
        "total_documents": 0,
        "total_questions": 0,
        "total_collections": 0,
    }
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_overview_returns_exact_owner_totals_and_safe_fields(
    overview_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "overview-populated-api")
    other_user = await _create_user(db_session, "overview-isolated-api")
    await _create_resources(
        db_session,
        owner,
        document_count=4,
        question_count=3,
        collection_count=2,
    )
    await _create_resources(
        db_session,
        other_user,
        document_count=2,
        question_count=1,
        collection_count=1,
    )

    response = await overview_client.get(
        OVERVIEW_PATH,
        headers=_auth_headers(owner),
        params={
            "user_id": str(other_user.id),
            "collection_id": str(uuid.uuid4()),
            "status": "FAILED",
            "time_range": "all",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "total_documents": 4,
        "total_questions": 3,
        "total_collections": 2,
    }
    assert set(payload) == EXPECTED_FIELDS
    assert all(
        forbidden not in response.text.lower()
        for forbidden in (
            "user_id",
            "email",
            "filename",
            "content",
            "token",
            "provider",
        )
    )

    other_response = await overview_client.get(
        OVERVIEW_PATH,
        headers=_auth_headers(other_user),
    )
    assert other_response.json() == {
        "total_documents": 2,
        "total_questions": 1,
        "total_collections": 1,
    }


@pytest.mark.asyncio
async def test_overview_rejects_opaque_refresh_token_as_bearer(
    overview_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, "overview-refresh-token")
    raw_refresh_token = generate_secure_token()
    await UserRepository(db_session).create_refresh_token(
        user.id,
        uuid.uuid4(),
        hash_token(raw_refresh_token),
        datetime.now(UTC) + timedelta(days=30),
    )

    response = await overview_client.get(
        OVERVIEW_PATH,
        headers={"Authorization": f"Bearer {raw_refresh_token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_overview_route_is_mounted_only_at_authenticated_v1_path() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}

    assert OVERVIEW_PATH in paths
    assert "/api/v1/overview" not in paths
    assert "/api/overview" not in paths
