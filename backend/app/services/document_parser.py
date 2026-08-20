import base64
import csv
import io
import json
import re

from app.ai.client import acomplete, get_groq_client, run_blocking, completion_text, vision_kwargs, json_kwargs
from app.config import settings
from app.services.uploads import pdf_to_text, spreadsheet_to_text

class UnreadableDocumentError(ValueError):
    """The file carried no text to give the model.

    Distinct from "the model could not make sense of it": a scanned or
    photographed checklist saved as a PDF has no selectable text at all, so
    pdfplumber returns an empty string and the extraction runs against nothing.
    The model then dutifully reports an empty degree, and the student is told
    their upload succeeded with zero courses found — the least useful possible
    answer, and one that looks like the app read the document and disagreed with
    them. This gets its own error so the router can say what is actually wrong
    and what to do about it.
    """


# Below this many characters there is nothing worth sending. A real checklist
# runs to thousands; a text layer of a few dozen characters is page furniture
# (a header, a page number) from a document that is otherwise an image.
MIN_EXTRACTED_CHARS = 80

SPREADSHEET_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
}

# ── Course-code normalization ────────────────────────────────────────
#
# Codes at York carry a faculty prefix (``LE/EECS 2101``, ``SC/MATH 1300``).
# Parsers frequently drop the prefix or the credit-value suffix. Other schools
# (e.g. SFU) use a bare ``SUBJECT NUMBER`` form with 3-digit numbers and an
# optional trailing letter (``CMPT 225``, ``MACM 101``, ``CMPT 105W``). These
# helpers restore a single canonical form so downstream services can key on it.
#
# Canonical form: ``<FACULTY>/<SUBJECT> <NUMBER>`` (e.g. ``LE/EECS 2101``) when
# the subject is a known York faculty, or the bare ``<SUBJECT> <NUMBER>`` form
# otherwise (e.g. ``CMPT 225``, ``CMPT 105W``).

# Subject -> faculty-letter prefix, for restoring dropped prefixes. Scoped to
# the faculties that appear in the York CS checklist; extend as needed. Subjects
# not in this map keep whatever prefix was supplied (or none).
FACULTY_PREFIXES: dict[str, str] = {
    "EECS": "LE",   # Lassonde School of Engineering
    "MATH": "SC",   # Faculty of Science
    "BIOL": "SC",
    "CHEM": "SC",
    "PHYS": "SC",
    "NATS": "SC",
    "EATS": "SC",
    "STS": "SC",
}

# Science subjects that legitimately belong in a "science lab" breadth bucket.
_SCIENCE_LAB_SUBJECTS = {"BIOL", "CHEM", "PHYS"}

# Matches an optional 2-letter faculty prefix, a 2-5 letter subject, a 3-OR-
# 4-digit catalog number, and an optional single trailing letter (e.g. the
# ``W`` in ``CMPT 105W``), tolerating loose spacing/slashes. Requiring at least
# 3 digits avoids false positives on prose ("MATH 12", "Chapter 300" fragments
# still need a subject-like token, but 1-2 digit numbers never match).
_CODE_RE = re.compile(
    r"(?:([A-Za-z]{2})\s*/\s*)?([A-Za-z]{2,5})\s*(\d{3,4})([A-Za-z]?)"
)


def normalize_course_code(raw: str | None) -> str:
    """Return the canonical form of a single course code.

    Uppercases the subject and any trailing letter, single-spaces the subject
    from the number, and drops any credit-value suffix. Restores/keeps the
    faculty prefix ONLY for known York faculties (``EECS 2101`` ->
    ``LE/EECS 2101``); for unknown subjects / non-York formats the bare
    ``SUBJECT NUMBER`` form is returned. If no course-code pattern is found the
    input is returned trimmed.

    Examples:
        ``"le/eecs 2101 3.00"`` -> ``"LE/EECS 2101"``
        ``"EECS2101"``          -> ``"LE/EECS 2101"``
        ``"MATH 1300"``         -> ``"SC/MATH 1300"``
        ``"SC/BIOL 1000 3.00"`` -> ``"SC/BIOL 1000"``
        ``"cmpt 225"``          -> ``"CMPT 225"``
        ``"CMPT225"``           -> ``"CMPT 225"``
        ``"CMPT 105w"``         -> ``"CMPT 105W"``
    """
    if not raw:
        return ""
    m = _CODE_RE.search(raw)
    if not m:
        return raw.strip()
    faculty, subject, number = m.group(1), m.group(2).upper(), m.group(3)
    number += m.group(4).upper()  # optional trailing letter, e.g. "105W"
    faculty = faculty.upper() if faculty else FACULTY_PREFIXES.get(subject)
    if faculty:
        return f"{faculty}/{subject} {number}"
    return f"{subject} {number}"


