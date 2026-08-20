"""Apply cached requirement rules: "does this course satisfy this bucket?"

This is the half of the design that runs for every student except the first.
``app/research/program_rules.py`` did the thinking once, against the university's
real pages; everything here is a lookup and a pattern match against what it
wrote down. No model call, no network, same answer for every student in the
program.

The verdict vocabulary is deliberately three-valued, and the middle value is the
important one:

``satisfies``  the rule matches the course
``excluded``   the source explicitly says this course does NOT count
``no_match``   the rule does not cover this course — which is **not** the same as
               "this course does not count". A rule captures what one page said;
               a course outside it may still count for a reason the page did not
               mention. Reporting ``no_match`` as a refusal would be exactly the
               overconfidence this module exists to avoid.

And every ``satisfies`` carries a certainty. ``stated`` means the source page
named this specific course. ``inferred`` means the course matched the rule's
subject/level pattern — a conclusion, not a reading, and it is labelled as one
every single time it reaches a student. A wrong "this counts toward your degree"
is the one error in this product that fails silently and surfaces a year later.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requirement_rule import BASIS_STATED, RequirementRule
from app.research.program_rules import is_stale
from app.services.document_parser import normalize_course_code, subject_of

# Verdict outcomes.
SATISFIES = "satisfies"
EXCLUDED = "excluded"
NO_MATCH = "no_match"

# Verdict certainty.
STATED = "stated"
INFERRED = "inferred"

_NUMBER_RE = re.compile(r"(\d{3,4})")


def _faculty_of(code: str) -> str | None:
    """``"AP/HUMA 1000"`` -> ``"AP"``; ``"CMPT 225"`` -> ``None``."""
    return code.split("/", 1)[0].upper() if "/" in code else None


def _level_of(code: str) -> int | None:
    m = _NUMBER_RE.search(code or "")
    return int(m.group(1)) if m else None


def subject_matches(code: str, subject_token: str) -> bool:
    """Does ``code`` belong to the subject family named by ``subject_token``?

    A rule may name the subject with its faculty (``"AP/HUMA"``) or without
    (``"HUMA"``). With a faculty, both halves must match — ``AP/HUMA`` and a
    hypothetical ``ES/HUMA`` are different offerings and a York rule that says
    one does not license the other. Without a faculty, the subject alone decides,
    so the rule still works at schools that do not use faculty prefixes at all.
    """
    token = (subject_token or "").strip().upper().replace(" ", "")
    if not token:
        return False
    code_subject = (subject_of(code) or "").upper()
    if not code_subject:
        return False
    if "/" in token:
        faculty, _, subject = token.partition("/")
        return code_subject == subject and (_faculty_of(code) or "") == faculty
    return code_subject == token


@dataclass
class BucketVerdict:
    """What a cached rule says about one course and one bucket."""

    bucket_name: str
    outcome: str
    certainty: str
    reason: str
    rule_basis: str = INFERRED
    source_urls: list[str] = field(default_factory=list)
    source_quote: str | None = None
    stale: bool = False
    credits_required: float | None = None

    @property
    def counts(self) -> bool:
        return self.outcome == SATISFIES

    @property
    def is_inference(self) -> bool:
        """True when a student must not be told this as a plain fact."""
        return self.certainty == INFERRED

    def label(self) -> str:
        """The user-facing sentence. Hedging is built in, not left to callers.

        Every caller that has to remember to add "probably" is a caller that will
        one day forget, and the failure is invisible until a student's graduation
        audit. So the hedge lives here, next to the data that determines it.
        """
        if self.outcome == EXCLUDED:
            return (
                f"Does NOT count toward {self.bucket_name} — "
                f"the requirement explicitly excludes it."
            )
        if self.outcome == NO_MATCH:
            return (
                f"Not covered by Acadvo's rule for {self.bucket_name}. "
                "That is not the same as 'does not count' — check with your advisor."
            )
        if self.certainty == STATED:
            base = f"Counts toward {self.bucket_name} — named in the requirement."
        else:
            base = (
                f"Likely counts toward {self.bucket_name}. This is Acadvo's "
                "inference from the requirement's subject and level rules, not a "
                "statement from your university — confirm before you rely on it."
            )
        if self.stale:
            base += " (Rule last checked over a term ago; calendars change yearly.)"
        return base

    def as_dict(self) -> dict:
        return {
            "bucket_name": self.bucket_name,
            "outcome": self.outcome,
            "certainty": self.certainty,
            "counts": self.counts,
            "is_inference": self.is_inference,
            "reason": self.reason,
            "rule_basis": self.rule_basis,
            "label": self.label(),
            "source_urls": list(self.source_urls),
            "source_quote": self.source_quote,
            "stale": self.stale,
            "credits_required": self.credits_required,
        }


def _source_uris(rule: RequirementRule) -> list[str]:
    out = []
    for s in rule.source_urls or []:
        if isinstance(s, dict) and s.get("uri"):
            out.append(s["uri"])
        elif isinstance(s, str) and s:
            out.append(s)
    return out


def evaluate_rule(
    rule: RequirementRule, course_code: str, *, now: datetime | None = None
) -> BucketVerdict:
    """Apply one stored rule to one course code.

    Order matters and is not arbitrary: exclusions are checked before anything
    else. A course can appear in both a subject family the rule allows and the
    "will not count" sentence beneath it — that is the normal shape of these
    documents, not an edge case — and the exclusion is the one the university
    means.
    """
    code = normalize_course_code(course_code)
    common = {
        "bucket_name": rule.bucket_name,
        "rule_basis": rule.basis,
        "source_urls": _source_uris(rule),
        "source_quote": rule.source_quote,
        "stale": is_stale(rule.extracted_at, now=now),
        "credits_required": rule.credits_required,
    }

    # 1. Explicit exclusions win over everything.
    if code in {normalize_course_code(c) for c in (rule.excluded_codes or [])}:
        return BucketVerdict(
            outcome=EXCLUDED,
            certainty=STATED,
            reason=f"{code} is on this requirement's exclusion list.",
            **common,
        )
    for token in rule.excluded_subjects or []:
        if subject_matches(code, token):
            return BucketVerdict(
                outcome=EXCLUDED,
                certainty=STATED,
                reason=f"{token} courses are excluded from this requirement.",
                **common,
            )

    # 2. The source named this exact course. The only case that is a reading
    #    rather than a conclusion.
    if code in {normalize_course_code(c) for c in (rule.stated_codes or [])}:
        return BucketVerdict(
            outcome=SATISFIES,
            certainty=STATED,
            reason=f"{code} is named in the requirement.",
            **common,
        )

    # 3. Pattern match on subject family and course level. Always an inference:
    #    even when the RULE was read plainly, applying it to a course the page
    #    never mentions is a step the page did not take.
    if not any(subject_matches(code, s) for s in rule.allowed_subjects or []):
        return BucketVerdict(
            outcome=NO_MATCH,
            certainty=INFERRED,
            reason=f"{code} is not in a subject this requirement accepts.",
            **common,
        )

    level = _level_of(code)
    if rule.level_floor is not None and (level is None or level < rule.level_floor):
        return BucketVerdict(
            outcome=NO_MATCH,
            certainty=INFERRED,
            reason=f"{code} is below this requirement's {rule.level_floor}-level floor.",
            **common,
        )
    if rule.level_ceiling is not None and (level is None or level > rule.level_ceiling):
        return BucketVerdict(
            outcome=NO_MATCH,
            certainty=INFERRED,
            reason=f"{code} is above this requirement's {rule.level_ceiling}-level ceiling.",
            **common,
        )

    return BucketVerdict(
        outcome=SATISFIES,
        certainty=INFERRED,
        reason=(
            f"{code} matches this requirement's subject rule "
            f"({', '.join(rule.allowed_subjects)})"
            + (f" at or above {rule.level_floor} level" if rule.level_floor else "")
            + "."
        ),
        **common,
    )


async def get_rules(
    university: str | None, program: str | None, db: AsyncSession
) -> list[RequirementRule]:
    """Every cached rule for a program. Empty list when none is researched yet."""
    if not university or not program:
        return []
    result = await db.execute(
        select(RequirementRule).where(
            RequirementRule.university == university,
            RequirementRule.program == program,
        )
    )
    return list(result.scalars())


def classify_course(
    rules: list[RequirementRule],
    course_code: str,
    *,
    bucket_name: str | None = None,
    now: datetime | None = None,
) -> BucketVerdict | None:
    """Best verdict for ``course_code`` across ``rules``, or ``None`` if uncovered.

    With ``bucket_name``, answers only about that bucket — the question the
    advisor actually asks when it has a bucket in mind. Without one, reports the
    strongest thing that can be said: an explicit exclusion first (a hard no is
    always worth surfacing), then a stated match, then an inferred one.
    """
    if not rules:
        return None

    if bucket_name:
        target = bucket_name.strip().lower()
        matched = [r for r in rules if r.bucket_name.strip().lower() == target]
        if not matched:
            return None
        return evaluate_rule(matched[0], course_code, now=now)

    verdicts = [evaluate_rule(r, course_code, now=now) for r in rules]
    for v in verdicts:
        if v.outcome == EXCLUDED:
            return v
    for v in verdicts:
        if v.outcome == SATISFIES and v.certainty == STATED:
            return v
    for v in verdicts:
        if v.outcome == SATISFIES:
            return v
    return None


def rules_summary(rules: list[RequirementRule], *, now: datetime | None = None) -> dict:
    """A user-facing description of what Acadvo knows about this program."""
    return {
        "bucket_count": len(rules),
        "stale": any(is_stale(r.extracted_at, now=now) for r in rules),
        "last_extracted_at": max((r.extracted_at for r in rules), default=None),
        "buckets": [
            {
                "bucket_name": r.bucket_name,
                "credits_required": r.credits_required,
                "allowed_subjects": list(r.allowed_subjects or []),
                "level_floor": r.level_floor,
                "level_ceiling": r.level_ceiling,
                "stated_codes": list(r.stated_codes or []),
                "excluded_codes": list(r.excluded_codes or []),
                "excluded_subjects": list(r.excluded_subjects or []),
                "basis": r.basis,
                # Spelled out rather than left for the UI to infer from `basis`:
                # this string is the difference between a student treating the
                # rule as their university's word and as ours.
                "basis_label": (
                    "Read directly from the university's page"
                    if r.basis == BASIS_STATED
                    else "Acadvo's reading of the university's page"
                ),
                "source_quote": r.source_quote,
                "source_urls": _source_uris(r),
                "extracted_at": r.extracted_at,
                "stale": is_stale(r.extracted_at, now=now),
            }
            for r in sorted(rules, key=lambda r: r.bucket_name.lower())
        ],
    }
