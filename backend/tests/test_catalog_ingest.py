"""Tests for the catalog ingestion store: idempotent upsert + provenance.

Uses sample rows (no network) so it locks in the write path any adapter relies on.
"""
import uuid

from sqlalchemy import select, func

from app.ingest.store import CatalogRow, upsert_catalog
from app.models.catalog import CatalogCourse
from app.services.catalog import get_catalog, has_seeded_catalog

UNI = "Test University"


def _rows():
    return [
        CatalogRow(
            course_code="CMPT 225",
            course_name="Data Structures and Programming",
            credits=3.0,
            subject_faculty="CMPT",
            prerequisites=[["CMPT 125", "CMPT 129"]],
            gpa_gate=None,
        ),
        CatalogRow(
            course_code="MACM 101",
            course_name="Discrete Mathematics I",
            credits=3.0,
            subject_faculty="MACM",
            prerequisites=[],
            gpa_gate=None,
        ),
    ]


async def test_upsert_inserts_rows_with_source(db):
    n = await upsert_catalog(db, UNI, _rows(), source="unit_test")
    assert n == 2
    rows = (
        await db.execute(select(CatalogCourse).where(CatalogCourse.university == UNI))
    ).scalars().all()
    assert {r.course_code for r in rows} == {"CMPT 225", "MACM 101"}
    assert all(r.source == "unit_test" for r in rows)
    cmpt = next(r for r in rows if r.course_code == "CMPT 225")
    assert cmpt.prerequisites == [["CMPT 125", "CMPT 129"]]


async def test_upsert_is_idempotent(db):
    await upsert_catalog(db, UNI, _rows(), source="unit_test")
    # Re-run with an updated name + credits; must UPDATE in place, not duplicate.
    updated = _rows()
    updated[0]["course_name"] = "Data Structures (renamed)"
    updated[0]["credits"] = 4.0
    await upsert_catalog(db, UNI, updated, source="reingest")

    total = await db.scalar(
        select(func.count()).select_from(CatalogCourse).where(CatalogCourse.university == UNI)
    )
    assert total == 2  # no duplicates
    cmpt = (
        await db.execute(
            select(CatalogCourse).where(
                CatalogCourse.university == UNI, CatalogCourse.course_code == "CMPT 225"
            )
        )
    ).scalar_one()
    assert cmpt.course_name == "Data Structures (renamed)"
    assert cmpt.credits == 4.0
    assert cmpt.source == "reingest"


async def test_ingested_catalog_is_verified_and_readable(db):
    await upsert_catalog(db, UNI, _rows(), source="unit_test")
    assert await has_seeded_catalog(UNI, db) is True
    catalog = await get_catalog(UNI, db)
    assert catalog["CMPT 225"]["source"] == "catalog"
    assert catalog["CMPT 225"]["prerequisites"] == [["CMPT 125", "CMPT 129"]]


async def test_empty_rows_noop(db):
    assert await upsert_catalog(db, UNI, [], source="unit_test") == 0