def extract_course_codes(text: str | None) -> list[str]:
    """Return every canonical course code found in a free-text string, in order."""
    if not text:
        return []
    out: list[str] = []
    for m in _CODE_RE.finditer(text):
        code = normalize_course_code(m.group(0))
        if code and code not in out:
            out.append(code)
    return out


def subject_of(code: str | None) -> str | None:
    """Return the subject (e.g. ``EECS``) of a canonical/near-canonical code."""
    if not code:
        return None
    m = _CODE_RE.search(code)
    return m.group(2).upper() if m else None


def _faculty_of(code: str | None) -> str | None:
    """Return the faculty prefix (e.g. ``LE``) of a canonical code, if present."""
    if not code:
        return None
    m = _CODE_RE.search(code)
    return m.group(1).upper() if (m and m.group(1)) else None


# ── Prerequisite / GPA-gate parsing ──────────────────────────────────

_GPA_GATE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([A-Za-z]{2,5})\s*GPA", re.IGNORECASE)


def parse_gpa_gate(notes: str | None) -> dict | None:
    """Extract a structured GPA gate from a notes string.

    ``"4.50 EECS GPA, LE/EECS 1022"`` -> ``{"scope": "EECS", "min": 4.5}``.
    Returns ``None`` when no gate phrase is present.
    """
    if not notes:
        return None
    m = _GPA_GATE_RE.search(notes)
    if not m:
        return None
    return {"scope": m.group(2).upper(), "min": float(m.group(1))}


def parse_prerequisites_from_notes(notes: str | None) -> list[list[str]]:
    """Parse a "Notes / Prerequisites" cell into requirement groups.

    Returns a list of groups; each group is a list of alternative canonical
    codes (AND across groups, OR within a group) — the same shape used by
    ``CatalogCourse.prerequisites``. Non-code prose (GPA gates, "Senior High
    School Calculus", "other specified courses") is ignored.

        ``"4.50 EECS GPA, LE/EECS 1019, LE/EECS 2030"``
            -> [["LE/EECS 1019"], ["LE/EECS 2030"]]
        ``"LE/EECS 1012 or LE/EECS 1015"``
            -> [["LE/EECS 1012", "LE/EECS 1015"]]
    """
    if not notes:
        return []
    groups: list[list[str]] = []
    # Comma / semicolon / newline separate AND-ed requirements.
    for segment in re.split(r"[,;\n]", notes):
        # " or " / "/" within a segment separate alternatives.
        alts = extract_course_codes(segment)
        if not alts:
            continue
        # A single segment that itself lists multiple codes joined by "or" is a
        # single OR-group; a segment with one code is its own AND-group.
        if re.search(r"\bor\b|/(?![A-Za-z]{2}\s)", segment, re.IGNORECASE) and len(alts) > 1:
            groups.append(alts)
        else:
            for code in alts:
                groups.append([code])
    return groups


# ── "A or B" alternative course collapsing ───────────────────────────
#
# Known alternative groups in the York CS checklist. Used as a safety net so
# alternatives are collapsed into ONE course even if the LLM emits them as
# separate rows.
_ALTERNATIVE_GROUPS: list[list[str]] = [
    ["LE/EECS 1012", "LE/EECS 1015"],
    ["LE/EECS 3215", "LE/EECS 3221"],
    ["LE/EECS 3401", "LE/EECS 3421", "LE/EECS 3461"],
]


# ── Extraction prompt ────────────────────────────────────────────────

