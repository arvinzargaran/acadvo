"""CLI to ingest a real university course catalog into ``CatalogCourse``.

Usage:
    python -m app.scripts.ingest_catalog sfu --term 2024/fall
    python -m app.scripts.ingest_catalog sfu --term 2024/fall --departments cmpt,macm
    python -m app.scripts.ingest_catalog waterloo            # current term, all subjects
    python -m app.scripts.ingest_catalog waterloo --subjects CS,MATH
    python -m app.scripts.ingest_catalog ubc                 # both campuses
    python -m app.scripts.ingest_catalog uoft                # all three campuses
    python -m app.scripts.ingest_catalog uoft --campuses artsci
    python -m app.scripts.ingest_catalog york                # whole university, from York's catalog API
    python -m app.scripts.ingest_catalog york --subjects EECS,MATH
    python -m app.scripts.ingest_catalog york-bundled        # the hand-entered 22-course CS seed

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

from app.config import settings
from app.database import async_session
from app.ingest import checklist, sfu, ubc, uoft, upsert_catalog, waterloo, york


async def _run_sfu(term: str, departments: list[str] | None) -> None:
    rows = sfu.fetch_courses(term, departments)
    async with async_session() as db:
        n = await upsert_catalog(db, sfu.UNIVERSITY, rows, source=sfu.SOURCE)
    print(f"SFU: upserted {n} courses for {term} into '{sfu.UNIVERSITY}'.")


async def _run_waterloo(term: str | None, subjects: list[str] | None) -> None:
    key = settings.WATERLOO_API_KEY
    term = term or waterloo.current_term(key)
    if not term:
        print(
            "Could not determine the current Waterloo term. Pass --term with a "
            "termCode (e.g. 1259); GET /v3/Terms lists them.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    rows = waterloo.fetch_courses(term, key, subjects)
    if not rows:
        print(f"Waterloo returned no courses for term {term} — nothing written.", file=sys.stderr)
        raise SystemExit(1)

    async with async_session() as db:
        n = await upsert_catalog(db, waterloo.UNIVERSITY, rows, source=waterloo.SOURCE)
    print(f"Waterloo: upserted {n} courses for term {term} into '{waterloo.UNIVERSITY}'.")
    # Said on every run, not buried in a docstring: the API publishes no course
    # weight, so these are all written at the standard unit.
    print(
        f"NOTE: the Open Data API publishes no unit field, so every course is "
        f"written at Waterloo's standard {waterloo.STANDARD_UNITS} units. Courses "
        f"that are really 0.25 or 1.0 units will read as {waterloo.STANDARD_UNITS}."
    )


async def _run_ubc(campuses: list[str] | None) -> None:
    rows = ubc.fetch_courses(campuses)
    if not rows:
        print("UBC returned no courses — nothing written.", file=sys.stderr)
        raise SystemExit(1)
    async with async_session() as db:
        n = await upsert_catalog(db, ubc.UNIVERSITY, rows, source=ubc.SOURCE)
    where = ", ".join(campuses or ubc.CAMPUSES)
    print(f"UBC: upserted {n} courses from {where} into '{ubc.UNIVERSITY}'.")
    print(
        "NOTE: UBC writes the campus into the subject (CPSC_V / CPSC_O) and the "
        "two campuses share 591 subject-and-number pairs that are DIFFERENT "
        "courses, so the marker is kept. A student's bare 'CPSC 100' resolves to "
        "Vancouver."
    )


async def _run_uoft(campuses: list[str] | None) -> None:
    rows = uoft.fetch_courses(campuses)
    if not rows:
        print("UofT returned no courses — nothing written.", file=sys.stderr)
        raise SystemExit(1)
    async with async_session() as db:
        n = await upsert_catalog(db, uoft.UNIVERSITY, rows, source=uoft.SOURCE)
    where = ", ".join(campuses or uoft.CAMPUSES)
    print(f"UofT: upserted {n} courses from {where} into '{uoft.UNIVERSITY}'.")


async def _run_york(
    subjects: list[str] | None, *, details: bool, throttle: float, limit: int | None
) -> None:
    rows = york.fetch_courses(
        details=details, throttle=throttle, limit=limit, subjects=subjects
    )
    if not rows:
        print("York returned no courses — nothing written.", file=sys.stderr)
        raise SystemExit(1)
    async with async_session() as db:
        n = await upsert_catalog(db, york.UNIVERSITY, rows, source=york.SOURCE)
    gated = sum(1 for r in rows if r.get("gpa_gate"))
    withpre = sum(1 for r in rows if r.get("prerequisites"))
    print(f"York: upserted {n} courses into '{york.UNIVERSITY}'.")
    print(f"      {withpre} with prerequisites, {gated} with a GPA gate.")
    if not details:
        print(
            "NOTE: --no-details skips the per-course records, so every course was "
            "written at the standard 3.00 credits with no prerequisites."
        )


async def _run_york_bundled() -> None:
    """Seed the hand-entered York BSc CS catalog that ships with the app.

    Superseded by the `york` ingest above, which covers the whole university from
    York's own catalog. Kept because it runs at startup, so a deployment that has
    never run an ingest still has a real (if narrow) York catalog rather than
    none, and because it is the offline fallback if the catalog API changes.
    """
    from app.data.york_cs_catalog import YORK_UNIVERSITY, seed_catalog

    async with async_session() as db:
        n = await seed_catalog(db)
    print(f"York: upserted {n} hand-entered CS courses into '{YORK_UNIVERSITY}'.")
    print("NOTE: this covers EECS and MATH only — run `york` for the whole university.")


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
    rows = checklist.rows_from_parsed_document(parsed, university)
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

    p_uw = sub.add_parser(
        "waterloo", help="University of Waterloo (official Open Data API v3; needs WATERLOO_API_KEY)"
    )
    p_uw.add_argument(
        "--term", default=None, help='termCode, e.g. "1259" (default: the current term)'
    )
    p_uw.add_argument(
        "--subjects",
        default=None,
        help="comma-separated subject codes to limit the ingest, e.g. CS,MATH (default: all)",
    )

    p_ubc = sub.add_parser(
        "ubc", help="University of British Columbia (public calendar JSON:API; no key needed)"
    )
    p_ubc.add_argument(
        "--campuses",
        default=None,
        help=f"comma-separated: {', '.join(ubc.CAMPUSES)} (default: both)",
    )

    p_ut = sub.add_parser(
        "uoft", help="University of Toronto (public calendar JSON:API; no key needed)"
    )
    p_ut.add_argument(
        "--campuses",
        default=None,
        help=f"comma-separated: {', '.join(uoft.CAMPUSES)} (default: all three)",
    )

    p_yk = sub.add_parser(
        "york", help="York University (public Kuali catalog API; no key needed)"
    )
    p_yk.add_argument(
        "--subjects",
        default=None,
        help="comma-separated subjects to limit the ingest, e.g. EECS,MATH (default: all)",
    )
    p_yk.add_argument(
        "--no-details",
        action="store_true",
        help="one request only: codes and titles, no credits or prerequisites",
    )
    p_yk.add_argument("--throttle", type=float, default=0.12, help="delay between requests (s)")
    p_yk.add_argument("--limit", type=int, default=None, help="stop after N courses (for testing)")

    sub.add_parser(
        "york-bundled",
        help="York University (the hand-entered 22-course CS seed shipped with the app)",
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
    if args.school == "waterloo":
        subjects = [x.strip() for x in args.subjects.split(",")] if args.subjects else None
        try:
            asyncio.run(_run_waterloo(args.term, subjects))
        except waterloo.WaterlooAuthError as exc:
            print(f"{exc}", file=sys.stderr)
            raise SystemExit(2)
    elif args.school == "ubc":
        camps = [c.strip() for c in args.campuses.split(",")] if args.campuses else None
        asyncio.run(_run_ubc(camps))
    elif args.school == "uoft":
        camps = [c.strip() for c in args.campuses.split(",")] if args.campuses else None
        asyncio.run(_run_uoft(camps))
    elif args.school == "york":
        subs = [x.strip() for x in args.subjects.split(",")] if args.subjects else None
        asyncio.run(
            _run_york(subs, details=not args.no_details, throttle=args.throttle, limit=args.limit)
        )
    elif args.school == "york-bundled":
        asyncio.run(_run_york_bundled())
    elif args.school == "sfu":
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
