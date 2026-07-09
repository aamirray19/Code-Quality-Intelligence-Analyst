# Clean State Checklist

Run through this before ending any session on this repo.

## Process hygiene
- [ ] No stray dev servers still listening: check ports 8000 (backend), 8080/8081 (frontend). `Get-NetTCPConnection -LocalPort 8000,8080,8081 -ErrorAction SilentlyContinue`
- [ ] No orphaned worker processes left running against a real Redis queue.
- [ ] Any `mode: async`/`detach: true` background processes started this session have been stopped or are intentionally left running (and the user was told so).

## Backend
- [ ] `task backend:test` (pytest) passes.
- [ ] No leftover debug prints, `breakpoint()`, or commented-out code in `backend/app/`.
- [ ] `backend/.env` / `backend/.env.example` are in sync if new env vars were added (`app/core/config.py` matches both).
- [ ] `backend/db/migrations/0001_init.sql` reflects the current schema if any tables/columns changed.
- [ ] No new dependency added to `backend/pyproject.toml` without also running `uv sync` and confirming `uv.lock` is updated.

## Frontend
- [ ] `task frontend:build` succeeds.
- [ ] `task frontend:lint` shows no new errors/warnings beyond the pre-existing baseline (see `handoff.md` for what's pre-existing).
- [ ] No dead imports/components left behind after any deletion (`grep` for the removed symbol names across `frontend/src`).
- [ ] `frontend/.env` has no stray/unused variables.
- [ ] `frontend/package.json` and `frontend/package-lock.json` are consistent (`npm install --legacy-peer-deps` run after any manual edit).

## Documentation & session records
- [ ] `handoff.md` has a new dated entry: currently verified, changes this session, verification run, still broken/unverified, next section, files changed.
- [ ] `decisions.md` updated if any new or revisited design decision was made this session (using the template).
- [ ] `docs/phase{1,2,3,4}.md` updated if a documented design/contract changed.
- [ ] `AGENTS.md` still accurately reflects available commands/docs if the Taskfile or repo structure changed.

## Repo/version control
- [ ] Temporary/scratch files created during the session (scripts, test fixtures, logs) are cleaned up or intentionally kept.

## Verification evidence
- [ ] Every claim of "passing"/"working" in this session's summary is backed by an actual command run and its output, not assumption.