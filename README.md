# Acadvo

**AI-powered academic and career advisor for Canadian university students.**

Acadvo helps students plan their degrees strategically, track career targets, build portfolios, and prepare for internships — with an AI advisor that doesn't just chat, but takes real actions. It knows your courses, grades, degree requirements, projects, and career goals, and uses that full picture to add courses to your plan, flag risks, build timelines, and generate semester-by-semester schedules aligned with your university's course catalog. Built specifically for the Canadian university system, with support for 25+ institutions.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Alembic |
| **Frontend** | React 18, Vite, Tailwind CSS, React Router v6, Axios |
| **AI** | Groq — Llama 3.3 70B function calling (15 tools), Llama 3.2 11B Vision for image input, PDF/spreadsheet text extraction |
| **Auth** | JWT (HS256) with refresh token rotation, bcrypt password hashing |
| **Infrastructure** | Docker Compose (PostgreSQL + backend + frontend) |

## Features

### Degree Planning
- Full CRUD for courses with inline editing (grades, semester, status, requirement bucket)
- Requirement buckets with credit progress tracking and at-risk detection
- AI semester-by-semester course plan — targets your university's catalog (course-code conventions per school), respects prerequisites, balances workload (max 5/semester), aligns with career goals
- Document import — upload a degree checklist (PDF, image, Excel, CSV) and the AI extracts requirements + courses automatically
- Prerequisite flow visualization and PDF export

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

Before exposing this app publicly, the backend enforces a few settings at startup (it refuses to boot otherwise when `DEBUG=False`):

- **`JWT_SECRET_KEY`** — must be a random 32+ char string (`openssl rand -hex 32`). Rotating it invalidates all existing sessions.
- **`COOKIE_SECURE=True`** — required in production so auth cookies are only sent over HTTPS. Deploy behind TLS.
- **`CORS_ORIGINS`** — must be your real domain(s), not `localhost` or `*`.

Additional operational requirements (not auto-enforced):

- **Rate limiting depends on the client IP, so proxy headers must be handled correctly.** Run the app with `--no-proxy-headers` unless it sits behind a reverse proxy you control. When you do use a proxy, run uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy-ip>` (never `*`) and keep the app's own port bound to loopback (`127.0.0.1:8000`) so clients can't reach uvicorn directly and spoof `X-Forwarded-For` to bypass rate limits. The provided `docker-compose.prod.yml` is configured this way.
- **Rate limits are per-worker and in-memory.** With `--workers N` the effective limit is multiplied by N and resets on restart; use a single worker or move to a shared (Redis) store for exact global limits.
- **Do not publish the database or backend port to a public interface.** The dev compose binds Postgres to `127.0.0.1` only; the prod compose keeps the DB internal to the Docker network.

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