EXTRACTION_PROMPT = """Analyze this degree document (academic calendar, degree checklist, transcript, or similar).
Extract ALL degree requirements and courses into this exact JSON format:

{
  "requirements": [
    {"bucket_name": "...", "credits_required": 0.0, "description": "...", "options_raw": "..."}
  ],
  "courses": [
    {
      "course_code": "...",
      "course_name": "...",
      "credit_value": 0.0,
      "requirement_bucket": "...",
      "term": null,
      "status": "not_scheduled",
      "grade": null,
      "prerequisites_raw": "...",
      "alternatives": []
    }
  ]
}

Rules:
- Preserve the FULL course code including any faculty prefix, e.g. "LE/EECS 2101", "SC/MATH 1300". Never drop the prefix.
- When a single row lists two or more courses joined by "or" (e.g. "LE/EECS 1012 or LE/EECS 1015", "LE/EECS 3401 or 3421 or 3461"), emit ONE course object: use the first code as course_code and put the OTHER alternative codes in the "alternatives" array. Do NOT emit separate course objects for each alternative.
- "prerequisites_raw" is the verbatim text from the "Notes / Prerequisites" column for that course (or "" if none).
- Group courses into logical requirement buckets (e.g. "Major Requirements", "Science Breadth", "Electives")
- Bucket courses by their subject: put MATH/EECS/ITEC courses in the major/math bucket. A "Foundational Science Lab" bucket is ONLY for BIOL/CHEM/PHYS lab science courses — never put MATH there.
- Match each course to the most appropriate requirement bucket
- status MUST be one of: "completed", "in_progress", "planned", "not_scheduled"
- Completion is a claim about this student's record, so it needs EVIDENCE IN THE
  DOCUMENT. Mark "completed" ONLY when the row carries a grade, or a tick/"Y"/
  "Passed"/"Completed" mark in a column that plainly means the course is done.
- NEVER infer completion from the year a course belongs to, from the student's
  start or graduation year, or from how far through a program they might be. A
  blank degree checklist is a list of what is REQUIRED, not a transcript: if its
  Enrolled/Passed columns are empty, every course is "not_scheduled".
- A term marker such as "F", "W", "Y", "F or W" or "Any" names WHEN a course is
  offered. It is never evidence that the course was taken or passed.
- If a course appears to be currently enrolled, mark status as "in_progress"
- If no clear status, mark as "not_scheduled"
- If no term is visible, set term to null
- If no grade is visible, set grade to null
- credit_value should be numeric (e.g. 0.5, 1.0, 3.0)
- credits_required per bucket should be the total credits needed for that bucket
- "options_raw" is the VERBATIM text listing which courses satisfy that bucket,
  copied character-for-character, including any sentence about courses that do
  NOT count. Example: "Foundational Science Lab Credits (6.00): SC/BIOL 1000
  3.00, SC/BIOL 1001 3.00, ... The following will not count towards this
  requirement: SC/BIOL 1500 3.00, ...". Do NOT summarise it and do NOT drop the
  exclusion sentence — a downstream parser reads the eligible courses out of this
  string, and a summary like "Foundational Science Lab credits" destroys the only
  record of which courses actually satisfy the requirement. Use "" when the
  document names no specific courses (e.g. it links to a web page instead).
- Return ONLY valid JSON, no markdown fences, no extra text"""


# Extraction lives in services.uploads, where it is bounded by page/sheet/row
# and character caps — a 10 MB PDF or XLSX is a compressed container and can
# otherwise expand into enough pages or cells to exhaust a worker. Both are
# blocking and CPU-bound, so every caller wraps them in run_blocking.
_spreadsheet_to_text = spreadsheet_to_text
_pdf_to_text = pdf_to_text


# ── Post-processing ──────────────────────────────────────────────────

_SCIENCE_LAB_BUCKET_KEYWORDS = ("science lab", "foundational science")
_MAJOR_BUCKET_NAME = "Major Requirements"
_DEGREE_TOTAL_BUCKET_NAME = "Degree Total Credits"
_DEGREE_TOTAL_CREDITS = 120.0


def _is_science_lab_bucket(name: str | None) -> bool:
    if not name:
        return False
    lower = name.lower()
    return any(kw in lower for kw in _SCIENCE_LAB_BUCKET_KEYWORDS)


