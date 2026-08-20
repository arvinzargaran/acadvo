# AI research + cached requirement rules — SHIPPED

Built 2026-08-12, from the handoff of the same date. `SOURCES.md` still records
which sources are usable and which are off-limits; nothing there changed.

## What was built

**The AI decides, and the decision is cached as data.** The first student in a
program triggers a research run that reads their university's public pages and
extracts that program's requirement *rules*; the result is stored with the URLs
it came from, and every student after them gets it instantly and identically. No
human authors a rule.

| Piece | Where |
|---|---|
| Gemini provider (Google Search grounding) | `app/ai/research_client.py` |
| Extraction contract + safety guards | `app/research/schema.py` |
| Prompt, extraction, persistence | `app/research/program_rules.py` |
| Background queue / worker | `app/research/runner.py` |
| Read path + matcher + verdicts | `app/services/requirement_rules.py` |
| "Does this count?" seam | `app/services/eligibility.satisfies_bucket` |
| Applied to recommendations | `app/services/course_recommendation.py` |
| Tables | `RequirementRule`, `ProgramResearchJob`, migration `016` |
| API | `GET/POST /course-advisor/program-rules[/refresh]` |
| UI | `ProgramRulesPanel.jsx`, `BucketVerdict.jsx` |

Groq was **not** replaced. It still does document parsing and catalog-grounded
recommendations, which are cheap and already grounded in data we hold. Gemini is
used for exactly one thing — reading live university pages — because the
OpenAI-compat shims do not expose search grounding and Groq cannot browse.

## The UX decision

**Background, with an honest placeholder.** The advising request calls
`ensure_research`, which enqueues and returns; it never waits on a web call. Until
rules land, the app behaves exactly as it did before (`NoCatalogError` /
`NoCoverageError`, no bucket labelling) and `GET /program-rules` returns a `state`
+ `message` written to be shown verbatim. Rationale is in `runner.py`'s docstring:
no request hangs, a failed run degrades instead of 500ing, and concurrent
first-students dedupe to one run via the unique `(university, program)` job row.

## The guards, and why each exists

Each is enforced in code, tested, and mutation-tested (see below).

1. **Grounding is mandatory.** `research()` refuses a response with no grounding
   chunks. An answer from the model's memory is indistinguishable from one read
   off the calendar and cannot be checked afterwards.
2. **Citations must be plausibly the university.** `validate_sources` drops
   user-generated-content domains and rejects a rule with nothing left. A
   grounded citation to r/yorku is not grounding.
3. **Exclusions are not options.** `normalize_rule` subtracts `excluded_codes`
   from `stated_codes`, and `evaluate_rule` checks exclusions *first*. Same rule
   `extract_bucket_options` enforces in the checklist parser, arriving by a
   different route.
4. **No vacuous rules.** Wildcard subjects and rules naming neither a subject nor
   a course are rejected — a rule matching everything is worse than none.
5. **`basis` only defaults down.** "stated" requires a quoted sentence; anything
   unparseable becomes "inferred".
6. **Inference is never rendered as fact.** A pattern match is `certainty:
   inferred` *even when the rule itself was stated*, because applying a rule to a
   course the page never named is a step the page did not take. The hedge lives in
   `BucketVerdict.label()`, not in each caller.
7. **`no_match` ≠ "does not count".** Three-valued outcomes, and the middle one
   says so in words.
8. **A rule can never introduce a course.** The research path has no write access
   to `CatalogCourse`. A hallucinated code inside a rule is inert — it fails to
   match anything. The existing validator in `generate_recommendations` still
   drops fabricated codes and flags ineligible ones underneath, unchanged.
9. **Rules are keyed on `(university, program)`**, unlike the catalog. A York
   Psychology rule never touches a York CS student.

## Verification

- Backend **434 passing** (was 325). Frontend **36** (was 22).
- Eval harness `tests/test_recommendation_evals.py` grew to 98 tests: a fourth
  dimension (requirement-rule state: none · supporting · excluding) crossed with
  every model misbehaviour, plus INV8 — no degree-credit claim without a citation,
  no inference rendered as a fact.
- New `tests/test_requirement_rules.py` (72 tests) organised by guard.
- **11 mutations, 11 caught.** Each guard above was deliberately broken and the
  suite failed. Script: not committed; re-derive from the guard list.
- Migration `016` applied and rolled back against real Postgres.
- End-to-end verified in the browser with a seeded rule (since removed).

## Retrieval: url_context, not Search grounding (this is the money question)

**Google Search grounding is a paid feature.** On the Gemini free tier every
grounded call returns `429 RESOURCE_EXHAUSTED` — verified across nine models,
including all current Flash and Pro variants. It is not a rate limit and has
nothing to do with the RPM/TPM figures on AI Studio's Rate Limit page; search
queries are metered and billed separately ($14/1k on Gemini 3, with the free
monthly allowance applying only once billing is enabled).

**`url_context` is free and does the part that matters.** It reads pages you
name, on the free tier, and reports a per-URL `URL_RETRIEVAL_STATUS`. So the
pipeline reads the university's page without paying; the only thing lost is
*discovery*, which is why a program's requirements URL is supplied by a student
(POST `/course-advisor/program-rules/research`) rather than searched for.

`settings.RESEARCH_USE_SEARCH_GROUNDING` turns discovery back on for a deployment
with billing enabled; it is off by default.

`url_retrieval_status` is *better* evidence than `groundingChunks`. Chunks say
"this informed the answer"; the status says whether the page loaded. That matters
because a model handed an unreachable URL will answer anyway, describing the page
from its address alone — observed in testing. Only `SUCCESS` becomes a citation.

## Verified live (free tier, 2026-08-14)

Against `https://artsci.calendar.utoronto.ca/section/Computer-Science`:

```
4 rules cached: First year [stated] · Second year [stated] ·
                Later years Core [stated] · Later years Electives [inferred]

CSC 369H  excluded/stated   "Does NOT count toward Later years - Electives"
CSC 490H  satisfies/stated  "Counts toward — named in the requirement"
PHY 151   no rule covers it
```

The exclusion is the real proof: `CSC 369H` is a core course and cannot
double-count as an elective, the model read that off the page, and the guard
surfaced it as a hard no.

## What is NOT done

- **Discovery.** Someone must supply the requirements URL per program. Guessing
  URL patterns scored 1/3 in testing (TMU and York both 404'd; UofT worked).
- **UofT course codes lose their campus digit.** `CSC110Y1` normalizes to
  `CSC 110Y`, so a UTM section and a St. George one collapse together.
  `normalize_course_code` needs a UofT-aware branch.
- **Transient 503s burn a retry.** Google returned `503 UNAVAILABLE` on one of
  two live runs; the worker records it as a failure against `MAX_ATTEMPTS`
  rather than distinguishing "try again" from "this will never work".
- **Cost is unbounded per program, not per student.** One research call per
  `(university, program)`, retried at most `MAX_ATTEMPTS` (3). That is the
  intended shape, but nothing caps total programs.
- **`level_floor` is the only structural constraint captured.** Real calendars
  also say things like "at most 6.00 credits at the 1000 level" — that is a
  *portfolio* constraint across courses, not a per-course test, and the current
  model cannot express it.
- Coverage still grows one program at a time, and the catalog problem
  (`SOURCES.md`) is unchanged: rules say what *counts*, not what *exists*.
