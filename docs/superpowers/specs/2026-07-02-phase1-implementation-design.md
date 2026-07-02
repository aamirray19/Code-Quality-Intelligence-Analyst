# Phase 1 Implementation Design — GitHub Repo Ingestion & Scan Queueing

Status: Approved
Source spec: `phase1.md` (repo root)

## 1. Scope

Implement Phase 1 end-to-end:
- A new FastAPI backend (`backend/`) that validates a GitHub repo URL, creates a scan
  record in Supabase, and enqueues a job to Redis (via RQ).
- Frontend wiring in the existing Vite/React app (`frontend/`) so the GitHub URL input
  calls the real backend and shows live scan status inline, without navigating to a new route.

Out of scope (per phase1.md): cloning, parsing, Qdrant/Neo4j storage, LangGraph agents,
report generation, RAG chatbot, and any actual job processing by a worker (Phase 2+).

## 2. Backend

### 2.1 Tooling
- Python, managed with **uv** (`pyproject.toml`, `uv.lock`).
- Web framework: FastAPI + Uvicorn.
- HTTP client for GitHub API: `httpx`.
- Supabase access: `supabase-py`.
- Queue: `rq` + `redis` client.
- Config: `pydantic-settings`.
- Tests: `pytest`, `pytest-mock`, `respx` (mock httpx calls to GitHub).

### 2.2 Directory layout
```
backend/
  pyproject.toml
  .env.example
  app/
    main.py
    api/
      routes/
        scans.py
        health.py
    core/
      config.py
      errors.py
      logging.py
    schemas/
      scans.py
      repos.py
      errors.py
    services/
      github_url_parser.py
      github_metadata_service.py
      repo_validation_service.py
      scan_service.py
      queue_service.py
    db/
      supabase_client.py
    workers/
      redis_connection.py
  tests/
    test_github_url_parser.py
    test_repo_validation_service.py
```

### 2.3 Behavior
Implements exactly the flow, validation rules, API contracts, error codes, and data
models described in `phase1.md` sections 5–9:
- `github_url_parser.py`: parses owner/repo/branch from supported URL formats
  (plain, trailing slash, `.git` suffix, `/tree/branch`); rejects unsupported paths
  (`/pull`, `/issues`, `/blob`) and non-GitHub hosts.
- `github_metadata_service.py`: calls GitHub REST API for repo metadata and branch
  existence, using `GITHUB_TOKEN` if set.
- `repo_validation_service.py`: applies validation rules 1–7 from §7.3, raising
  structured `AppError`s (mapped to the error codes in §9) on failure.
- `scan_service.py`: creates/reads/updates scan rows in Supabase `scans` table.
- `queue_service.py`: pushes the job payload (§8.4) onto `repo_scan_queue` via RQ.
- `workers/redis_connection.py`: shared Redis connection used by `queue_service`
  and available for a future Phase 2 worker. No job consumer is implemented in
  Phase 1.
- Routes: `POST /scans`, `GET /scans/{scan_id}`, `GET /health` matching the exact
  request/response bodies and status codes in phase1.md §6.
- Error handling: a global FastAPI exception handler converts `AppError` (carrying
  `error_code`, `message`, `http_status`) into the `ErrorResponse` schema.
- CORS: allow origin `http://localhost:8080` (frontend dev server) via `FRONTEND_URL` env var.

### 2.4 Data
- Supabase tables `scans` and `scan_events` created via a SQL migration file
  (`backend/db/migrations/0001_init.sql`) containing the exact DDL from phase1.md §8.3.
  The user will run this against their own Supabase project — this repo does not
  have DB credentials to run it automatically.
- `scan_events` rows `scan_created` and `job_queued` are inserted by `scan_service`/
  `queue_service` respectively (best-effort, non-blocking to the main flow).

### 2.5 Environment variables
Matches phase1.md §10 exactly:
```
APP_ENV, API_BASE_URL
GITHUB_TOKEN, MAX_REPO_SIZE_KB=51200
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
REDIS_URL, REDIS_QUEUE_NAME=repo_scan_queue
FRONTEND_URL=http://localhost:8080
```
An `.env.example` is committed; the real `.env` is not (gitignored), and the user
supplies real Supabase/Redis/GitHub credentials themselves.

### 2.6 Testing
- Unit tests for `github_url_parser` (pure function, table-driven cases covering all
  supported/unsupported formats from §6.1).
- Unit tests for `repo_validation_service` with GitHub API mocked via `respx`,
  covering: not found, private, archived, too large, branch not found, and success.
- No live network/Supabase/Redis calls in automated tests.

## 3. Frontend

### 3.1 Changes to `RepoAnalyzer.tsx`
- Remove ZIP upload mode entirely: `Mode` type, `ModeToggle`, dropzone UI, `zipSchema`,
  `formatBytes`, and related state/handlers. Component becomes GitHub-URL-only.
- Add `VITE_API_BASE_URL` to `frontend/.env` (default `http://localhost:8000`).
- Replace the mock `analyze()` call with a real `fetch("${API_BASE_URL}/scans", {method: "POST", body: {github_url}})`.
- Client-side Zod schema updated to accept the supported URL formats (trailing slash,
  `.git` suffix, `/tree/branch`) and reject unsupported paths, mirroring backend rules
  for immediate feedback before the network round trip; backend remains source of truth.
- On success: show "Repository is valid. Scan started." then begin polling
  `GET /scans/{scan_id}` every 2s (via `setInterval`, cleaned up on unmount/completion)
  and render the current `status` value (queued → cloning → ... → completed/failed)
  inline in the same component — no route/page change.
- On failure: show the `message` from the backend's `ErrorResponse` (e.g.
  "Repository is invalid. Please enter a valid public GitHub repository URL.").
- On terminal status (`completed` or `failed`), stop polling and show a final message
  (Phase 1 has no report to link to yet, so `completed` just shows a "queued/processing
  handed off" style message — actual report display is a later phase).

### 3.2 No route changes
`AnimatedRoutes.tsx` and `pages/Index.tsx` are untouched. Everything happens within
`RepoAnalyzer.tsx`'s own state.

## 4. Error handling summary (frontend + backend)
All error codes from phase1.md §9 are surfaced verbatim as backend `error_code` +
`message`; the frontend displays `message` directly under the input, matching the
existing `error` UI pattern already in `RepoAnalyzer.tsx`.

## 5. Out of scope / explicitly deferred
- Actual worker process consuming `repo_scan_queue` (Phase 2).
- Any UI for scan report contents.
- Automated running of the Supabase SQL migration (user runs it manually).