def _collapse_alternatives(courses: list[dict]) -> list[dict]:
    """Collapse "A or B" alternative rows into a single course.

    Two mechanisms:
    1. A course whose ``course_code`` string already contains multiple codes
       (a single "A or B" cell): first code -> code, rest -> ``alternatives``.
    2. Separate rows that belong to a known alternative group are merged into
       the first-seen row, with the others recorded as ``alternatives``.
    """
    # (1) split multi-code course_code strings in place
    for course in courses:
        codes = extract_course_codes(course.get("course_code", ""))
        existing_alts = [normalize_course_code(a) for a in (course.get("alternatives") or []) if a]
        if len(codes) > 1:
            course["course_code"] = codes[0]
            existing_alts = codes[1:] + [a for a in existing_alts if a not in codes]
            # Also split an "A or B" course_name on "or".
            name = course.get("course_name") or ""
            name_parts = [p.strip() for p in re.split(r"\bor\b", name, flags=re.IGNORECASE) if p.strip()]
            if name_parts:
                course["course_name"] = name_parts[0]
        else:
            course["course_code"] = codes[0] if codes else normalize_course_code(course.get("course_code", ""))
        # de-dupe alternatives, drop any equal to the primary code
        course["alternatives"] = [
            a for i, a in enumerate(existing_alts) if a and a != course["course_code"] and a not in existing_alts[:i]
        ]

    # (2) merge separate rows sharing a known alternative group
    result: list[dict] = []
    consumed: set[int] = set()
    for idx, course in enumerate(courses):
        if idx in consumed:
            continue
        code = course.get("course_code", "")
        group = next((g for g in _ALTERNATIVE_GROUPS if code in g), None)
        if group:
            for jdx in range(idx + 1, len(courses)):
                if jdx in consumed:
                    continue
                other_code = courses[jdx].get("course_code", "")
                if other_code in group and other_code != code:
                    consumed.add(jdx)
                    if other_code not in course["alternatives"]:
                        course["alternatives"].append(other_code)
        result.append(course)
    return result


def _fix_buckets(courses: list[dict], requirements: list[dict]) -> None:
    """Reassign courses misfiled in a science-lab bucket by subject.

    A "Foundational Science Lab" bucket is only valid for BIOL/CHEM/PHYS. Any
    other subject (notably SC/MATH calculus) found there is moved to the major
    bucket, which is created if it does not already exist.
    """
    existing_names = {r.get("bucket_name") for r in requirements}
    moved_any = False
    for course in courses:
        bucket = course.get("requirement_bucket")
        subject = subject_of(course.get("course_code"))
        if _is_science_lab_bucket(bucket) and subject not in _SCIENCE_LAB_SUBJECTS:
            course["requirement_bucket"] = _MAJOR_BUCKET_NAME
            moved_any = True
    if moved_any and _MAJOR_BUCKET_NAME not in existing_names:
        requirements.append(
            {
                "bucket_name": _MAJOR_BUCKET_NAME,
                "credits_required": 0.0,
                "description": "Core major courses (auto-assigned).",
            }
        )


def _ensure_degree_total(requirements: list[dict]) -> None:
    """Ensure a "Degree Total Credits: 120" meta-bucket is present.

    The degree summary reads this bucket to drive the overall denominator
    (its ``degree_total_override``).
    """
    for req in requirements:
        name = (req.get("bucket_name") or "").lower()
        if "degree total" in name or "total credits" in name or "program total" in name:
            # Normalize the York CS honours total if it looks unset/wrong.
            if not req.get("credits_required"):
                req["credits_required"] = _DEGREE_TOTAL_CREDITS
            return
    requirements.append(
        {
            "bucket_name": _DEGREE_TOTAL_BUCKET_NAME,
            "credits_required": _DEGREE_TOTAL_CREDITS,
            "description": "Total credits required for the degree.",
        }
    )


