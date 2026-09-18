"""The York catalog that ships with the app must actually reach the database.

Twenty-two courses were transcribed by hand from York's official 2025-2026 BSc
checklist and stored in ``app/data/york_cs_catalog.py`` — where nothing called
them. Every fresh deployment therefore came up with an empty ``CatalogCourse``
table: ``catalog_status.verified`` was False for York, and advising fell back to
whatever the student had uploaded, with no sign anything was missing.

Two things are locked in here: the seed writes, and it is idempotent (it runs on
every boot, so a second run must refresh rather than duplicate).
"""
from sqlalchemy import func, select

from app.data.york_cs_catalog import YORK_CS_COURSES, YORK_UNIVERSITY, SOURCE, seed_catalog
from app.models.catalog import CatalogCourse
from app.services.catalog import get_catalog_status, has_seeded_catalog


async def test_seed_catalog_writes_the_bundled_york_courses(db):
    assert not await has_seeded_catalog(YORK_UNIVERSITY, db)

    written = await seed_catalog(db)
    assert written == len(YORK_CS_COURSES) == 22

    status = await get_catalog_status(YORK_UNIVERSITY, db)
    assert status["verified"] is True
    assert status["course_count"] == 22
    assert status["sources"] == [SOURCE]
    # Coverage is reported by subject so a York Psychology student is still told
    # this catalog is not about their program.
    assert set(status["subjects"]) == {"EECS", "MATH"}


async def test_seed_catalog_is_idempotent_across_restarts(db):
    await seed_catalog(db)
    await seed_catalog(db)

    total = await db.scalar(
        select(func.count()).select_from(CatalogCourse).where(
            CatalogCourse.university == YORK_UNIVERSITY
        )
    )
    assert total == 22, "re-seeding on boot duplicated rows"


async def test_seeded_gate_survives_the_round_trip(db):
    """The 4.50 EECS GPA gate is the reason this catalog is worth seeding at all."""
    await seed_catalog(db)
    row = await db.scalar(
        select(CatalogCourse).where(
            CatalogCourse.university == YORK_UNIVERSITY,
            CatalogCourse.course_code == "LE/EECS 2030",
        )
    )
    assert row.gpa_gate == {"scope": "EECS", "min": 4.50}
    assert row.prerequisites == [["LE/EECS 1022"]]
