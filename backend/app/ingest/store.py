"""Generalized, idempotent upsert of ingested courses into ``CatalogCourse``.

Any adapter produces ``CatalogRow`` dicts; this module writes them with an
ON CONFLICT (university, course_code) upsert so re-running an ingestion refreshes
existing rows in place (name/credits/prereqs/gate/source) without duplicating.

The upsert is dialect-aware (PostgreSQL in production, SQLite under the test
harness) so the same write path is exercised everywhere.
"""
import uuid
from datetime import datetime, timezone
from typing import TypedDict

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CatalogCourse


class CatalogRow(TypedDict, total=False):
    course_code: str          # canonical, e.g. "CMPT 225"
    course_name: str
    credits: float
    subject_faculty: str | None
    prerequisites: list[list[str]]
    gpa_gate: dict | None


async def upsert_catalog(
    db: AsyncSession,
    university: str,
    rows: list[CatalogRow],
    source: str,
) -> int:
    """Upsert ``rows`` for ``university`` tagged with ``source``. Returns the number
    of rows written. Caller owns the transaction lifecycle beyond this commit."""
    if not rows:
        return 0

    now = datetime.now(timezone.utc)
    values = [
        {
            "id": uuid.uuid4(),
            "university": university,
            "course_code": r["course_code"],
            "course_name": r["course_name"],
            "credits": float(r.get("credits", 3.0)),
            "subject_faculty": r.get("subject_faculty"),
            "prerequisites": r.get("prerequisites") or [],
            "gpa_gate": r.get("gpa_gate"),
            "source": source,
            "updated_at": now,
        }
        for r in rows
    ]

    dialect = db.get_bind().dialect.name
    insert = pg_insert if dialect == "postgresql" else sqlite_insert
    stmt = insert(CatalogCourse).values(values)
    set_ = {
        "course_name": stmt.excluded.course_name,
        "credits": stmt.excluded.credits,
        "subject_faculty": stmt.excluded.subject_faculty,
        "prerequisites": stmt.excluded.prerequisites,
        "gpa_gate": stmt.excluded.gpa_gate,
        "source": stmt.excluded.source,
        "updated_at": now,
    }
    # PostgreSQL matches the conflict by named constraint; SQLite matches by the
    # unique index's columns.
    if dialect == "postgresql":
        stmt = stmt.on_conflict_do_update(
            constraint="uq_catalog_university_course_code", set_=set_
        )
    else:
        stmt = stmt.on_conflict_do_update(
            index_elements=["university", "course_code"], set_=set_
        )

    await db.execute(stmt)
    await db.commit()
    return len(values)
