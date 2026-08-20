"""Background worker for program research.

Why background, and not inline on the first request
---------------------------------------------------
A Search-grounded extraction reads several pages and takes tens of seconds. Doing
it inside the first student's advising request would mean one unlucky person
holds a spinner for a minute, a slow university site turns into a user-visible
timeout, and two students signing up at once do the work twice.

So the request path never waits. It calls ``ensure_research``, which records that
this program needs looking at and returns immediately; the student gets exactly
the behaviour the app already has for an uncovered program — honest gaps, nothing
invented — plus a status the UI can render as "working out your program's
requirements". When the job lands, every student in that program has rules,
including the one who triggered it.

Concurrency
-----------
One worker, one job at a time, per process. That is deliberate: research is the
expensive call in this system and the queue is the natural place to bound it. The
``pending -> running`` claim is a conditional UPDATE, so two workers (two
uvicorn processes) cannot pick up the same job, and a job row is unique per
``(university, program)`` so a thousand students in one program produce one run.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.research_client import ResearchDisabledError, is_research_enabled
from app.config import settings
from app.database import async_session
from app.models.requirement_rule import (
    JOB_FAILED,
    JOB_PENDING,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    ProgramResearchJob,
    RequirementRule,
)
from app.research.program_rules import ResearchFailed, is_stale, run_research

logger = logging.getLogger("acadvo.research.runner")

# A program whose research has failed this many times is left alone until someone
# asks for it explicitly. Retrying forever burns the research budget on the same
# university whose pages we cannot read.
MAX_ATTEMPTS = 3

# Gap before a failed job is retried, so a transient outage recovers on its own
# without a failing one hammering the provider.
RETRY_AFTER = timedelta(hours=6)

# How often the worker looks for pending work. Research is a once-per-program
# event, so this is a slow poll by design.
POLL_SECONDS = 30

# A job stuck in `running` longer than this is assumed to have died with its
# process; it becomes claimable again rather than blocking the program forever.
STALE_RUNNING_AFTER = timedelta(minutes=30)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; comparisons here must not crash on them."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def needs_research(db: AsyncSession, university: str, program: str) -> bool:
    """True when this program has no usable cached rules.

    Stale rules count as "needs research" for the *queue* but are still served to
    students meanwhile — see ``program_rules.is_stale``. Refreshing in the
    background is the whole point: nobody should lose advising because a calendar
    turned over.
    """
    result = await db.execute(
        select(RequirementRule.extracted_at).where(
            RequirementRule.university == university,
            RequirementRule.program == program,
        )
    )
    timestamps = list(result.scalars())
    if not timestamps:
        return True
    return all(is_stale(ts) for ts in timestamps)


async def ensure_research(
    db: AsyncSession,
    university: str | None,
    program: str | None,
    urls: list[str] | None = None,
) -> ProgramResearchJob | None:
    """Queue research for ``(university, program)`` if it is needed and not already
    queued. Never raises into the caller — a failure to enqueue must not turn a
    working advising request into an error.

    Returns the job row (existing or new), or ``None`` when nothing was queued.
    """
    if not university or not program or not is_research_enabled():
        return None
    if not settings.PROGRAM_RESEARCH_ENABLED:
        return None

    try:
        if not await needs_research(db, university, program):
            return None

        existing = await db.scalar(
            select(ProgramResearchJob).where(
                ProgramResearchJob.university == university,
                ProgramResearchJob.program == program,
            )
        )
        if existing is not None:
            if existing.status in (JOB_PENDING, JOB_RUNNING):
                return existing
            if existing.status == JOB_FAILED:
                if existing.attempts >= MAX_ATTEMPTS:
                    return existing
                finished = _aware(existing.finished_at)
                if finished and _now() - finished < RETRY_AFTER:
                    return existing
            # Succeeded-but-stale, or failed and eligible for another try.
            if urls:
                existing.source_urls = list(urls)
            existing.status = JOB_PENDING
            existing.requested_at = _now()
            existing.started_at = None
            existing.finished_at = None
            await db.commit()
            return existing

        job = ProgramResearchJob(
            university=university,
            program=program,
            status=JOB_PENDING,
            source_urls=list(urls or []),
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        logger.info("research: queued %s / %s", university, program)
        return job
    except IntegrityError:
        # Another request won the race on the unique (university, program)
        # constraint. That is the constraint doing its job, not an error.
        await db.rollback()
        return None
    except Exception:
        await db.rollback()
        logger.exception("research: could not queue %s / %s", university, program)
        return None


async def request_refresh(
    db: AsyncSession, university: str, program: str, urls: list[str] | None = None
) -> ProgramResearchJob:
    """Force a re-research, ignoring TTL and the failed-attempt ceiling.

    ``ensure_research`` deliberately refuses to retry a program that has failed
    ``MAX_ATTEMPTS`` times — otherwise one unreadable university consumes the
    research budget on every request. This is the explicit override for when
    something changed (the calendar was republished, the pages moved), so it
    resets the attempt counter rather than merely re-queueing under the old one.
    """
    job = await get_job(db, university, program)
    if job is None:
        job = ProgramResearchJob(university=university, program=program)
        db.add(job)
    if urls:
        job.source_urls = list(urls)
    job.status = JOB_PENDING
    job.attempts = 0
    job.last_error = None
    job.requested_at = _now()
    job.started_at = None
    job.finished_at = None
    await db.commit()
    await db.refresh(job)
    logger.info("research: refresh requested for %s / %s", university, program)
    return job


async def get_job(
    db: AsyncSession, university: str | None, program: str | None
) -> ProgramResearchJob | None:
    if not university or not program:
        return None
    return await db.scalar(
        select(ProgramResearchJob).where(
            ProgramResearchJob.university == university,
            ProgramResearchJob.program == program,
        )
    )


async def _claim_next(db: AsyncSession) -> ProgramResearchJob | None:
    """Atomically move one pending job to ``running`` and return it.

    The conditional UPDATE is what makes this safe across processes: two workers
    issue the same statement, exactly one reports a row changed.
    """
    # Free jobs abandoned by a dead process before looking for new ones.
    cutoff = _now() - STALE_RUNNING_AFTER
    await db.execute(
        update(ProgramResearchJob)
        .where(
            ProgramResearchJob.status == JOB_RUNNING,
            ProgramResearchJob.started_at < cutoff,
        )
        .values(status=JOB_PENDING, started_at=None)
        # Evaluate the criteria in the database, not against objects already in
        # the session. SQLite hands back naive datetimes, so the ORM's in-Python
        # synchronisation would try to compare them with the aware `cutoff` and
        # raise — and this is a bulk housekeeping update with no session state
        # worth keeping in sync anyway.
        .execution_options(synchronize_session=False)
    )
    await db.commit()

    candidate = await db.scalar(
        select(ProgramResearchJob)
        .where(ProgramResearchJob.status == JOB_PENDING)
        .order_by(ProgramResearchJob.requested_at)
        .limit(1)
    )
    if candidate is None:
        return None

    if not await claim(db, candidate):
        return None
    await db.refresh(candidate)
    return candidate


async def claim(db: AsyncSession, job: ProgramResearchJob) -> bool:
    """Take ownership of ``job``, or report that someone else already has.

    The ``status == JOB_PENDING`` predicate is the whole mechanism. Between the
    SELECT that found this job and this UPDATE, another worker — in another
    uvicorn process, with its own connection — may have claimed it. Both issue
    this statement; the database reports one row changed for exactly one of them.

    Dropping that predicate would still "work" in every single-process test while
    quietly letting two processes pay for the same research call, so it is
    tested directly rather than only through ``_claim_next``.
    """
    result = await db.execute(
        update(ProgramResearchJob)
        .where(
            ProgramResearchJob.id == job.id,
            ProgramResearchJob.status == JOB_PENDING,
        )
        .values(status=JOB_RUNNING, started_at=_now(), attempts=job.attempts + 1)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    return result.rowcount == 1


async def run_job(db: AsyncSession, job: ProgramResearchJob) -> None:
    """Execute one claimed job and record its outcome on the row.

    Every failure path writes ``last_error``. A research run that fails silently
    leaves a program permanently uncovered with no way to find out why.
    """
    try:
        written = await run_research(
            db, job.university, job.program, list(job.source_urls or [])
        )
        job.status = JOB_SUCCEEDED
        job.rules_extracted = written
        job.last_error = None
    except ResearchDisabledError as exc:
        job.status = JOB_FAILED
        job.last_error = str(exc)
    except ResearchFailed as exc:
        job.status = JOB_FAILED
        job.last_error = str(exc)
        logger.warning(
            "research: failed for %s / %s: %s", job.university, job.program, exc
        )
    except Exception as exc:  # noqa: BLE001 — the worker must survive any job
        job.status = JOB_FAILED
        job.last_error = f"{type(exc).__name__}: {exc}"[:1000]
        logger.exception(
            "research: crashed for %s / %s", job.university, job.program
        )
    finally:
        job.finished_at = _now()
        await db.commit()


async def process_once(db: AsyncSession) -> bool:
    """Claim and run at most one job. Returns True if one was processed."""
    job = await _claim_next(db)
    if job is None:
        return False
    await run_job(db, job)
    return True


async def _worker_loop() -> None:
    while True:
        try:
            async with async_session() as db:
                # Drain whatever is queued, then go back to sleep. Each iteration
                # is one research call, so this stays naturally rate-limited.
                while await process_once(db):
                    pass
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("research: worker iteration failed")
        await asyncio.sleep(POLL_SECONDS)


_worker_task: asyncio.Task | None = None


def start_worker() -> None:
    """Start the background worker, unless research is off or it is already up."""
    global _worker_task
    if not settings.PROGRAM_RESEARCH_ENABLED or not is_research_enabled():
        logger.info(
            "research: worker not started (GEMINI_API_KEY unset or research disabled)"
        )
        return
    if _worker_task is not None and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(_worker_loop(), name="acadvo-research-worker")
    logger.info("research: background worker started")


async def stop_worker() -> None:
    global _worker_task
    if _worker_task is None:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except (asyncio.CancelledError, Exception):  # noqa: B014 — shutdown must not raise
        pass
    _worker_task = None
