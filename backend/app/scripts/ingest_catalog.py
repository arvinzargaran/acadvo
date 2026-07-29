"""CLI to ingest a real university course catalog into ``CatalogCourse``.

Usage:
    python -m app.scripts.ingest_catalog sfu --term 2024/fall
    python -m app.scripts.ingest_catalog sfu --term 2024/fall --departments cmpt,macm

Each school is an adapter (``app.ingest.<school>``). Add a school by writing an
adapter that returns ``list[CatalogRow]`` and registering it below. Real data
only — adapters fetch from official sources and never fabricate courses.
"""
import argparse
import asyncio
import logging

from app.database import async_session
from app.ingest import sfu, upsert_catalog


async def _run_sfu(term: str, departments: list[str] | None) -> None:
    rows = sfu.fetch_courses(term, departments)
    async with async_session() as db:
        n = await upsert_catalog(db, sfu.UNIVERSITY, rows, source=sfu.SOURCE)
    print(f"SFU: upserted {n} courses for {term} into '{sfu.UNIVERSITY}'.")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Ingest a real university course catalog.")
    sub = parser.add_subparsers(dest="school", required=True)

    p_sfu = sub.add_parser("sfu", help="Simon Fraser University (public course-outlines API)")
    p_sfu.add_argument("--term", default="2024/fall", help='e.g. "2024/fall", "2025/spring"')
    p_sfu.add_argument(
        "--departments",
        default=None,
        help="comma-separated dept codes to limit the crawl, e.g. cmpt,macm (default: all)",
    )

    args = parser.parse_args()
    if args.school == "sfu":
        depts = [d.strip() for d in args.departments.split(",")] if args.departments else None
        asyncio.run(_run_sfu(args.term, depts))


if __name__ == "__main__":
    main()
