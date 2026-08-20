# Acadvo

**AI-powered academic and career advisor for Canadian university students.**

Acadvo helps students plan their degrees strategically, track career targets, build portfolios, and prepare for internships — with an AI advisor that doesn't just chat, but takes real actions. It knows your courses, grades, degree requirements, projects, and career goals, and uses that full picture to add courses to your plan, flag risks, build timelines, and generate semester-by-semester schedules aligned with your university's course catalog. Built specifically for the Canadian university system, with GPA and grading-scale support for 16 Canadian universities. Verified course catalogs (with prerequisites and enrolment gates) currently ship for Simon Fraser University — 1,195 courses across 26 subjects, ingested from SFU's official course-outlines API — and York (Computer Science, hand-authored), with more schools expandable through the same pipeline.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Alembic |
| **Frontend** | React 19, Vite, Tailwind CSS, React Router v8, Axios |
| **AI** | Groq — `openai/gpt-oss-120b` function calling (15 tools), `qwen/qwen3.6-27b` for image input, PDF/spreadsheet text extraction. Gemini (optional) — Google Search grounding, used only to research a program's requirement rules from the university's own public pages |
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
- 15 function-calling tools: add courses, create projects, flag risks, generate timelines, update profiles, search course catalogs, build semester plans, add degree requirements
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
- 10 widgets: GPA tracker, credit progress, deadline countdown, portfolio score, smart alerts, weekly AI check-in, current courses, active milestones, upcoming deadlines, AI suggestions
- Smart alerts analyze your data client-side: at-risk requirement buckets, overdue milestones, missing career targets
- AI-generated weekly progress summary

### Platform
- **Installable PWA** — web app manifest, offline app-shell caching via service worker (Workbox), iOS home-screen support; API routes are explicitly excluded from caching so authenticated data is never served stale
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
   - `GEMINI_API_KEY` — optional; enables requirement-rule research ([get one here](https://aistudio.google.com/apikey)). Leave it empty and the app simply will not say which degree requirement a course satisfies, which is the honest answer when it has not read your university's rules.
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
| `GEMINI_API_KEY` | Gemini key — requirement-rule research only; empty disables that path | No | (empty) |
| `GEMINI_MODEL` | Model used for research | No | `gemini-flash-latest` |
| `RESEARCH_USE_SEARCH_GROUNDING` | Let the model find requirement pages itself. **Billed** — 429s on the free tier | No | `False` |
| `REQUIREMENT_RULE_TTL_DAYS` | Days before a researched rule is re-checked in the background | No | `180` |
| `PROGRAM_RESEARCH_ENABLED` | Master switch for the background research worker | No | `True` |
| `COOKIE_SECURE` | Send auth cookies only over HTTPS — set `True` in production | No | `False` |
| `DEBUG` | Enables `/docs` and `/redoc` | No | `False` |
| `SENTRY_DSN` | Sentry error tracking — disabled when empty | No | (empty) |
| `SENTRY_TRACES_SAMPLE_RATE` | Sentry performance tracing sample rate | No | `0.0` |
| `BEHIND_PROXY` | Trust `X-Forwarded-For` for rate limiting (set when behind nginx/Caddy) | No | `False` |
| `VITE_API_URL` | Backend URL for frontend | No | `http://localhost:8000` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | No | `http://localhost:5173,http://localhost:3000` |

## API Overview

| Group | Prefix | Key Endpoints |
|-------|--------|---------------|
| **Auth** | `/auth` | Register, login, refresh token, logout, forgot/reset password, verify email |
| **Users** | `/users` | Get/update profile, delete account |
| **Degree** | `/degree` | Course CRUD, requirement buckets, degree summary, document parsing |
| **Projects** | `/projects` | Project CRUD, milestone management |
| **Career** | `/career` | Career targets, timeline events, resume AI review |
| **Course Advisor** | `/course-advisor` | Course search, AI recommendations, semester plan generation + apply |
| **Conversations** | `/conversations` | Create/list conversations, send messages (triggers AI + tool execution) |
| **Dashboard** | `/dashboard` | AI weekly summary |
| **Suggestions** | `/suggestions` | List/accept/dismiss AI-generated suggestions |

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
│       ├── models/               # 8 ORM models (user, degree, project, career, etc.)
│       ├── schemas/              # Pydantic request/response schemas
│       ├── routers/              # 9 API routers, 40+ endpoints
│       ├── services/             # Business logic (degree, career, auth, etc.)
│       └── ai/
│           ├── client.py         # Groq client configuration
│           ├── research_client.py # Gemini + Google Search grounding (citations required)
│           ├── context.py        # System prompt builder (full user context)
│           ├── tools.py          # 15 tool declarations for function calling
│           ├── tool_executor.py  # Tool dispatch + handlers (DB operations)
│           └── conversation.py   # Multi-turn conversation loop with tool execution
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── App.jsx               # Routing (10 routes)
        ├── api/                  # 10 API client modules (Axios)
        ├── context/              # Auth + Theme providers
        ├── hooks/                # useConversation (chat state management)
        ├── data/                 # Static data (universities, programs)
        ├── pages/                # 10 page components
        └── components/
            ├── layout/           # AppShell, Sidebar, Topbar, ProtectedRoute
            ├── chat/             # ChatWidget, MessageBubble, ChatInput, ToolCallResult
            ├── degree/           # CourseTable, SemesterPlanner, PrerequisiteFlow, FileUploadZone, etc.
            ├── career/           # CareerAIChat, ApplicationPipeline, ResumeReview, etc.
            ├── dashboard/        # 10 dashboard widgets
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
- **Point an uptime monitor at both hostnames.** `https://$API_DOMAIN/health` returns `{"status":"ok"}` without touching the database or requiring auth; `https://$APP_DOMAIN/` serves the app shell. Container-level `HEALTHCHECK`s restart a wedged service but tell you nothing when the whole host is gone.
- **Set `SENTRY_DSN`.** Without it a 500 in production exists only in `docker compose logs`, which nobody is reading at the moment it happens. Sentry runs with `send_default_pii=False` and the feed token scrubbed.

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

- **Hard email-gating & 2FA** — Email verification exists but is soft (login isn't blocked on unverified accounts). Gating sensitive actions on verification, plus optional TOTP 2FA, would harden account security further.

- **Background email delivery** — Emails send inline (in a worker thread). A queue (e.g. Celery/RQ) would decouple delivery from the request and add retries.
