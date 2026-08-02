from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.schemas import OverviewResponse


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (
            {
                "total_documents": 0,
                "total_questions": 0,
                "total_collections": 0,
            },
            {
                "total_documents": 0,
                "total_questions": 0,
                "total_collections": 0,
            },
        ),
        (
            {
                "total_documents": 12,
                "total_questions": 31,
                "total_collections": 4,
            },
            {
                "total_documents": 12,
                "total_questions": 31,
                "total_collections": 4,
            },
        ),
    ],
)
def test_overview_response_serializes_exact_non_negative_totals(
    values: dict[str, int],
    expected: dict[str, int],
) -> None:
    response = OverviewResponse.model_validate(values)

    assert response.model_dump() == expected
    assert set(response.model_dump()) == {
        "total_documents",
        "total_questions",
        "total_collections",
    }


@pytest.mark.parametrize(
    "field",
    ["total_documents", "total_questions", "total_collections"],
)
def test_overview_response_rejects_negative_totals(field: str) -> None:
    values = {
        "total_documents": 0,
        "total_questions": 0,
        "total_collections": 0,
    }
    values[field] = -1

    with pytest.raises(ValidationError):
        OverviewResponse.model_validate(values)
