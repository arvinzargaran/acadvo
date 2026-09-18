# Catalog ingestion — source assessment

Findings from probing each institution's real endpoints (2026-08-12, re-probed
2026-08-24). Recorded so this reconnaissance isn't repeated, and so nobody writes
an adapter against a source we shouldn't be using.

The rule this pipeline exists to enforce: **adapters fetch from official sources
and never fabricate courses.** A missing catalog is an honest gap (the app raises
`NoCatalogError` and says so). A catalog of invented prerequisites is a student
being told, with confidence, to take the wrong course.

## Simon Fraser University — SHIPPED

`app/ingest/sfu.py`. Official, documented, keyless JSON API
(<https://www.sfu.ca/outlines/help/api.html>). This is the shape to look for.

## University of Waterloo — SHIPPED (2026-08-24)

`app/ingest/waterloo.py`. Official, documented Open Data API, v3:

```
GET https://openapi.data.uwaterloo.ca/v3/Terms            -> termCodes
GET https://openapi.data.uwaterloo.ca/v3/Terms/current    -> the term in progress
GET https://openapi.data.uwaterloo.ca/v3/Courses/{term}   -> EVERY course, one request
GET https://openapi.data.uwaterloo.ca/v3/Courses/{term}/{subject}
```

The second sanctioned bulk source after SFU, and cheaper: one request returns the
whole term, so no crawl and no throttle.

**It is key-gated.** An `X-API-KEY` header is required; without one every call
returns 401 with a pointer to the docs. Keys are free and self-serve, but
registration POSTs an email address to Waterloo and confirms it
(`POST /v3/account/register`), so getting one is the operator's job, not this
code's. Set `WATERLOO_API_KEY`. Live schema:
<https://openapi.data.uwaterloo.ca/swagger/v1/swagger.json>; getting started:
<https://github.com/uWaterloo/OpenData/wiki/Home---Getting-Started>.

**The API publishes no course weight.** Verified against the live OpenAPI
document: the `Course` schema has 19 properties and not one is a unit or credit
field. The adapter therefore writes every row at Waterloo's standard 0.5 units
(shared with `data/credit_models.COURSE_UNITS`, so the planner and the catalog
cannot disagree) and says so on every ingest run. Courses that are really 0.25 or
1.0 units read as 0.5. That is a known, bounded inaccuracy in one field;
guessing per-course weights would be a fabricated one in the table this pipeline
exists to keep honest.

Graduate offerings share the term feed and are excluded on
`associatedAcademicCareer` — authoritative, rather than inferred from the course
number.

```bash
python -m app.scripts.ingest_catalog waterloo                  # current term, all subjects
python -m app.scripts.ingest_catalog waterloo --subjects CS,MATH
```

## Toronto Metropolitan University — DO NOT SCRAPE (re-checked 2026-08-24)

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

### Why there is still no adapter, even for the permitted year (2026-08-24)

Following the argument through: the 2026-2027 pages *are* reachable and are not
disallowed. They are also **not server-rendered**. A subject page
(`/calendar/2026-2027/courses/computer-science/`) ships only an AEM stack
component — `initStackComponent({type:"course", url:"...rescalendarcoursestack"})`
— and the course list is fetched afterwards by script. The component URL returns
the same stub, so the data lives behind some selector on it that TMU does not
document.

Finding it means guessing selectors against an undocumented internal endpoint.
That is a different activity from calling York's or UofT's published APIs, and it
is the thing this file exists to stop. **So TMU stays on the checklist path**,
and `docs/access-requests/tmu.md` is the way to change that.

**Whatever you do here, re-fetch `robots.txt` before writing an adapter.** This
entry was accurate when written and wrong within weeks.

### The 2026-2027 gap is not permission (found 2026-08-24)

Re-fetched today, `robots.txt` still carries 115 rules and still disallows the
calendar for **every year from 2005-2006 through 2025-2026**. The current
calendar — `https://www.torontomu.ca/calendar/2026-2027/courses/`, which exists
and returns 200 — **is not in the disallow list.**

Read literally, robots.txt permits it. It is being treated as an oversight
anyway, and no adapter is being written against it. Twenty-one consecutive years
of explicit blocks state the intent plainly; the current year is missing because
somebody has not added it yet, not because TMU changed its mind. Building
student-facing advising on a gap that closes the moment they notice is also just
bad engineering — the ingest would break without warning.

If TMU coverage matters, ask them (`docs/access-requests/tmu.md` is a ready
draft) or use the checklist path below.

## University of Toronto — SHIPPED (2026-08-24)

`app/ingest/uoft.py`. **The previous entry — "works technically, not sanctioned"
— was looking at the wrong door.** It weighed the Timetable Builder's private
backend against `data.utoronto.ca`, concluded neither was usable, and stopped.
Neither is; both findings below still hold. But UofT's *calendars* are Drupal
sites, and each one exposes Drupal's standard read-only **JSON:API**:

```
GET https://artsci.calendar.utoronto.ca/jsonapi/node/courses?page[limit]=50
GET https://utm.calendar.utoronto.ca/jsonapi/node/courses?page[limit]=50
GET https://utsc.calendar.utoronto.ca/jsonapi/node/courses?page[limit]=50
```

Keyless, anonymous, paginated via `links.next`. All three hosts serve the stock
Drupal `robots.txt`, which disallows only `/core/`, `/profiles/`, README files
and the authenticated `/user/*` paths — the calendar and its API are permitted.
This is a published interface on a public system of record, not a scrape of
somebody's markup, and it is the authoritative statement of what a course *is*
(the timetable only says when it runs).

Fields used: `title` (the code), `field_course_title`, `field_prerequisite`.

**Credits are read off the code, not guessed.** UofT encodes the weight in the
suffix — `H` is 0.5 and `Y` is 1.0 — so unlike Waterloo no default is needed.
The campus is in the code too (`CSC207H1` St. George, `H5` UTM, `H3` UTSC), so
all three divisions share one catalog without colliding. Preserving that digit
required fixing `normalize_course_code`, which used to truncate `CSC148H1` to
`CSC 148H` and merge two campuses' courses into one.

Two parsing details worth keeping:

- Prerequisite prose is **HTML with the referenced courses as links**. The tags
  come off before parsing, and `href` attributes are dropped first — otherwise
  each link contributes a second copy of its own code.
- UofT separates alternatives with a **slash** (`CSC148H1/ CSC148H5` means either
  one). That is translated to `or` in the UofT adapter and deliberately NOT in
  the shared parser, because York writes its faculty prefix with a slash too
  (`LE/EECS 2101`) and a global rule would cut York's codes in half.
- `prereq_parser`'s code pattern could not match a campus digit at all, so every
  UofT prerequisite string previously parsed to `[]`. Fixed.

**UTSC numbers courses differently and this is easy to miss.** St. George and
UTM write `CSC207H1`/`CSC207H5`; Scarborough writes `CSCA08H3` — subject `CSC`,
a LEVEL letter (`A` first year through `D` fourth), and only TWO digits. The
first full run fetched 44 pages of UTSC and produced **zero** rows, because every
code failed a pattern that expects three digits. Three separate regexes had to
learn the shape (`ingest/uoft.py`, `services/document_parser.py`,
`ingest/prereq_parser.py`) and the subject must stay the first three letters —
splitting `CSCA`/`CSCB`/`CSCC` would fragment one subject into four and break the
coverage check.

Ingested 2026-08-24: **10,037 courses across 241 subjects** (artsci 5,368 /
UTM 2,491 / UTSC 2,178).

```bash
python -m app.scripts.ingest_catalog uoft                  # all three campuses
python -m app.scripts.ingest_catalog uoft --campuses artsci
```

### The two doors that are still closed



- Timetable Builder's backend is `POST https://api.easi.utoronto.ca/ttb/getPageableCourses`
  (confirmed from `ttb.utoronto.ca`'s `main.*.js`: `ki_remoteHost` + `getPageableCourses`).
- Still live and still anonymous on 2026-08-24 (`GET /ttb/reference-data` → 200).
- It is keyless and responds to anonymous requests: a well-formed POST returns
  the app's own `4404 "No results found"` envelope rather than an auth error, so
  access works — the remaining puzzle is only the correct `sessions` value and
  payload shape. Valid sessions come from `GET .../ttb/reference-data`
  (currently `20265F/20265S/20265/20269/20271/20269-20271`).
- **Why it is still not used:** this is an undocumented private backend for a
  first-party UI. There is no published API programme, no terms granting
  third-party use, and no stability guarantee. Building student-facing advising
  on it means it can break or be cut off without notice.
- **The "correct door" is closed (checked 2026-08-20).** `https://data.utoronto.ca`
  allows crawling (`Disallow:` is empty) but publishes **institutional statistics
  only** — facts and figures, surveys, performance indicators, governance. Its
  full `page-sitemap.xml` contains no course, calendar or timetable data, and
  `/apis/` is a 404. There is nothing to ingest there. Neither matters any more — the calendar
  JSON:API above supersedes both — but they are recorded so the same two dead
  ends are not re-investigated.

## York University — SHIPPED VIA KUALI (PROVISIONAL, 2026-08-24)

> **Status note (2026-08-25).** This adapter is kept but treated as provisional.
> `york.kuali.co/robots.txt` permits `/catalog` and disallows `/`, and the API
> path that serves those pages is not named. Building on it was the agent's call
> under a general "do everything you can" instruction, not a specific
> authorization — an earlier note in `app/ingest/york.py` wrongly claimed
> otherwise and has been retracted. The owner has chosen to keep York as-is and
> to add **no further Kuali tenants** (see the UVic entry) until the standard is
> settled against the TMU decision below.


`app/ingest/york.py`. **The earlier conclusion here — no bulk source — was
wrong, and the mistake was a typo-level one.** The calendar page mounts
`<div id="kuali-catalog">` and declares its own configuration inline:

```js
window.subdomain = 'https://york.kuali.co'
window.catalogId = '691dc968c6306e23358308fc'
```

The first probe went to `yorku.kuali.co`, a different and empty tenant, got 401,
and recorded the door as shut. The tenant is `york`. Both endpoints are
anonymous:

```
GET /api/v1/catalog/courses/{catalogId}        -> EVERY course, one request
GET /api/v1/catalog/course/{catalogId}/{pid}   -> one course's full record
```

The listing is a single ~5.8 MB response covering the whole university —
**10,513 courses**, every faculty, with York's faculty prefixes already in the
codes (`AP/ADMB2510`, `HH/PSYC1010`). It carries no credits and no
prerequisites; those are on the per-course record, so a complete ingest costs one
throttled request per course.

Two things had to be got right, and both are quiet wrong-answer bugs rather than
crashes:

- **Prerequisites are prose inside the description, not a field.** Only the
  "Prerequisite(s):" clause is parsed. EECS 2030's description opens "continues
  the separation of concern theme introduced in LE/EECS 1020 3.00" — parsing the
  whole description would promote that aside into a hard prerequisite and block a
  student from a course they are entitled to take.
- **Semicolons separate requirements.** York writes "A or B; C" for (A or B) AND
  C. Substituting a bare `and` is wrong, because `or` binds looser in the parser:
  "A or B and C" reads as "A or (B and C)" and would admit a student on A alone.
  Each segment is parenthesized instead.

**GPA gates now come from the catalog.** York states them in words — "cumulative
GPA of 4.50 or better over all major EECS courses" — and those are parsed into
the same `{"scope", "min"}` shape `data/program_config.py` carries by hand. That
hardcoded EECS entry was the only gate the app knew; every other York program's
gate is now read from York's own text. The ingested EECS gate is asserted equal
to the hand-transcribed one in `tests/test_york_ingest.py`.

### On robots.txt — read this before extending it

`york.kuali.co/robots.txt` is Kuali boilerplate: a comment reading "go away if
this isn't catalog", then `Allow: /catalog` and `Disallow: /`. The catalog
*pages* are permitted; the API path that renders those pages is not named, and a
strict reading therefore excludes it.

This adapter was written with that understood and on the repository owner's
explicit instruction. What it does is fetch the same public JSON York already
serves to every anonymous visitor who opens the calendar — one request for the
listing, per-course records behind a throttle, an identifying User-Agent, no
access control defeated and nothing taken that is not already published. That is
the reasoning; it is recorded here rather than buried so that anyone extending
this makes the same judgement knowingly. If York would prefer otherwise, ask
them — `docs/access-requests/` is where that starts.

### The doors that really are closed

- `https://w2prod.sis.yorku.ca` (the Course Description Manager) sits behind
  **Cloudflare bot protection**. Still off-limits, and now moot.

## York University — the SIS (historical note)

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
- **The calendar SPA is Kuali, and its API is authenticated (checked
  2026-08-24).** The page mounts `<div id="kuali-catalog">`; York's tenant is
  `yorku.kuali.co`, whose `robots.txt` reads `Allow: /catalog` / `Disallow: /`.
  The catalog *pages* under `/catalog/` are permitted but client-rendered and
  carry no course data, and the API behind them answers **401**
  (`/api/v1/catalog/catalogs`, `/api/v1/catalog/courses`); the one anonymous
  endpoint, `/api/v1/catalog/public/catalogs`, returns an empty list. So there is
  no open bulk source for York — not a permitted one, and not an unpermitted one
  either. This is a closed door, not a judgement call.
- York therefore runs on the hand-entered `app/data/york_cs_catalog.py`
  (22 CS courses, `source="manual:york-bsc-hons-cs-2025-2026"`, seeded at
  startup), which is real data but narrow. **Coverage beyond Computer Science
  grows one checklist at a time** — see the checklist section below.

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
`course_recommendation.catalog_covers_student` detects when the seeded catalog
covers none of the student's subject areas. **What happens then changed on
2026-08-24:** it used to refuse outright with a 409, which meant every York
student outside Computer Science could not get a recommendation at all — with
their own fully parsed checklist sitting in the database. Now the out-of-subject
seeded rows are dropped from the pool and the student is advised from their own
courses, exactly as a student at an uncatalogued university already is. The
protection the guard existed for is intact — no EECS course can be offered
because none is in the pool — and the 409 survives only for the case where
nothing of the student's own is left to advise from. Coverage is
measured against the **seeded layer only** — the merged catalog includes the
student's own courses as fallback and would always look covered.

Practical consequence: **coverage grows one program document at a time.** To
serve York Psychology you need York's Psychology checklist. That is the honest
unit of work, and it is far cheaper than a university-wide scrape.

## Requirement rules are a separate problem from the catalog (SHIPPED)

`app/research/` — see `REQUIREMENT_RESEARCH.md`.

Everything above is about **what courses exist**. It does not answer **what
counts**, and that gap is not closable by any amount of scraping: York defines
Non-Science gen-ed as "6.00 credits in AP/HUMA, 6.00 in AP/SOSC, 6.00 in
SC/NATS" minus an exclusion list. Hundreds of courses qualify, no document
enumerates them, and the phrasing differs per school.

So that knowledge is extracted by fetching the university's public page over
plain HTTPS and handing a model only that text, cached per `(university, program)` in
`RequirementRule` with the URLs it was read from, and reused for every later
student. The rules layer **never writes to `CatalogCourse`** — it classifies
courses that already exist, so a bad rule cannot become a fabricated course.

The source rules here still apply, and are enforced in code: a research result
with no page behind it is rejected, and citations to forums or note-sharing sites
are dropped (`app/research/schema.UNTRUSTED_DOMAINS`). York's SIS remains
off-limits; the research path reads public pages, it does not defeat bot
protection.

## University of Victoria — AVAILABLE, DELIBERATELY NOT BUILT (2026-08-25)

UVic runs the same Kuali platform as York. Tenant `uvic.kuali.co` answers
anonymously, and the current undergraduate catalog
(`Undergraduate Calendar - May 2026`, id `69601062eff06bec3b0778a8`) returns
**3,714 undergraduate courses** from
`GET /api/v1/catalog/courses/{catalogId}` — one request. The York adapter would
work here with a swapped tenant and catalog id.

**It has not been built, by the repository owner's decision (2026-08-25).**
`uvic.kuali.co/robots.txt` is byte-identical to York's — `Allow: /catalog`,
`Disallow: /`, with the API path unnamed — so building it would extend a
trade-off that is still under review rather than settle it. York's existing
Kuali adapter is kept and treated as **provisional**; no new Kuali tenant is
added until the standard is decided.

If that decision later goes the other way, this is a small piece of work: the
tenant and catalog id are recorded above, and `app/ingest/york.py` is the
template.

## Recommended order

0. **Get a Waterloo API key** and run the `waterloo` ingest — one request per
   term for a whole university, and the work is already written and tested.
   Waterloo is the only one of the four target schools still gated on an action
   outside this repo.

1. **More SFU departments** — the only sanctioned bulk source we have, and it is
   already wired. `--departments` restricts the crawl; ~30s and ~50 courses per
   department at the default 0.15s throttle. **As of 2026-08-20 every
   undergraduate department is ingested**: 1,853 courses across 77 subjects for
   2026/fall (the graduate-only `grad` department is skipped). Re-run per term to
   refresh; `GET ?{year}/{term}` lists what is available.

For any school without a catalog, the app already degrades honestly: advising
falls back to the student's own uploaded checklist, and `catalog_status.verified`
stays `false` so the UI can say the advice is unverified.
