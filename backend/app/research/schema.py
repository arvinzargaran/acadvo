"""The contract a researched requirement rule must satisfy before it is stored.

Everything here is a guard. The research call itself is a language model reading
web pages, so the question is never "did it answer" — it always answers — but
"is this answer safe to persist and repeat to every future student in this
program". Each function below rejects one specific way the answer can be unsafe:

* ``validate_sources``      — the model answered from memory, not from a page.
* ``normalize_rule``        — a rule so broad it matches everything.
* ``normalize_rule``        — an exclusion list re-read as an option list.
* ``normalize_rule``        — ``basis`` quietly upgraded to "stated".

A rejected rule is not a disaster: the program stays uncovered, the app keeps
saying so, and nothing false is written down. A rule that is wrong *and stored*
is repeated to everyone, forever, and surfaces a year later when a student is
told a course they took did not count.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.requirement_rule import BASIS_INFERRED, BASIS_STATED, RULE_BASES
from app.services.document_parser import normalize_course_code, subject_of


class RuleRejected(ValueError):
    """A researched rule failed a safety guard and must not be stored."""


# Sites that are never authoritative for what satisfies a degree requirement, no
# matter how confidently they answer. Student forums and note-sharing services
# are the top organic results for exactly these queries, which is precisely why
# they have to be named: a grounded citation to r/yorku is not grounding.
UNTRUSTED_DOMAINS = frozenset(
    {
        "reddit.com",
        "quora.com",
        "chegg.com",
        "coursehero.com",
        "studocu.com",
        "ratemyprofessors.com",
        "ratemyprofessor.com",
        "wikipedia.org",
        "medium.com",
        "facebook.com",
        "x.com",
        "twitter.com",
        "youtube.com",
        "linkedin.com",
        "scribd.com",
        "numerade.com",
        "brainly.com",
    }
)

# A rule whose allowed-subject list is one of these matches every course ever
# offered. That is not a requirement rule, it is the absence of one, and stored
# as a rule it would silently mark every course as counting toward the bucket.
WILDCARD_SUBJECTS = frozenset({"*", "ANY", "ALL", "ANYTHING", "N/A", "NONE", "-", "ELECTIVE"})

MAX_SUBJECTS = 40
MAX_CODES = 400


def _root_domain(value: str) -> str:
    """Reduce a domain or URL to ``example.com`` for denylist comparison."""
    host = (value or "").strip().lower()
    host = re.sub(r"^[a-z]+://", "", host)
    host = host.split("/")[0].split("?")[0]
    host = host.removeprefix("www.")
    parts = [p for p in host.split(".") if p]
    if len(parts) < 2:
        return host
    # Handle ac.uk / edu.au / co.uk style two-part public suffixes.
    if len(parts) >= 3 and parts[-2] in {"ac", "edu", "co", "gov", "org", "net"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def validate_sources(sources: list[dict]) -> list[dict]:
    """Keep only citations that could plausibly be the university speaking.

    Raises ``RuleRejected`` when nothing survives. This is the anti-hallucination
    guard with teeth: the caller cannot store a rule whose only support is a
    forum post, and it cannot store one with no support at all, because
    ``ResearchResult`` only carries URLs the provider reports as actually
    retrieved.
    """
    # Known limitation: grounding chunks often arrive as provider redirect URLs
    # (vertexaisearch.cloud.google.com/...), with the real site only in `domain`
    # or `title`. Those fields are preferred below for exactly that reason. If a
    # chunk carries neither, the redirect host is all there is and the denylist
    # cannot see through it — such a citation is kept but is weak, so the first
    # extractions for any new university are worth eyeballing.
    kept: list[dict] = []
    for s in sources or []:
        uri = (s.get("uri") or "").strip()
        if not uri:
            continue
        root = _root_domain(s.get("domain") or s.get("title") or uri)
        if root in UNTRUSTED_DOMAINS:
            continue
        kept.append({"uri": uri, "title": (s.get("title") or "").strip(), "domain": root})
    if not kept:
        raise RuleRejected(
            "no citation from a source that could be the university — the answer "
            "was either ungrounded or grounded only in user-generated content"
        )
    return kept


def validate_requirements_url(raw: str) -> str:
    """Check a student-supplied requirements-page URL before it is queued.

    This URL is fetched server-side by the model provider, so it is an SSRF-shaped
    input even though we never fetch it ourselves: an attacker who can name the
    target gets to point a request somewhere. Restricting it to public http(s)
    origins and rejecting credentials, ports, and obvious internal hosts keeps it
    to what it is meant to be — a link to a university's public calendar page.

    Raises ``RuleRejected`` with a message safe to show the student.
    """
    from urllib.parse import urlparse

    url = (raw or "").strip()
    if not url:
        raise RuleRejected("no URL given")
    if len(url) > 2000:
        raise RuleRejected("that URL is too long")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RuleRejected("the URL must start with http:// or https://")
    if parsed.username or parsed.password:
        raise RuleRejected("the URL must not contain credentials")
    host = (parsed.hostname or "").lower()
    if not host or "." not in host:
        raise RuleRejected("that is not a public web address")
    if host in {"localhost"} or host.endswith(".local") or host.endswith(".internal"):
        raise RuleRejected("that is not a public web address")
    # Bare IP literals are never a university calendar and are the usual shape of
    # an attempt to reach something on the host's own network.
    if re.fullmatch(r"[0-9.]+|\[[0-9a-fA-F:]+\]", host):
        raise RuleRejected("give the university's web address, not an IP address")
    if _root_domain(host) in UNTRUSTED_DOMAINS:
        raise RuleRejected(
            "that is not an official university page — link the university's own "
            "calendar or program-requirements page"
        )
    return url


def _clean_subjects(raw) -> list[str]:
    out: list[str] = []
    for item in raw or []:
        value = str(item or "").strip().upper().replace(" ", "")
        if not value or value in WILDCARD_SUBJECTS:
            continue
        # Accept "AP/HUMA" and "HUMA" alike; reject anything that is not a
        # subject-shaped token (a full course code here means the model confused
        # a rule with a list, and the code belongs in stated_codes).
        if not re.fullmatch(r"(?:[A-Z]{2,4}/)?[A-Z]{2,6}", value):
            continue
        if value not in out:
            out.append(value)
    return out[:MAX_SUBJECTS]


def _clean_codes(raw) -> list[str]:
    out: list[str] = []
    for item in raw or []:
        code = normalize_course_code(str(item or ""))
        # normalize_course_code returns its input trimmed when it finds no
        # code-shaped token, so re-check rather than trusting a passthrough.
        if not code or not subject_of(code) or not re.search(r"\d{3,4}", code):
            continue
        if code not in out:
            out.append(code)
    return out[:MAX_CODES]


def _clean_level(raw) -> int | None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if 0 < value < 10000 else None


def _clean_credits(raw) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if 0 < value <= 200 else None


@dataclass
class ExtractedRule:
    """A validated rule, ready to persist. Construct via ``normalize_rule``."""

    bucket_name: str
    credits_required: float | None = None
    allowed_subjects: list[str] = field(default_factory=list)
    level_floor: int | None = None
    level_ceiling: int | None = None
    stated_codes: list[str] = field(default_factory=list)
    excluded_codes: list[str] = field(default_factory=list)
    excluded_subjects: list[str] = field(default_factory=list)
    source_quote: str | None = None
    notes: str | None = None
    basis: str = BASIS_INFERRED


def normalize_rule(raw: dict) -> ExtractedRule:
    """Turn one raw JSON rule from the model into a validated ``ExtractedRule``.

    Raises ``RuleRejected`` with a specific reason for anything unsafe.
    """
    if not isinstance(raw, dict):
        raise RuleRejected("rule is not an object")

    bucket = str(raw.get("bucket_name") or "").strip()
    if not bucket:
        raise RuleRejected("rule has no bucket_name")
    bucket = bucket[:255]

    allowed = _clean_subjects(raw.get("allowed_subjects"))
    stated = _clean_codes(raw.get("stated_codes"))
    excluded_codes = _clean_codes(raw.get("excluded_codes"))
    excluded_subjects = _clean_subjects(raw.get("excluded_subjects"))

    # An exclusion always wins over an option. Documents phrase both in the same
    # comma-separated shape, one sentence apart, so a model that mis-splits them
    # produces a rule recommending exactly the courses the requirement forbids —
    # the same failure `extract_bucket_options` guards against in the checklist
    # parser, arriving by a different route.
    if excluded_codes:
        blocked = set(excluded_codes)
        stated = [c for c in stated if c not in blocked]
    if excluded_subjects:
        blocked_subjects = set(excluded_subjects)
        allowed = [s for s in allowed if s not in blocked_subjects]

    # A rule that names neither a subject family nor a specific course matches
    # nothing it can justify — and the tempting "fall back to matching anything"
    # reading is the catastrophic one. Refuse it.
    if not allowed and not stated:
        raise RuleRejected(
            f"rule for {bucket!r} names no allowed subjects and no specific courses"
        )

    basis = str(raw.get("basis") or "").strip().lower()
    if basis not in RULE_BASES:
        # Default down, never up. An unparseable basis is not evidence that the
        # source stated the rule plainly.
        basis = BASIS_INFERRED
    if basis == BASIS_STATED and not (raw.get("source_quote") or "").strip():
        # "Stated" means there is a sentence to point at. Without one, the claim
        # that it was read directly is itself unsupported.
        basis = BASIS_INFERRED

    return ExtractedRule(
        bucket_name=bucket,
        credits_required=_clean_credits(raw.get("credits_required")),
        allowed_subjects=allowed,
        level_floor=_clean_level(raw.get("level_floor")),
        level_ceiling=_clean_level(raw.get("level_ceiling")),
        stated_codes=stated,
        excluded_codes=excluded_codes,
        excluded_subjects=excluded_subjects,
        source_quote=(str(raw.get("source_quote")).strip()[:2000] or None)
        if raw.get("source_quote")
        else None,
        notes=(str(raw.get("notes")).strip()[:2000] or None) if raw.get("notes") else None,
        basis=basis,
    )


def normalize_rules(raw_rules) -> tuple[list[ExtractedRule], list[str]]:
    """Normalize a list of raw rules. Returns ``(accepted, rejection_reasons)``.

    Partial success is the right outcome: one unusable bucket should not throw
    away three good ones, and the reasons are recorded on the job so a bad
    extraction is diagnosable instead of merely absent.
    """
    accepted: list[ExtractedRule] = []
    rejected: list[str] = []
    seen: set[str] = set()
    if not isinstance(raw_rules, list):
        return [], ["research output was not a list of rules"]
    for raw in raw_rules:
        try:
            rule = normalize_rule(raw)
        except RuleRejected as exc:
            rejected.append(str(exc))
            continue
        key = rule.bucket_name.strip().lower()
        if key in seen:
            rejected.append(f"duplicate bucket {rule.bucket_name!r}")
            continue
        seen.add(key)
        accepted.append(rule)
    return accepted, rejected
