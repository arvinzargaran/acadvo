# Catalog ingestion — source assessment

Findings from probing each institution's real endpoints (2026-08-12). Recorded so
this reconnaissance isn't repeated, and so nobody writes an adapter against a
source we shouldn't be using.

The rule this pipeline exists to enforce: **adapters fetch from official sources
and never fabricate courses.** A missing catalog is an honest gap (the app raises
`NoCatalogError` and says so). A catalog of invented prerequisites is a student
being told, with confidence, to take the wrong course.

## Simon Fraser University — SHIPPED

`app/ingest/sfu.py`. Official, documented, keyless JSON API
(<https://www.sfu.ca/outlines/help/api.html>). This is the shape to look for.

## Toronto Metropolitan University — DO NOT SCRAPE (re-checked 2026-08-20)

**This entry previously said "VIABLE, NEEDS PATH DISCOVERY". That was wrong, and
acting on it would have meant writing a scraper the site's own policy forbids.**

The earlier note read `robots.txt` as permitting the calendar. Re-fetched today,
`https://www.torontomu.ca/robots.txt` disallows the calendar for `User-agent: *`
— **every year from 2005-2006 through the current 2025-2026**, across all three
path prefixes:

```
Disallow: /calendar/2025-2026*
Disallow: /content/dam/calendar/2025-2026*
Disallow: /content/ryerson/calendar/2025-2026*
```

(63 of the 115 rules in that group are calendar paths.) The course-list URL the
old entry was looking for does exist — `/calendar/2025-2026/courses/` indexes
~90 subject pages — which makes this *more* dangerous, not less: the path is easy
to find and the block is easy to miss.

So TMU is in the same category as York's SIS. The data is reachable and we are
asked not to take it. If TMU coverage matters, the routes are the **checklist
path below** (a student's own program document, which they are entitled to
share) or asking TMU directly.

**Whatever you do here, re-fetch `robots.txt` before writing an adapter.** This
entry was accurate when written and wrong within weeks.

## University of Toronto — WORKS TECHNICALLY, NOT SANCTIONED

- Timetable Builder's backend is `POST https://api.easi.utoronto.ca/ttb/getPageableCourses`
  (confirmed from `ttb.utoronto.ca`'s `main.*.js`: `ki_remoteHost` + `getPageableCourses`).
- It is keyless and responds to anonymous requests: a well-formed POST returns
  the app's own `4404 "No results found"` envelope rather than an auth error, so
  access works — the remaining puzzle is only the correct `sessions` value and
  payload shape. Valid sessions come from `GET .../ttb/reference-data`
  (currently `20265F/20265S/20265/20269/20271/20269-20271`).
- **Why it is not shipped:** this is an undocumented private backend for a
  first-party UI. There is no published API programme, no terms granting
  third-party use, and no stability guarantee. Building student-facing advising
  on it means it can break or be cut off without notice.
- **The "correct door" is closed (checked 2026-08-20).** `https://data.utoronto.ca`
  allows crawling (`Disallow:` is empty) but publishes **institutional statistics
  only** — facts and figures, surveys, performance indicators, governance. Its
  full `page-sitemap.xml` contains no course, calendar or timetable data, and
  `/apis/` is a 404. There is nothing to ingest there. The remaining honest
  routes are asking UofT for access to the TTB backend, or the checklist path.

## York University — DO NOT SCRAPE THE SIS

- `https://w2prod.sis.yorku.ca` (the Course Description Manager, the obvious
  source) sits behind **Cloudflare bot protection** and returns an "Attention
  Required!" challenge page.
- Getting course data from it would mean defeating a bot-protection system the
  institution deliberately put there. Not doing that, and neither should the
  adapter.
- `https://calendars.students.yorku.ca` (the *public* academic calendar, a
  different system) is reachable and serves a stock Drupal `robots.txt` that
  disallows only `/core/`, `/admin/`, `/user/*` and `/search/` — the calendar
  itself is permitted. **But there is nothing there to fetch (checked
  2026-08-20).** The real entry point is `/academic-calendar#/programs`, a
  hash-routed client-side app: the served HTML contains no course codes, no
  program data, and no application bundle or API base — `drupalSettings` holds
  only `path`/`user`. Whatever renders that view is not reachable from the
  document, so there is no URL an adapter could call.
- **`atlas.yorku.ca` is not a course system.** It looks like one from the name and
  is linked off the calendar; it redirects to `atlas.cafe.uit.yorku.ca` and is the
  **phone and e-mail directory**. Dead end, recorded so nobody follows the same
  link twice.
- York currently runs on the hand-entered `app/data/york_cs_catalog.py`
  (22 CS courses, `source="manual"`), which is real data but narrow.

## Checklist ingestion — the general answer (SHIPPED)

`app/ingest/checklist.py` + `python -m app.scripts.ingest_catalog checklist`.

Most schools publish no course API, and the one that matters most here (York)
puts its course system behind bot protection. But the *authoritative document* is
public and students already hold it, and Acadvo can already read one — that is
what onboarding does. The only thing missing was that a parse landed in one
student's rows and helped nobody else.

So: parse the official checklist once, **review the JSON by hand**, then promote
it to `CatalogCourse`. This turns the catalog problem from a scraping problem
into a document problem, and it works for any school that publishes a checklist.

```bash
# 1. parse (AI step, once)
curl -b cookies -X POST localhost:8000/degree/parse-document \
  -F "file=@checklist.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" \
  -o parsed.json

# 2. inspect what would land — ALWAYS do this
python -m app.scripts.ingest_catalog checklist parsed.json \
  --university "York University" --label york-bsc-hons-cs-2025-2026 --dry-run

# 3. ingest
python -m app.scripts.ingest_catalog checklist parsed.json \
  --university "York University" --label york-bsc-hons-cs-2025-2026
```

**The review step is not optional.** On the real York BSc CS checklist this
produced 26 courses with prerequisites and GPA gates intact — but generic
elective rows came through with the *bucket label* as the course name
(`SC/BIOL 1000 — "Foundational Science Lab"`, `ECON 1000 — "Non-Science General
Education"`). Those need correcting before they become the name every student
sees. `--dry-run` prints exactly what would be written.

Provenance lands as `source="checklist:<label>"`, so `get_catalog_status` can
tell a student where their advising came from, and a later authoritative import
is distinguishable from this one.

### A checklist covers ONE program, and the catalog is keyed on university

This is the important limit. `CatalogCourse` is unique on `(university,
course_code)` — there is no program column, and there shouldn't be: EECS 2030 is
a York course whoever takes it. But it means ingesting a Computer Science
checklist marks *York* as having a catalog, when what York actually has is
**York's EECS and MATH courses**.

Without a guard, a York Psychology student then stops getting "no catalog" and
starts being recommended EECS courses. Confidently wrong is worse than blank.

So `get_catalog_status` reports a `subjects` list, and
`course_recommendation.catalog_covers_student` refuses (409 `NoCoverageError`)
when the seeded catalog covers none of the student's subject areas. Coverage is
measured against the **seeded layer only** — the merged catalog includes the
student's own courses as fallback and would always look covered.

Practical consequence: **coverage grows one program document at a time.** To
serve York Psychology you need York's Psychology checklist. That is the honest
unit of work, and it is far cheaper than a university-wide scrape.

## Requirement rules are a separate problem from the catalog (SHIPPED)

`app/research/` — see `NEXT_SESSION.md`.

Everything above is about **what courses exist**. It does not answer **what
counts**, and that gap is not closable by any amount of scraping: York defines
Non-Science gen-ed as "6.00 credits in AP/HUMA, 6.00 in AP/SOSC, 6.00 in
SC/NATS" minus an exclusion list. Hundreds of courses qualify, no document
enumerates them, and the phrasing differs per school.

So that knowledge is extracted by a model that can read the university's public
pages (Gemini, Google Search grounding), cached per `(university, program)` in
`RequirementRule` with the URLs it was read from, and reused for every later
student. The rules layer **never writes to `CatalogCourse`** — it classifies
courses that already exist, so a bad rule cannot become a fabricated course.

The source rules here still apply, and are enforced in code: a research result
with no grounding is rejected, and citations to forums or note-sharing sites are
dropped (`app/research/schema.UNTRUSTED_DOMAINS`). York's SIS remains off-limits;
the research path searches, it does not defeat bot protection.

## Recommended order

1. **More SFU departments** — the only sanctioned bulk source we have, and it is
   already wired. `--departments` restricts the crawl; ~30s and ~50 courses per
   department at the default 0.15s throttle. **As of 2026-08-20 every
   undergraduate department is ingested**: 1,853 courses across 77 subjects for
   2026/fall (the graduate-only `grad` department is skipped). Re-run per term to
   refresh; `GET ?{year}/{term}` lists what is available.

For any school without a catalog, the app already degrades honestly: advising
falls back to the student's own uploaded checklist, and `catalog_status.verified`
stays `false` so the UI can say the advice is unverified.
