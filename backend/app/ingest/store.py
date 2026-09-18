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

    # Last-line dedupe on the conflict key. Every adapter already dedupes, but a
    # single chunk containing the same course twice does not merely write it
    # twice — PostgreSQL aborts the whole statement with "ON CONFLICT DO UPDATE
    # command cannot affect row a second time", losing the entire ingest over one
    # repeated row.
    by_code: dict[str, dict] = {}
    for v in values:
        by_code[v["course_code"]] = v
    values = list(by_code.values())

    dialect = db.get_bind().dialect.name
    insert = pg_insert if dialect == "postgresql" else sqlite_insert

    # Chunked because a single INSERT ... VALUES carries one bind parameter per
    # column per row, and both backends cap that: PostgreSQL (asyncpg) at 32,767,
    # SQLite lower still. A whole university does not fit. SFU's 1,853 courses
    # times 11 columns came to 20,383 and squeaked under the ceiling, which is
    # the only reason this held — the first genuinely large ingest (UofT, several
    # thousand courses across three campuses) fetched every page correctly and
    # then died on the write with "the number of query arguments cannot exceed
    # 32767", losing the entire crawl.
    for chunk in _chunks(values, _CHUNK_ROWS):
        await _upsert_chunk(db, insert, chunk, dialect, now)

    await db.commit()
    return len(values)


# One row costs len(_COLUMNS) parameters; stay well under the tighter of the two
# backend ceilings so the same path works on SQLite in tests and PostgreSQL in
# production.
_MAX_BIND_PARAMS = 20000
_COLUMN_COUNT = 11
_CHUNK_ROWS = _MAX_BIND_PARAMS // _COLUMN_COUNT


def _chunks(rows: list, size: int):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


async def _upsert_chunk(db, insert, chunk: list, dialect: str, now) -> None:
    stmt = insert(CatalogCourse).values(chunk)
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
