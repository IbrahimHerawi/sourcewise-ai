from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.schemas import (
    CollectionCreateRequest,
    CollectionResponse,
    CollectionUpdateRequest,
    PaginatedCollectionListResponse,
)


def test_create_normalizes_text_and_preserves_name_display_casing() -> None:
    request = CollectionCreateRequest(
        name="  Research Sources  ",
        description="  Primary source material  ",
    )

    assert request.name == "Research Sources"
    assert request.description == "Primary source material"


@pytest.mark.parametrize("description", ["", "   \t\n"])
def test_create_normalizes_empty_description_to_none(description: str) -> None:
    request = CollectionCreateRequest(name="Research", description=description)

    assert request.description is None


@pytest.mark.parametrize("name", ["", "   \t\n"])
def test_create_rejects_empty_name(name: str) -> None:
    with pytest.raises(ValidationError):
        CollectionCreateRequest(name=name)


def test_create_applies_length_limits_after_trimming() -> None:
    request = CollectionCreateRequest(
        name=f"  {'N' * 255}  ",
        description=f"  {'D' * 2_000}  ",
    )

    assert len(request.name) == 255
    assert request.description is not None
    assert len(request.description) == 2_000

    with pytest.raises(ValidationError):
        CollectionCreateRequest(name="N" * 256)

    with pytest.raises(ValidationError):
        CollectionCreateRequest(name="Research", description="D" * 2_001)


@pytest.mark.parametrize("description", [None, "", "   "])
def test_update_can_clear_description(description: str | None) -> None:
    request = CollectionUpdateRequest(description=description)

    assert request.description is None
    assert request.model_fields_set == {"description"}


def test_update_normalizes_supplied_text() -> None:
    request = CollectionUpdateRequest(
        name="  My RESEARCH  ",
        description="  Updated description  ",
    )

    assert request.name == "My RESEARCH"
    assert request.description == "Updated description"


def test_update_applies_length_limits_after_trimming() -> None:
    request = CollectionUpdateRequest(
        name=f"  {'N' * 255}  ",
        description=f"  {'D' * 2_000}  ",
    )

    assert request.name == "N" * 255
    assert request.description == "D" * 2_000

    with pytest.raises(ValidationError):
        CollectionUpdateRequest(name="N" * 256)

    with pytest.raises(ValidationError):
        CollectionUpdateRequest(description="D" * 2_001)


def test_update_rejects_empty_payload() -> None:
    with pytest.raises(ValidationError):
        CollectionUpdateRequest()


@pytest.mark.parametrize("name", [None, "", "   "])
def test_update_rejects_null_or_empty_name(name: str | None) -> None:
    with pytest.raises(ValidationError):
        CollectionUpdateRequest(name=name)


@pytest.mark.parametrize(
    "schema,payload",
    [
        (CollectionCreateRequest, {"name": "Research", "user_id": str(uuid4())}),
        (CollectionUpdateRequest, {"description": None, "unknown": True}),
    ],
)
def test_requests_reject_extra_fields(schema: type, payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError) as error:
        schema.model_validate(payload)

    assert any(item["type"] == "extra_forbidden" for item in error.value.errors())


def test_collection_response_excludes_user_id() -> None:
    now = datetime.now(UTC)
    response = CollectionResponse(
        id=uuid4(),
        name="Research",
        description=None,
        created_at=now,
        updated_at=now,
    )

    assert set(response.model_dump()) == {
        "id",
        "name",
        "description",
        "created_at",
        "updated_at",
    }

    with pytest.raises(ValidationError):
        CollectionResponse.model_validate(
            {
                **response.model_dump(),
                "user_id": uuid4(),
            }
        )


def test_paginated_collection_list_response() -> None:
    now = datetime.now(UTC)
    collection = CollectionResponse(
        id=uuid4(),
        name="Research",
        description="Sources",
        created_at=now,
        updated_at=now,
    )

    response = PaginatedCollectionListResponse(
        items=[collection],
        limit=20,
        offset=0,
        total=1,
    )

    assert response.items == [collection]
    assert response.limit == 20
    assert response.offset == 0
    assert response.total == 1
