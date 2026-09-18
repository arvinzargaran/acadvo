# Acadvo

[![CI](https://github.com/arvinzargaran/acadvo/actions/workflows/ci.yml/badge.svg)](https://github.com/arvinzargaran/acadvo/actions/workflows/ci.yml)

**AI-powered academic and career advisor for Canadian university students.**

Acadvo helps students plan their degrees strategically, track career targets, build portfolios, and prepare for internships — with an AI advisor that doesn't just chat, but takes real actions. It knows your courses, grades, degree requirements, projects, and career goals, and uses that full picture to add courses to your plan, flag risks, build timelines, and generate semester-by-semester schedules aligned with your university's course catalog. Built specifically for the Canadian university system, with GPA and grading-scale support for 16 Canadian universities. Verified course catalogs — with prerequisites and enrolment gates — are ingested from each university's own catalog source: **York** (public Kuali catalog API, whole university), the **University of Toronto** (public calendar JSON:API, all three campuses), **Simon Fraser** (public course-outlines API), and the **University of Waterloo** (official Open Data API — needs a free `WATERLOO_API_KEY`). Adapters never fabricate a course: a prerequisite is only ever a code the university itself published, and a school with no catalog degrades honestly instead of guessing. Every source was assessed before it was used, and the ones deliberately *not* used are recorded with the reason — see `backend/app/ingest/SOURCES.md`.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Alembic |
| **Frontend** | React 19, Vite, Tailwind CSS, React Router v8, Axios |
| **AI** | Groq only, and it runs on the free tier — `openai/gpt-oss-120b` function calling (16 tools), `qwen/qwen3.6-27b` for image input, PDF/spreadsheet text extraction. Requirement-rule research reads the university's own page directly over HTTPS and gives the model only that text, so nothing here is metered beyond the Groq call itself |
| **Auth** | JWT (HS256) with refresh token rotation, bcrypt password hashing |
| **Infrastructure** | Docker Compose (PostgreSQL + backend + frontend) |

## Features

### Degree Planning
- Full CRUD for courses with inline editing (grades, semester, status, requirement bucket)
- Requirement buckets with credit progress tracking and at-risk detection
- AI semester-by-semester course plan — targets your university's catalog (course-code conventions per school), respects prerequisites, balances workload (max 5/semester), aligns with career goals
- Document import — upload a degree checklist (PDF, image, Excel, CSV) and the AI extracts requirements + courses automatically
- Prerequisite flow visualization and PDF export
- **Requirement rules, researched once per program** — electives and gen-ed are not lists, they are rules ("6.00 credits in AP/HUMA, minus these exclusions"), and hundreds of courses satisfy them. One student links their program's official requirements page; an AI run reads it and extracts those rules; the result is cached with its source URLs and reused for every student after them. A course is only ever said to satisfy a requirement alongside the page it was read from and a label saying whether the university stated it or Acadvo concluded it. Unresearched programs say so rather than guessing.

### AI Advisor
- 16 function-calling tools: add courses, create projects, flag risks, generate timelines, update profiles, search course catalogs, build semester plans, add degree requirements
- Multi-turn tool execution loop (up to 10 rounds per message) — the AI calls tools, reads results, and decides what to do next
- Full context on every call: degree progress, projects, career targets, upcoming deadlines
- Floating chat widget available on every page + dedicated full-screen career advisor

### Career Tracking
- Kanban pipeline (Researching → Applied → Interviewing → Offer / Rejected)
- Full-screen AI career advisor with live context panel (targets, timeline, pipeline counts)
- Resume upload with AI review — overall score, strengths, improvements, ATS tips
- Timeline events with deadline tracking

### Projects
- Project CRUD with priority levels, tech stack, deadlines, product framing
- Milestone tracking (pending → in progress → complete → overdue)
- Portfolio readiness scoring on dashboard

### DSA Prep
- Problem tracker by difficulty (easy/medium/hard) and topic (12 categories, 50+ problems)
- Weekly goal setting with progress ring
- All data persisted server-side per user (problems, stats, and weekly goal), with automatic one-time migration of any legacy localStorage goal

### Dashboard
- 14 widgets: GPA tracker, GPA calculator, credit progress, deadline countdown, portfolio score, readiness score, smart alerts, smart insights feed, next actions, getting started, weekly AI check-in, current courses, active milestones, upcoming deadlines
- Smart alerts analyze your data client-side: at-risk requirement buckets, overdue milestones, missing career targets
- AI-generated weekly progress summary

### Platform
- **Installable PWA** — web app manifest, offline app-shell caching via service worker (Workbox), iOS home-screen support; API routes are explicitly excluded from caching so authenticated data is never served stale
- **Privacy self-serve** — `/privacy` and `/terms` (linked from the landing footer, the registration consent tick, and Settings), plus Settings → *Download my data* (`GET /users/me/export`) and password-confirmed account deletion. See [Privacy and the legal pages](#privacy-and-the-legal-pages)
- **Observability** — structured JSON logging with per-request `X-Request-ID` tracing, AI tool-loop instrumentation (model-call latency, rounds, per-tool durations, token usage — never user content), and optional Sentry error tracking gated behind `SENTRY_DSN`

### Onboarding
- Guided multi-step wizard: profile → university → program → years → location → career goal → degree upload → courses → projects → career targets → review
- Document upload integration for auto-filling degree data
- Tooltip tour on first dashboard visit

## Setup

### Prerequisites

- Docker and Docker Compose
- A Groq API key ([get one here](https://console.groq.com/keys))

### Steps

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd acadvo
   ```

2. Create your environment file:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` and set your values:
   - `GROQ_API_KEY` — your Groq API key (required for all AI features)
   - `GROQ_MAX_REQUEST_TOKENS` — set to `8000` on Groq's free tier. Groq applies its per-minute token limit *per request*, so the semester planner and requirement research are refused outright (413) without this; with it they trim to fit.
   - `JWT_SECRET_KEY` — change to a random 32+ character string (run `openssl rand -hex 32`)
   - Other defaults work for local development

4. Start everything:
   ```bash
   docker-compose up --build
   ```

5. The app will be available at:
   - **Frontend:** http://localhost:5173
   - **Backend API:** http://localhost:8000
   - **API docs (Swagger):** http://localhost:8000/docs

### Running Without Docker

**Backend:**
```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --no-proxy-headers
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Make sure PostgreSQL is running and `DATABASE_URL` in `.env` points to it.

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | Async PostgreSQL connection string | Yes | `postgresql+asyncpg://acadvo:acadvo@db:5432/acadvo` |
| `DATABASE_URL_SYNC` | Sync PostgreSQL connection (Alembic) | Yes | `postgresql://acadvo:acadvo@db:5432/acadvo` |
| `POSTGRES_USER` | PostgreSQL username | Yes | `acadvo` |
| `POSTGRES_PASSWORD` | PostgreSQL password | Yes | `acadvo` |
| `POSTGRES_DB` | PostgreSQL database name | Yes | `acadvo` |
| `JWT_SECRET_KEY` | Secret for JWT signing — **change this** | Yes | `change-me-to-a-random-secret-at-least-32-chars` |
| `JWT_ALGORITHM` | JWT algorithm | No | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL | No | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL | No | `7` |
| `GROQ_API_KEY` | Groq API key | Yes (for AI) | — |
| `GROQ_MAX_REQUEST_TOKENS` | Ceiling on prompt + completion for one request; `8000` on the free tier, `0` (none) on a paid one | No | `0` |
| `GROQ_TIMEOUT_SECONDS` | Wall-clock ceiling on one model call. Raise only if a legitimate call is being cut off — the app retries transient failures itself, and an unbounded call holds a worker thread the rest of the API is queueing for | No | `30.0` |
| `GROQ_SDK_MAX_RETRIES` | Retries the Groq SDK performs on top of the app's own retry loop. `0` on purpose: two retry layers multiply (3 × 3 attempts × the timeout above) | No | `0` |
| `GROQ_MODEL` | Chat/JSON model id. Groq retires ids — check `/v1/models` before blaming the app | No | `openai/gpt-oss-120b` |
| `GROQ_VISION_MODEL` | Model used for image input (scanned checklists, résumé images) | No | `qwen/qwen3.6-27b` |
| `GROQ_VISION_REASONING_EFFORT` | `none` or `default` for Qwen; empty for a model that rejects the parameter | No | `none` |
| `GROQ_JSON_REASONING_EFFORT` | Reasoning effort on JSON-producing calls (plans, search, parsing). Empty omits the parameter | No | `low` |
| `RESEARCH_MODEL` | Model used to extract requirement rules from a fetched page | No | `openai/gpt-oss-120b` |
| `RESEARCH_SEARCH_MODEL` | Model used when search grounding is on (a Groq compound system, for its larger per-request token ceiling) | No | `groq/compound` |
| `RESEARCH_MAX_PAGE_CHARS` | Cap on how much of a fetched page is shown to the model | No | `48000` |
| `RESEARCH_USE_SEARCH_GROUNDING` | Let the model find requirement pages itself, instead of reading a supplied URL. Free, but a search exceeds the free tier's per-request token limit (413) | No | `False` |
| `REQUIREMENT_RULE_TTL_DAYS` | Days before a researched rule is re-checked in the background | No | `180` |
| `PROGRAM_RESEARCH_ENABLED` | Master switch for the background research worker | No | `True` |
| `COOKIE_SECURE` | Send auth cookies only over HTTPS — set `True` in production | No | `False` |
| `COOKIE_SAMESITE` | `lax` or `strict`. `none` is refused at startup when `DEBUG=False` | No | `lax` |
| `RATE_LIMIT_STORAGE_URI` | Shared store for rate limits. Empty = in-memory, which counts per worker; the prod compose sets Redis | No | (empty) |
| `FRONTEND_URL` | Base URL used to build verification and password-reset links | No | `http://localhost:5173` |
| `PUBLIC_API_URL` | Public origin of the API, used to build the `.ics` calendar feed URL | No | `http://localhost:8000` |
| `SMTP_HOST` | Mail server. Empty logs emails instead of sending them — load-bearing in production, see below | No | (empty) |
| `SMTP_PORT` | Mail server port | No | `587` |
| `SMTP_USER` / `SMTP_PASSWORD` | Mail server credentials | No | (empty) |
| `SMTP_STARTTLS` | Upgrade the SMTP connection with STARTTLS | No | `True` |
| `ALLOW_NO_SMTP` | Boot with no mail server configured. Without it the app refuses to start in production, because verification links would only reach the log | No | `False` |
| `EMAIL_FROM` / `EMAIL_FROM_NAME` | Sender address and display name | No | `no-reply@acadvo.app` / `Acadvo` |
| `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` | Lifetime of a password-reset link | No | `60` |
| `EMAIL_VERIFY_TOKEN_EXPIRE_MINUTES` | Lifetime of an email-verification link | No | `1440` |
| `DEBUG` | Enables `/docs` and `/redoc` | No | `False` |
| `SENTRY_DSN` | Sentry error tracking — disabled when empty | No | (empty) |
| `SENTRY_TRACES_SAMPLE_RATE` | Sentry performance tracing sample rate | No | `0.0` |
| `BEHIND_PROXY` | Trust `X-Forwarded-For` for rate limiting (set when behind nginx/Caddy) | No | `False` |
| `FORWARDED_ALLOW_IPS` | IPs/CIDRs uvicorn trusts proxy headers from (never `*`). Compose-only; passed to uvicorn, not read by `config.py` | No | `172.28.0.0/16` (prod compose) |
| `APP_DOMAIN` / `API_DOMAIN` | Public host names Caddy issues certificates for. Compose-only | Yes (prod) | — |
| `ACME_EMAIL` | Contact address for Let's Encrypt. Compose-only | Yes (prod) | — |
| `VITE_API_URL` | Backend URL for frontend | No | `http://localhost:8000` |
| `VITE_PRIVACY_EMAIL` | Contact published in the privacy policy and terms for access requests and complaints. Must be a mailbox that exists | No | `privacy@<served domain>` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | No | `http://localhost:5173,http://localhost:3000` |

## API Overview

| Group | Prefix | Key Endpoints |
|-------|--------|---------------|
| **Auth** | `/auth` | Register, login, refresh token, logout, forgot/reset password, verify email |
| **Users** | `/users` | Get/update profile, change password, **`GET /users/me/export`** — a JSON copy of everything stored about the account (PIPEDA Principle 9; `no-store` attachment, rate-limited 5/hour, credentials marked withheld), delete account |
| **Degree** | `/degree` | Course CRUD, requirement buckets, degree summary, document parsing |
| **Projects** | `/projects` | Project CRUD, milestone management |
| **Career** | `/career` | Career targets, timeline events, resume AI review |
| **Course Advisor** | `/course-advisor` | Course search, AI recommendations, semester plan generation + apply |
| **Conversations** | `/conversations` | Create/list conversations, send messages (triggers AI + tool execution) |
| **Dashboard** | `/dashboard` | AI weekly summary |
| **Suggestions** | `/suggestions` | List/accept/dismiss AI-generated suggestions |
| **Study** | `/study` | Study session logging and stats |
| **DSA** | `/dsa` | Practice-problem tracker, per-user stats and weekly goal |
| **Calendar** | `/calendar` | Token-authenticated `.ics` feed of courses and deadlines |

Full interactive docs at `http://localhost:8000/docs` when the backend is running.

## Project Structure

```
acadvo/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/versions/         # Database migrations
│   └── app/
│       ├── main.py               # FastAPI app, CORS, router mounts
│       ├── config.py             # Settings from environment
│       ├── database.py           # Async SQLAlchemy engine + sessions
│       ├── deps.py               # Auth dependency (JWT extraction)
│       ├── models/               # 12 ORM models (user, degree, project, career, etc.)
│       ├── schemas/              # Pydantic request/response schemas
│       ├── routers/              # 12 API routers, 85 endpoints
│       ├── services/             # Business logic (degree, career, auth, etc.)
│       └── ai/
│           ├── client.py         # Groq client configuration
│           ├── research_client.py # Fetches university pages; citations required
│           ├── context.py        # System prompt builder (full user context)
│           ├── tools.py          # 16 tool declarations for function calling
│           ├── tool_executor.py  # Tool dispatch + handlers (DB operations)
│           └── conversation.py   # Multi-turn conversation loop with tool execution
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── App.jsx               # Routing (18 routes, incl. /privacy and /terms)
        ├── api/                  # 13 API client modules (Axios)
        ├── context/              # Auth + Theme providers
        ├── hooks/                # useConversation (chat state management)
        ├── data/                 # Static data (universities, programs)
        ├── pages/                # 19 page components (incl. PrivacyPage, TermsPage)
        └── components/
            ├── layout/           # AppShell, Sidebar, Topbar, ProtectedRoute
            ├── chat/             # ChatWidget, MessageBubble, ChatInput, ToolCallResult
            ├── degree/           # CourseTable, SemesterPlanner, PrerequisiteFlow, FileUploadZone, etc.
            ├── career/           # CareerAIChat, ApplicationPipeline, ResumeReview, etc.
            ├── dashboard/        # 14 dashboard components
            ├── projects/         # ProjectCard, MilestoneList, MilestoneItem
            ├── tour/             # OnboardingTour
            └── ui/               # Button, Card, Input, Select, Modal, Badge, ProgressBar, ProgressRing, Spinner
```

## Production Deployment & Security

### Deploying

`docker-compose.prod.yml` brings up the whole stack behind Caddy, which obtains and renews Let's Encrypt certificates automatically. Nothing except the proxy publishes a host port — the API, the static frontend, Postgres and Redis are reachable only inside the compose network.

```bash
cp .env.example .env   # then fill in every value
docker compose -f docker-compose.prod.yml up -d --build
```

Set `APP_DOMAIN` and `API_DOMAIN` to two names under **one registrable domain** (e.g. `acadvo.app` and `api.acadvo.app`) and point both at the host before starting, or the ACME challenge fails. Same-registrable-domain matters for more than tidiness: it keeps app→API requests *same-site*, so the `SameSite=lax` auth cookies still work. Two unrelated domains would force `COOKIE_SAMESITE=none`, which the app refuses to start with.

### Enforced at startup

The backend refuses to boot when `DEBUG=False` and any of these is wrong:

- **`JWT_SECRET_KEY`** — a random 32+ char string (`openssl rand -hex 32`). Rotating it invalidates all existing sessions.
- **`JWT_ALGORITHM`** — must be HS256/384/512. An asymmetric or `none` value is rejected, closing the JWT algorithm-confusion hole.
- **`COOKIE_SECURE=True`** — auth cookies only over HTTPS.
- **`COOKIE_SAMESITE`** — `none` is refused outright, not merely warned about.
- **`CORS_ORIGINS`** — your real domain(s), never `localhost` or `*`.

### What protects what

| Control | Where | Against |
|---|---|---|
| httpOnly + `Secure` + `SameSite=lax` cookies; refresh cookie scoped to `/auth` | `services/auth.py` | Token theft via XSS; refresh token riding on every request |
| Required `X-Requested-With` header on all state-changing requests | `main.py` (`csrf_protection`) | CSRF, including the multipart form vector that CORS preflight does not cover |
| Refresh-token rotation **with reuse detection** — a replayed token revokes the whole family | `services/auth.py` | A stolen refresh token silently outliving detection |
| Per-account login backoff (escalating, capped) on top of the per-IP limit | `services/auth.py` | Distributed credential stuffing, which a per-IP limit does nothing against |
| 12-char minimum + breach-list blocklist + bcrypt 72-byte cap | `schemas/password.py` | Guessable passwords; silent bcrypt truncation |
| Magic-byte sniffing; declared Content-Type must match real bytes | `services/uploads.py` | Mislabelled files reaching PDF/spreadsheet parsers |
| Page/sheet/row/character caps on extraction | `services/uploads.py` | Decompression bombs — a 10 MB XLSX or PDF expanding to exhaust a worker |
| Every Groq call and every PDF/XLSX parse runs off the event loop | `ai/client.py` (`run_blocking`) | One user's chat or upload stalling the whole worker (trivially triggered DoS) |
| A course-code shortlist, not the whole catalog, is put in each prompt — ranked, budget-capped, and still validated against the full catalog afterwards | `services/eligibility.py` | A real catalog (1,195 courses ≈ 23k tokens) exceeding the per-request token limit, breaking every AI feature as coverage grows |
| Graduate-level courses filtered out of undergraduate advising | `services/eligibility.py` | An ingested catalog is the whole calendar; the planner scheduled an 800-level seminar into a first-year term |
| Graduate numbering is per-university, not a width heuristic | `data/program_config.py` | UofT and TMU number graduate courses with four digits and undergraduate ones with three — the inverse of York — so the general rule read every UofT graduate course as undergraduate |
| Credits per course derived from the student's own checklist, never assumed | `data/credit_models.py` | A Waterloo course is 0.5 units and a UofT one 0.5 credits; York's hardcoded 3.0/120 told a Waterloo student their 20-unit degree was 100 units short |
| Only the "Prerequisite:" clause of a course description is parsed | `ingest/york.py` | York names other courses in passing ("continues the theme introduced in EECS 1020"); parsing the whole description turns an aside into a hard prerequisite and blocks a student from a course they can take |
| Catalog lookups tolerate a missing faculty prefix | `services/catalog.py` | `HH/PSYC 1010` and `PSYC 1010` were two different courses: the student's own course counted twice, and recommendations dropped as "fabricated" |
| The catalog upsert is chunked | `ingest/store.py` | One INSERT per row-batch exceeds PostgreSQL's 32,767 bind parameters; a whole-university ingest crawled every page and then lost all of it on the write |
| York faculty prefixes applied only to York-shaped (four-digit) course numbers | `services/document_parser.py` | `get_catalog` normalises every row, so SFU's `MATH 100` was stored and shown to Simon Fraser students as York's `SC/MATH 100` |
| The elective tail of a shortlist is spread across subjects, not alphabetical | `services/eligibility.py` | A French major whose every elective was a biology course, because "B" sorts early and the list was truncated |
| ICS feed escapes carriage returns and folds lines to 75 octets | `services/calendar.py` | Calendar injection through a course name into an unauthenticated feed; over-long lines rejected by stricter clients |
| Reasoning effort pinned low on JSON-producing calls | `config.py`, `ai/client.py` | A reasoning model spending its entire completion budget thinking and returning zero characters — measured at 4,631 tokens of reasoning, no plan |
| Researched requirement rules must cite pages the model actually retrieved; forum/UGC citations dropped | `ai/research_client.py`, `research/schema.py` | A model answering from memory being stored, repeated to every future student, and surfacing as a wrong "this counts toward your degree" a year later |
| Requirement rules can classify courses but never write to the catalog | `research/program_rules.py` | A hallucinated course code inside a rule becoming a course the advisor recommends |
| Exclusion lists subtracted from option lists, and checked first | `research/schema.py`, `services/requirement_rules.py` | Recommending exactly the courses a requirement rules out — the two lists sit one sentence apart in real documents |
| Email verification required for every AI endpoint | `deps.py` (`require_verified_email`) | Throwaway addresses burning Groq budget; accounts on addresses the signer-up doesn't own |
| Feed token redacted from the request log **and** uvicorn's access log **and** Sentry | `observability.py` | Leaking a permanent bearer credential for a user's schedule into logs |
| CSP, HSTS, `frame-ancestors`, Permissions-Policy, COOP/CORP — repeated into every nginx `location` | `frontend/nginx.conf`, `security-headers.conf` | XSS impact, clickjacking. **`add_header` is not inherited into a `location` that sets its own — hence the `include`.** |
| HTML escaping in the PDF export; `javascript:`/`data:` URLs rejected in both the schema and the UI | `ExportPDF.jsx`, `utils/urls.js`, `schemas/weburl.py` | Stored XSS via AI-extracted course names and user-supplied links |
| Containers run non-root, read-only rootfs, `cap_drop: ALL`, `no-new-privileges`, digest-pinned images | Dockerfiles, `docker-compose.prod.yml` | Privilege escalation after a parser RCE; supply-chain drift |

### Operational requirements (not auto-enforced)

- **Proxy headers must be handled correctly or rate limiting is bypassable.** Run with `--no-proxy-headers` unless behind a reverse proxy you control. Behind one, use `--proxy-headers --forwarded-allow-ips=<proxy-ip-or-cidr>` (never `*`) and keep the app's own port off public interfaces. Note that with Caddy in a **container**, the trusted peer is its address on the compose network, *not* loopback — `docker-compose.prod.yml` defaults `FORWARDED_ALLOW_IPS` to the fixed `172.28.0.0/16` subnet it declares.
- **Rate limits are per-worker unless shared.** With `--workers N` an in-memory limit is effectively multiplied by N and resets on restart. The prod compose wires `RATE_LIMIT_STORAGE_URI` to Redis for you.
- **Set `SMTP_*`. This is now load-bearing, not optional.** The AI features require a verified email address, and verification links are delivered by email. With SMTP unconfigured those links are only written to the server log, so no real user can ever reach the advisor. The app warns about this at startup.
- **Rotate the pinned base-image digests deliberately.** Pinning stops silent drift but also stops silent patching; refresh them on a schedule.
- **Check the Groq model ids before you trust an AI failure.** Groq retires hosted models, and a retired id fails *every* AI call with a 404 — one dead config value reads as "the whole product is broken". The Llama models this app was built against are already gone. `curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"` lists what is actually servable; the defaults live in `backend/app/config.py`.
- **On Groq's free tier, set `GROQ_MAX_REQUEST_TOKENS` to 8000.** Groq's per-minute token limit is also a *per-request* limit: one call whose prompt plus `max_tokens` exceeds it is refused with a 413 every time, no matter how long you wait. The semester planner asks for an 8,192-token completion, so on the free tier it fails 100% of the time. With this set, the planner trims its completion budget to fit and produces a real plan; if a plan still runs long, the terms that completed are returned with a warning rather than discarded. A paid tier leaves this at 0.
- **Schedule `scripts/backup-db.sh` and copy the dumps off the host.** Nothing in the stack backs the database up on its own. See [Backups, restore, and rollback](#backups-restore-and-rollback).
- **Point an uptime monitor at `/health/ready`, not `/health`.** The two answer different questions and only one of them is useful to a monitor. `https://$API_DOMAIN/health` is *liveness* — it returns `{"status":"ok"}` as soon as uvicorn binds a socket, without touching the database, because restarting the API when Postgres blips would replace one broken dependency with two. `https://$API_DOMAIN/health/ready` is *readiness*: it runs a real query and returns **503** when the database is unreachable, so a container with bad credentials cannot report healthy while every request 500s. Both are unauthenticated and neither leaks connection details. The container `HEALTHCHECK` and Caddy's startup gate use the readiness endpoint. Also watch `https://$APP_DOMAIN/` for the app shell — container health tells you nothing when the whole host is gone.
- **Watch for `groq quota low` in the logs.** Every AI response carries the account's remaining allowance, and the app records it (`app/ai/client.record_quota`). When the request budget drops below 10% it logs a warning, and any provider error logs the last known quota beside it. This is the difference between an outage investigation and reading a clock: on a free tier the daily allowance runs out mid-afternoon, *every* AI feature starts failing at once, and nothing else in the system says why.
- **Run `scripts/loadtest.py` before a launch and after any query change.** Everything else in this repo tests one request at a time; an N+1 is invisible until the tenth concurrent user and obvious at the hundredth. It logs in once (so it measures the read paths rather than bcrypt and the login rate limiter), warms the pool, then fans out. Non-zero exit on any failure or p95 breach, so it can gate a release:

  ```bash
  python scripts/loadtest.py --url https://$API_DOMAIN \
      --email you@example.com --password '...' --users 100 --requests 3
  ```
- **Set `SENTRY_DSN`.** Without it a 500 in production exists only in `docker compose logs`, which nobody is reading at the moment it happens. Sentry runs with `send_default_pii=False` and the feed token scrubbed.

- **Create the privacy mailbox before the first real user.** `/privacy` and `/terms` name `VITE_PRIVACY_EMAIL` (defaulting to `privacy@<your domain>`) as the contact for access requests, corrections, and complaints. PIPEDA's openness principle requires that contact to be reachable — a policy pointing at a mailbox that bounces is worse than no policy, because it is a published commitment nobody can act on.

### Privacy and the legal pages

The app holds student transcripts, grades, and advisor conversations — personal
information under PIPEDA, which brings three obligations the code has to satisfy,
not just the policy text:

| Obligation | Where it lives | What would break it |
|---|---|---|
| **Openness** (Principle 8) — publish what is collected, why, who else sees it | `frontend/src/pages/PrivacyPage.jsx`, linked from the landing footer, the registration form, and Settings | Changing what is collected without changing the page. Every claim on it — "uploads are never stored", "no analytics", "Groq does not train on it" — was checked against the code and is only true while that stays true |
| **Individual access** (Principle 9) — give the person a copy on request | `GET /users/me/export`, Settings → *Download my data* | A new user-owned table that the export misses. `tests/test_data_export.py` derives the expected tables from the foreign keys, so a new one joins the export or fails the suite |
| **Consent** (Principle 3) — meaningful, informed, age-appropriate | The tick box on `RegisterPage.jsx`, which states the age minimum and the US transfer | Turning it into a passive "by continuing you agree" line, which is not consent the OPC recognises |

The operator identity, governing province, minimum age, and hosting region are
facts asserted on both pages and are set in one place —
`frontend/src/legal/config.js`. **If the hosting region changes, that file is
wrong and the privacy policy is making a false statement about where data lives.**

Deliberately absent: a cookie banner (the only cookies are the two session
cookies, which are strictly necessary), an arbitration clause, and a
class-action waiver.

### Security policy and incident response

Who owns security, how to report a vulnerability, what to revoke first when
something leaks, and the PIPEDA notification duty: **[SECURITY.md](SECURITY.md)**.
It ships with the owner deliberately unassigned — fill that in before launch, or
the plan is one nobody executes.

### Backups, restore, and rollback

Every user's academic record lives in one Postgres volume, and that volume is on the same host as the app. Nothing above protects it from a bad migration, a `docker compose down -v`, or a dead disk.

```bash
./scripts/backup-db.sh                    # -> ./backups/acadvo-<utc-stamp>.sql.gz
RETENTION_DAYS=30 ./scripts/backup-db.sh  # keep a month instead of a fortnight
```

`pg_dump` runs *inside* the db container (nothing publishes a Postgres port), the stream is gzipped on the host, and the result is verified — `gzip -t` plus a check for the dump's terminator line — before it is promoted from `.partial` to its final name. A truncated backup that looks fine is worse than no backup, and both of its failure modes are silent.

Run it from cron on the deployment host:

```bash
15 3 * * * cd /srv/acadvo && ./scripts/backup-db.sh >> /var/log/acadvo-backup.log 2>&1
```

Two things the script cannot do for you: **copy the dumps off the host** (a disk failure takes the app and its backups together — push them to object storage, encrypted), and **prove they restore**. Practise that on a scratch host:

```bash
./scripts/restore-db.sh backups/acadvo-20260819T031500Z.sql.gz
```

It stops the backend first so nothing writes into a half-restored schema, replays the dump with `ON_ERROR_STOP=1`, and starts the backend again (which runs `alembic upgrade head` on boot). It asks you to type the database name, because it overwrites everything.

**Rolling back a release** is a rebuild at the previous commit — images are built from this repo, not pulled from a registry:

```bash
git checkout <previous-good-sha>
docker compose -f docker-compose.prod.yml up -d --build
```

That reverts application code only. A release containing an Alembic migration is *not* fully reversible this way: the old code will run against the new schema. Check `backend/alembic/versions/` before rolling back across a migration, and use the pre-deploy backup if the schema has to go back too — which is the reason to take one immediately before every deploy, not only nightly.

### Email verification

AI endpoints (`/conversations`, `/course-advisor/*`, `/suggestions`, degree document/syllabus parsing, resume review) return **403** until the account's address is confirmed. Everything else — reads, ordinary CRUD, onboarding, password change, account deletion — stays open, because gating those would leave new users unable to finish signup without buying any real protection: that data is per-account, isolated and rate-limited.

The line is drawn at cost. Each model call spends money, and a per-IP rate limit does nothing against someone cycling throwaway addresses.

Migration `015` marks all pre-existing accounts verified. Those rows predate any enforcement, so leaving them alone would lock out every current user — including anyone who *did* verify while the flag was decorative. Drop that migration before deploying if you would rather force everyone through verification.

### Security in CI

`.github/workflows/ci.yml` runs, with `permissions: contents: read` and every action pinned to a commit SHA (not a mutable tag):

- `pip-audit` against the pinned `requirements.txt`
- `npm run audit` — a gate script that fails on any high/critical advisory not carrying a written, **expiring** justification in `frontend/audit-allowlist.json` (that allowlist is currently empty — everything known is actually fixed)
- Bandit and CodeQL (`security-extended`) for Python and JS
- gitleaks over full history
- a build of both **production images**, a smoke test that the frontend container serves the app with its CSP placeholder actually substituted, and an interpolation check of `docker-compose.prod.yml`. The other jobs run pytest and `npm run build` on the runner, so nothing there ever exercises the Dockerfiles — image-only breakage used to surface on the deployment host

Run them locally the same way:

```bash
cd backend && pip-audit --requirement requirements.txt --strict && bandit -r app -ll
```

```bash
cd frontend && npm run audit
```

## Technical Decisions

- **Async SQLAlchemy** — Every database call is non-blocking. AI tool execution can involve 5-10 DB operations per message; async prevents the server from stalling while the model thinks and tools execute sequentially.

- **LLM function calling over simple chat** — The AI doesn't just suggest actions, it takes them. When a student says "plan my next semester," the AI calls `generate_semester_plan`, reviews the result, and can follow up with `add_course` calls. This is only possible with structured tool use, not free-text chat.

- **University-scoped course prompts** — Plan and recommendation prompts embed the student's university and its web domain so the model uses that school's real course-code conventions. Generated plans are sanitized server-side (past semesters stripped, workload capped) before anything is saved.

- **JSONB for tool_calls** — Each AI message can trigger multiple tool calls with nested inputs and results. Storing this as JSONB in PostgreSQL keeps the schema simple (one `messages` table) while preserving the full tool execution trace for the frontend to render inline.

- **Client-side smart alerts** — Dashboard alerts (at-risk buckets, overdue milestones, missing career targets) are computed from data already fetched for the page. No extra API call, no AI cost, instant feedback.

## What I Would Build Next

- **Streaming chat responses** — The advisor chat waits for the full tool-execution loop before responding; streaming tokens (like the semester planner's SSE endpoint already does) would improve perceived latency.

- **2FA** — Every AI endpoint already requires a verified address (`require_verified_email`, see [Email verification](#email-verification)); login itself is deliberately not blocked. Optional TOTP 2FA is the remaining account-security step.

- **Background email delivery** — Emails send inline (in a worker thread). A queue (e.g. Celery/RQ) would decouple delivery from the request and add retries.
