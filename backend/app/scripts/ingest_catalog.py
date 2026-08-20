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
import json
import logging
import sys
from pathlib import Path

from app.database import async_session
from app.ingest import checklist, sfu, upsert_catalog


async def _run_sfu(term: str, departments: list[str] | None) -> None:
    rows = sfu.fetch_courses(term, departments)
    async with async_session() as db:
        n = await upsert_catalog(db, sfu.UNIVERSITY, rows, source=sfu.SOURCE)
    print(f"SFU: upserted {n} courses for {term} into '{sfu.UNIVERSITY}'.")


async def _run_checklist(
    path: Path, university: str, label: str, *, dry_run: bool
) -> None:
    """Promote an already-parsed degree checklist into the shared catalog.

    Input is the JSON ``document_parser`` produces, so the expensive/AI step is
    done once and reviewed by a human before anything is written. Review the
    file, then ingest it — that human check is what makes this a *verified*
    catalog rather than a model's opinion.
    """
    parsed = json.loads(path.read_text())
    rows = checklist.rows_from_parsed_document(parsed)
    if not rows:
        print("No usable courses in that document — nothing written.", file=sys.stderr)
        raise SystemExit(1)

    print(f"{len(rows)} course(s) parsed from {path.name} for '{university}':")
    for r in rows[:10]:
        gate = " [GPA gate]" if r.get("gpa_gate") else ""
        pre = f" prereqs={len(r.get('prerequisites') or [])}" if r.get("prerequisites") else ""
        print(f"  {r['course_code']:<16} {r['course_name'][:46]:<46} {r['credits']}cr{pre}{gate}")
    if len(rows) > 10:
        print(f"  ... and {len(rows) - 10} more")

    if dry_run:
        print("\nDry run — nothing written. Re-run without --dry-run to ingest.")
        return

    async with async_session() as db:
        n = await upsert_catalog(
            db, university, rows, source=checklist.source_label(label)
        )
    print(f"\nUpserted {n} courses into '{university}' (source: {checklist.source_label(label)}).")


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

    p_cl = sub.add_parser(
        "checklist",
        help="promote a parsed official degree checklist into the shared catalog",
    )
    p_cl.add_argument("path", type=Path, help="JSON produced by document_parser")
    p_cl.add_argument("--university", required=True, help='e.g. "York University"')
    p_cl.add_argument(
        "--label",
        required=True,
        help='provenance, e.g. "york-bsc-cs-2025-2026" — shown to students as the catalog source',
    )
    p_cl.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be ingested and exit without writing",
    )

    args = parser.parse_args()
    if args.school == "sfu":
        depts = [d.strip() for d in args.departments.split(",")] if args.departments else None
        asyncio.run(_run_sfu(args.term, depts))
    elif args.school == "checklist":
        asyncio.run(
            _run_checklist(
                args.path, args.university, args.label, dry_run=args.dry_run
            )
        )


if __name__ == "__main__":
    main()