def _postprocess(parsed: dict) -> dict:
    """Normalize, validate and enrich raw LLM output. Deterministic and
    idempotent — safe to run on any parser output regardless of the model."""
    requirements = parsed.get("requirements") or []
    courses = parsed.get("courses") or []

    for req in requirements:
        req["bucket_name"] = req.get("bucket_name") or ""
        try:
            req["credits_required"] = float(req.get("credits_required") or 0)
        except (TypeError, ValueError):
            req["credits_required"] = 0.0

    _VALID_STATUSES = {"completed", "in_progress", "planned", "not_scheduled"}
    _STATUS_MAP = {
        "not completed": "planned",
        "incomplete": "in_progress",
        "enrolled": "in_progress",
        "registered": "in_progress",
        "current": "in_progress",
        "taking": "in_progress",
        "done": "completed",
        "passed": "completed",
        "failed": "completed",
        "withdrawn": "not_scheduled",
        "dropped": "not_scheduled",
    }

    for course in courses:
        course["course_code"] = course.get("course_code") or ""
        course["course_name"] = course.get("course_name") or ""
        try:
            course["credit_value"] = float(course.get("credit_value") or 0)
        except (TypeError, ValueError):
            course["credit_value"] = 0.0
        raw_status = (course.get("status") or "not_scheduled").strip().lower()
        course["status"] = raw_status if raw_status in _VALID_STATUSES else _STATUS_MAP.get(raw_status, "planned")

        # Completion needs evidence, and a grade is the only evidence that
        # survives into the parsed record. The prompt forbids inferring it, but
        # prompts drift and this one already did: a blank York checklist came
        # back with a whole first year marked "completed" purely because the
        # student's start year made it plausible. That silently fabricates an
        # academic record, and every downstream number — GPA, credits, remaining
        # requirements, graduation date — is then wrong. Downgrading costs the
        # user a few clicks on the review screen; the alternative costs them a
        # plan built on courses they never took.
        if course["status"] == "completed" and not (course.get("grade") or "").strip():
            course["status"] = "planned"
        # Prerequisites from the notes column.
        notes_raw = course.get("prerequisites_raw") or ""
        course["prerequisites"] = parse_prerequisites_from_notes(notes_raw)
        gate = parse_gpa_gate(notes_raw)
        if gate:
            course["gpa_gate"] = gate
        course.setdefault("alternatives", [])

    # Collapse "A or B" alternatives, normalize codes.
    courses = _collapse_alternatives(courses)
    parsed["courses"] = courses

    # Fix subject/faculty bucket misclassification.
    _fix_buckets(courses, requirements)

    # Emit degree-total meta bucket.
    _ensure_degree_total(requirements)
    parsed["requirements"] = requirements

    return parsed


async def parse_degree_document(file_bytes: bytes, mime_type: str) -> dict:
    client = get_groq_client()

    if mime_type == "application/pdf":
        content_text = await run_blocking(_pdf_to_text, file_bytes)
        if len(content_text.strip()) < MIN_EXTRACTED_CHARS:
            raise UnreadableDocumentError(
                "This PDF has no readable text — it looks like a scan or a photo saved "
                "as a PDF. Upload it as an image (PNG or JPEG) instead and Acadvo will "
                "read it with the vision model."
            )
        response = await acomplete(
            client,
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": f"{EXTRACTION_PROMPT}\n\nDocument content:\n\n{content_text}"}],
            max_tokens=4096,
            **json_kwargs(),
        )
    elif mime_type in SPREADSHEET_MIME_TYPES:
        spreadsheet_text = await run_blocking(_spreadsheet_to_text, file_bytes, mime_type)
        if len(spreadsheet_text.strip()) < MIN_EXTRACTED_CHARS:
            raise UnreadableDocumentError(
                "This spreadsheet appears to be empty. Check that the checklist is on the "
                "first sheet and that the file saved correctly."
            )
        response = await acomplete(
            client,
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": f"{EXTRACTION_PROMPT}\n\nSpreadsheet content:\n\n{spreadsheet_text}"}],
            max_tokens=4096,
            **json_kwargs(),
        )
    else:
        # Image — use vision model
        b64 = base64.b64encode(file_bytes).decode()
        response = await acomplete(
            client,
            model=settings.GROQ_VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                ],
            }],
            max_tokens=4096,
            **vision_kwargs(),
        )

    text = completion_text(response)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError(
            "The AI response was not valid JSON. "
            "Try uploading a clearer document or a different format."
        )

    return _postprocess(parsed)
