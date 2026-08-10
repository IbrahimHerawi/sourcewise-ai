"""Enforce case-insensitive collection-name uniqueness per user."""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_collection_name_ci"
down_revision: str | None = "0006_content_ownership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORIGINAL_CONSTRAINT_NAME = "uq_collections_user_id"
CASE_INSENSITIVE_INDEX_NAME = "uq_collections_user_lower_name"


def _find_case_insensitive_duplicates() -> list[dict[str, str]]:
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                """
                SELECT
                    CAST(user_id AS text) AS user_id,
                    lower(name) AS normalized_name
                FROM collections
                GROUP BY user_id, lower(name)
                HAVING count(*) > 1
                ORDER BY CAST(user_id AS text), lower(name)
                """
            )
        )
        .mappings()
        .all()
    )
    return [
        {
            "user_id": row["user_id"],
            "normalized_name": row["normalized_name"],
        }
        for row in rows
    ]


def upgrade() -> None:
    """Replace exact-name uniqueness with case-insensitive uniqueness."""
    # Keep the preflight result stable until the new unique index exists.
    op.execute(sa.text("LOCK TABLE collections IN SHARE ROW EXCLUSIVE MODE"))
    duplicates = _find_case_insensitive_duplicates()
    if duplicates:
        affected_pairs = json.dumps(duplicates, ensure_ascii=True)
        raise RuntimeError(
            "Cannot enforce case-insensitive collection-name uniqueness. "
            "Resolve duplicate collections for these user/name pairs, then rerun "
            f"the migration: {affected_pairs}. No collection data was changed."
        )

    op.drop_constraint(ORIGINAL_CONSTRAINT_NAME, "collections", type_="unique")
    op.create_index(
        CASE_INSENSITIVE_INDEX_NAME,
        "collections",
        ["user_id", sa.text("lower(name)")],
        unique=True,
    )


def downgrade() -> None:
    """Restore exact-name uniqueness per user."""
    op.drop_index(CASE_INSENSITIVE_INDEX_NAME, table_name="collections")
    op.create_unique_constraint(
        ORIGINAL_CONSTRAINT_NAME,
        "collections",
        ["user_id", "name"],
    )
