# AGENTS.md

## Project overview

Code Quality Intelligence Analyst — point it at a public GitHub repository and it produces a deep code-quality report (bugs, security, performance, complexity, duplication, reliability) plus a RAG chatbot for the scanned repo.

Stack:

- **Backend** (`backend/`): Python 3.11, FastAPI, managed with `uv`. Background jobs run via RQ on Redis Cloud, driven by `backend/run_worker.py`.
- **Storage**: Supabase (Postgres) for permanent scan/file/symbol/chunk/finding metadata, Qdrant Cloud for chunk/report embeddings, Neo4j Aura for the code graph.
- **Frontend** (`frontend/`): React + TypeScript + Vite, Tailwind/shadcn UI.
- **Task runner**: [Task](https://taskfile.dev) (`Taskfile.yml` at repo root) orchestrates both subprojects.

Pipeline phases (see `docs/phase{1,2,3,4}.md`):

1. Phase 1 — accept a GitHub URL, validate it, create a scan, queue a Redis job.
2. Phase 2 — worker clones the repo, discovers files, parses with Tree-sitter, chunks, embeds, and indexes into Qdrant/Neo4j.
3. Phase 3 — LangGraph supervisor-worker workflow runs Security/Performance/Complexity/Duplication/Reliability agents and stores ranked findings.
4. Phase 4 — generates the final report and serves a RAG chatbot over the scanned repo.

## Required startup

1. Read `handoff.md` (session handoff log — what the previous session did, what's still broken/unverified, and what's next).
2. Read the relevant phase doc(s) under `docs/` (`phase1.md`, `phase2.md`, `phase3.md`, `phase4.md`) for the phase you're working on.
3. Read `decisions.md` for any recorded design decisions before introducing new ones.
4. Run `task install` to install backend (`uv sync`) and frontend (`npm install --legacy-peer-deps`) dependencies.
5. Do not write feature code until you understand what's currently passing (`task backend:test`) and what's still unverified per `handoff.md`.

## Commands

All commands are defined in the root `Taskfile.yml`. Run `task --list-all` to see the full list.

- Install/setup: `task install` (or `task backend:install` / `task frontend:install` individually)
- Backend dev server: `task backend:dev` (FastAPI on `http://localhost:8000`)
- Worker: `task worker:dev` (RQ worker consuming `repo_scan_queue`; requires a reachable `REDIS_URL`)
- Frontend dev server: `task frontend:dev` (Vite on `http://localhost:8080`)
- Run everything at once: `task dev` (backend + worker + frontend concurrently)
- Backend tests: `task backend:test` (pytest)
- Frontend build: `task frontend:build`
- Lint: `task lint` (or `task frontend:lint`)
- Full test suite: `task test`

## Hard constraints

- Work on one feature/phase at a time.
- Do not mark a feature passing unless its verification command (`task backend:test`, `task frontend:build`/`lint`, or a manual smoke test) actually passes.
- Do not skip tests because the change "looks simple."
- Do not refactor unrelated code while implementing a feature.
- Record evidence of verification in `handoff.md` (this repo does not use `feature_list.json`/`progress.md`; `handoff.md` is the equivalent evidence/session log).
- Record any new or revisited design decisions in `decisions.md`.

## Definition of done

Done means:

1. Relevant backend unit tests pass (`task backend:test`).
2. Frontend builds and lints cleanly (`task frontend:build`, `task frontend:lint`) with no new errors/warnings beyond pre-existing ones.
3. A manual end-to-end or smoke check passes when user-facing or worker behavior changed (e.g. `task dev` plus a real scan through `POST /scans`, or targeted `curl`/pytest coverage of the changed path).
4. Evidence (commands run and their results) is recorded.
5. `handoff.md` is updated with a new dated session entry (currently verified, changes this session, verification run, still broken/unverified, next section, files changed).

## Topic docs

- Phase 1 (repo ingestion & scan queueing): `docs/phase1.md`
- Phase 2 (cloning, parsing, chunking, indexing): `docs/phase2.md`
- Phase 3 (LangGraph analysis workflow): `docs/phase3.md`
- Phase 4 (report generation & RAG chatbot): `docs/phase4.md`
- Decision log: `decisions.md`
- Session handoff log: `handoff.md`