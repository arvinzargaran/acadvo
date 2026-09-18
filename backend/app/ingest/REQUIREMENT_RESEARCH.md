# AI research and cached requirement rules

How Acadvo turns a program's published requirements page into reusable rules.
`SOURCES.md` is the companion document: it records which catalog sources are
usable and which are off-limits, and why.

## What was built

**The AI decides, and the decision is cached as data.** The first student in a
program triggers a research run that reads their university's public pages and
extracts that program's requirement *rules*; the result is stored with the URLs
it came from, and every student after them gets it instantly and identically. No
human authors a rule.

| Piece | Where |
|---|---|
| Page fetch + grounded extraction | `app/ai/research_client.py` |
| Extraction contract + safety guards | `app/research/schema.py` |
| Prompt, extraction, persistence | `app/research/program_rules.py` |
| Background queue / worker | `app/research/runner.py` |
| Read path + matcher + verdicts | `app/services/requirement_rules.py` |
| "Does this count?" seam | `app/services/eligibility.satisfies_bucket` |
| Applied to recommendations | `app/services/course_recommendation.py` |
| Tables | `RequirementRule`, `ProgramResearchJob`, migration `016` |
| API | `GET/POST /course-advisor/program-rules[/refresh]` |
| UI | `ProgramRulesPanel.jsx`, `BucketVerdict.jsx` |

Groq is the only provider. It does document parsing and catalog-grounded
recommendations as before; for research it is handed the text of a page **this
app fetched itself**, because Groq cannot browse and nothing here may be billed.
Doing our own retrieval turned out to be the stronger design anyway — the HTTP
status is ours to check, so "the model cited a page it never opened" is not a
state the system can reach.

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

## Retrieval: we fetch the page, the model never browses

**Everything here runs on the Groq free tier and nothing is billed.** That ruled
out the original design (Gemini's Google Search grounding, a metered feature that
429s on Google's free tier regardless of model), and it also rules out Groq's own
`groq/compound` web search: a search pulls several whole pages into one request,
and Groq applies its per-minute token allowance *per request*, so it comes back
`413 Request Entity Too Large` every time.

**So the app fetches the page itself** (`research_client.fetch_page`) — an
ordinary HTTPS GET, zero tokens — strips it to text, and gives the model that
text and nothing else. `settings.RESEARCH_USE_SEARCH_GROUNDING` turns discovery
back on for an account with the per-request headroom; it is off by default, which
is why a program's requirements URL is supplied by a student (POST
`/course-advisor/program-rules/research`) rather than searched for.

This is *better* evidence than any provider's grounding metadata, which only says
"this informed the answer". We saw the HTTP status ourselves, so a model handed
an unreachable URL cannot answer anyway from its address alone — the failure
observed in testing under the old design. Two extra guards come from owning the
fetch: a soft 404 (200 OK with a "Page Not Found" body, which university
calendars serve constantly) and a JS-rendered page that yields only navigation
chrome are both counted as *failed* retrievals, not as pages that said nothing.

**Watch the token ceiling.** `groq/compound` advertises 70,000 TPM against
gpt-oss-120b's 8,000 and looks like free headroom for a whole calendar page. It
is not — the compound systems are routers that delegate to the ordinary models
and are refused on *their* limits; the same request 413s under compound while its
own rate-limit headers still report 64,000 tokens remaining. Pages are therefore
trimmed to fit `GROQ_MAX_REQUEST_TOKENS` (`research_client.page_budget_chars`),
and the truncation is announced in the prompt so the model reports a partial read
rather than a confident absence.

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
- **Transient failures burn a retry.** A provider 5xx, or a university site that
  is briefly down, is recorded as a failure against `MAX_ATTEMPTS` rather than
  distinguishing "try again" from "this will never work".
- **Work is unbounded per program, not per student.** One research call per
  `(university, program)`, retried at most `MAX_ATTEMPTS` (3). That is the
  intended shape, but nothing caps total programs — and on the free tier the
  binding constraint is Groq's daily request allowance, not money.
- **`level_floor` is the only structural constraint captured.** Real calendars
  also say things like "at most 6.00 credits at the 1000 level" — that is a
  *portfolio* constraint across courses, not a per-course test, and the current
  model cannot express it.
- Coverage still grows one program at a time, and the catalog problem
  (`SOURCES.md`) is unchanged: rules say what *counts*, not what *exists*.
