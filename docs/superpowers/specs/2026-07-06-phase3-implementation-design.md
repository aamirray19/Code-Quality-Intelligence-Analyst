# Phase 3 Implementation Design — LangGraph Analysis Workflow

Status: Approved
Source spec: `docs/phase3.md` (repo root)
Related decisions: `decisions.md` (all 2026-07-06 entries)

## 1. Scope

Implement Phase 3 end-to-end: a LangGraph supervisor-worker analysis workflow that runs
after Phase 2 marks a scan `parsed`, produces ranked/deduplicated findings, and marks the
scan `analyzed`.

Included:
- Same-worker trigger (Option A): `repo_scan_worker.py` invokes the analysis graph directly
  after Phase 2 completes, no separate `analysis_queue`.
- LangGraph `AnalysisState` graph: context loading, readiness validation, hybrid-planning
  supervisor, 5 concurrent specialist agents, normalize/dedupe/rank/persist/mark-analyzed.
- Supabase tables: `analysis_tasks`, `agent_runs`, `findings`.
- OpenRouter-backed LLM client (DeepSeek v3, pinned slug), one dedicated API key per agent
  + supervisor, async HTTP calls for concurrency.
- Supabase/Qdrant/Neo4j tool wrappers reused from Phase 2, scoped by `scan_id`.

Out of scope (per `phase3.md` and 2026-07-06 decisions):
- Final report generation and RAG chatbot (Phase 4).
- A separate `analysis_queue` / dedicated analysis worker (deferred; documented as a future
  option in `decisions.md`).
- Re-analysis / re-run of an already-`analyzed` scan (silently skipped, not implemented as a
  feature).
- Live LLM/Qdrant/Neo4j/Redis credential testing — built and tested against mocks/fakes only,
  consistent with how Phase 2 was verified before real credentials existed.
- Deterministic complexity metrics requiring re-parsing (`branch_count`, `nesting_depth`,
  `parameter_count`, `loop_count`) — Complexity Agent uses LLM + existing Phase 2 metadata only.

## 2. Architecture

```
repo_scan_worker.py (existing, Phase 2)
        ↓ (status = parsed)
asyncio.run(run_analysis(scan_id))
        ↓
LangGraph AnalysisState graph (async)
  load_scan_context → validate_analysis_ready
        ↓ ready                  ↓ not ready
  build_analysis_plan        fail_analysis → END
        ↓ (Send-based fan-out, concurrent asyncio)
  security_agent | performance_agent | complexity_agent | duplication_agent | reliability_agent
        ↓ (all converge, operator.add on raw_findings)
  normalize_findings → deduplicate_findings → rank_findings → persist_findings
        ↓
  mark_scan_analyzed → END
```

- Every agent node and the supervisor node is `async def`, using `httpx.AsyncClient` to call
  OpenRouter (`deepseek/deepseek-chat-v3-0324`), each with its own dedicated API key. This
  gives true concurrency for the 5 agent LLM calls (the dominant latency).
- Existing Phase 2 tool clients (Supabase `create_client`, Qdrant client, Neo4j driver — all
  synchronous, verified against `backend/app/db/supabase_client.py` and
  `embedding_service.py`) are reused as-is. Every blocking call made from inside an async node
  is wrapped in `asyncio.to_thread(...)` so the event loop isn't blocked while other agents'
  LLM calls are in flight.
- `repo_scan_worker.py` (a plain sync function driven by RQ's `SimpleWorker`) bridges into the
  async graph via `asyncio.run(run_analysis(scan_id))` immediately after it marks
  `status = parsed`, matching the Option A same-worker decision.
- If `run_analysis` is invoked for a scan whose status is already `analyzed`, it logs a
  `duplicate_job_skipped`-style scan event and returns early (mirrors Phase 2's existing
  skip-if-already-parsed behavior) — no `SCAN_ALREADY_ANALYZED` error is raised in this path.

## 3. Supabase Data Model

Three new tables, added as a new migration file `backend/db/migrations/0002_phase3.sql`
(Phase 2 was merged directly into `0001_init.sql` per an explicit one-off instruction from
that session; Phase 3 uses a new numbered migration as the default convention going forward).

### 3.1 `analysis_tasks`

Same as `phase3.md` §16.1, **without** an extra `task_id` text column (2026-07-06 decision:
UUID `id` only). The in-memory `AnalysisTask` TypedDict's `task_id` field is populated from
this UUID once the row is created — no separate human-readable identifier is persisted.

```sql
create table analysis_tasks (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references scans(id) on delete cascade,

  agent_name text not null,
  objective text not null,
  priority integer not null default 1,

  target_file_ids jsonb not null default '[]',
  target_chunk_ids jsonb not null default '[]',
  target_symbol_ids jsonb not null default '[]',

  status text not null default 'pending',
  error_message text,

  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz
);
```

### 3.2 `agent_runs`

Exactly per `phase3.md` §16.2 (tracks each agent/supervisor LLM execution, including token
usage and status).

### 3.3 `findings`

Exactly per `phase3.md` §16.3, including the `findings(scan_id, fingerprint)` unique index and
the `severity in ('extreme','high','medium','low')` check constraint. `file_id`/`symbol_id`
are nullable and populated by `normalize_findings` (see §6.6) when resolution succeeds; they
remain `null` if a finding's `file_path`/`symbol_name` can't be matched to a known row (this is
not a hard failure — the finding is still persisted with `file_path`/`symbol_name` as the
human-readable reference).

### 3.4 `scan_events`

Reuse the existing Phase 1 table. New event types used by Phase 3 (per `phase3.md` §16.4):
`analysis_started`, `analysis_context_loaded`, `analysis_plan_created`, `agent_started`,
`agent_completed`, `agent_failed`, `findings_normalized`, `findings_deduplicated`,
`findings_ranked`, `findings_stored`, `analysis_completed`, `analysis_failed`,
`duplicate_job_skipped` (reused from Phase 2's convention for the already-analyzed skip case).

### 3.5 Scan statuses

Minimum v1 set per `phase3.md` §17: `parsed` (start) → `analyzing` → `analyzed` |
`analysis_failed`. The more granular intermediate statuses
(`planning_analysis`/`running_agents`/`normalizing_findings`/`storing_findings`) are not
required for v1; scan_events provide the granular timeline instead.

## 4. LangGraph State & Schemas

`backend/app/workflows/analysis/state.py` defines `AnalysisState`, `RepoContext`,
`AnalysisTask`, `RawFinding`, `NormalizedFinding` exactly per `phase3.md` §13, with
`raw_findings: Annotated[list[RawFinding], operator.add]` so parallel agent workers can each
append into shared state safely.

`backend/app/schemas/{analysis_task,finding,agent_output}.py` hold the corresponding Pydantic
models used for Supabase I/O and for validating each agent's strict JSON output (per `phase3.md`
§14) before it's converted into a `RawFinding`.

## 5. LLM Client (OpenRouter)

`backend/app/services/openrouter_client.py`:

- Defines an `LLMClient` protocol (`async def complete(self, *, system: str, user: str) -> str`)
  so tests can inject a fake implementation without any network access.
- `OpenRouterClient` implements this protocol using `httpx.AsyncClient`, POSTing to
  OpenRouter's chat completions endpoint with `model="deepseek/deepseek-chat-v3-0324"`.
- Config (`app/core/config.py` + `.env.example`) adds:
  ```env
  AGENT_LLM_PROVIDER=openrouter
  AGENT_LLM_MODEL=deepseek/deepseek-chat-v3-0324
  OPENROUTER_API_KEY_SUPERVISOR=
  OPENROUTER_API_KEY_SECURITY=
  OPENROUTER_API_KEY_PERFORMANCE=
  OPENROUTER_API_KEY_COMPLEXITY=
  OPENROUTER_API_KEY_DUPLICATION=
  OPENROUTER_API_KEY_RELIABILITY=
  AGENT_MAX_RETRIES=2
  AGENT_TIMEOUT_SECONDS=120
  LANGGRAPH_RECURSION_LIMIT=50
  MAX_AGENT_CONTEXT_CHUNKS=12
  MAX_FINDINGS_PER_AGENT=20
  ```
  This replaces `phase3.md` §19's `DEEPSEEK_API_KEY`/`AGENT_LLM_PROVIDER=deepseek` per the
  2026-07-06 OpenRouter decision. `REDIS_URL`/`SUPABASE_*`/`QDRANT_*`/`NEO4J_*` are unchanged
  (already present from Phase 1/2).
- Each agent/supervisor node is constructed with its own `OpenRouterClient` instance bound to
  its dedicated key. No shared client, no cross-key fallback: on failure/rate-limit, a node
  retries only with its own key up to `AGENT_MAX_RETRIES`, then marks its own
  `analysis_tasks` row `status = failed` and continues (does not fail the whole workflow).

## 6. Node-by-Node Design

### 6.1 `load_scan_context`

Loads lightweight scan/repo metadata from Supabase (`scans`, `repo_stats`) into
`RepoContext`. Does not load file/symbol/chunk rows here — that happens later, scoped, inside
`build_analysis_plan` and each agent's tools. Failure cases (scan not found, scan has
`status = failed`) populate `state["errors"]` and set `status = "context_load_failed"`.

### 6.2 `validate_analysis_ready`

Checks, in order:
1. `scan.status == "analyzed"` → silently skip: log `duplicate_job_skipped` scan event,
   set `status = "skipped"`, route to `END` (not `fail_analysis`).
2. `scan.status != "parsed"` (and not already `analyzed`) → `fail_analysis`
   (`SCAN_NOT_PARSED`).
3. Supabase has `scan_files` rows for `scan_id` → required.
4. Supabase has `code_chunks` rows for `scan_id` → required.
   (2026-07-06 decision: `code_symbols` rows are **not** required — a repo of only
   unsupported-language files can have 0 symbols but still be analyzable via chunks.)
5. Qdrant has points for `scan_id` (existing collection, non-zero count) → required.
6. Neo4j has a `:Scan {scan_id: ...}` node → required (verified this node type already exists
   via `neo4j_graph_service.py`).

Routes: `ready` → `build_analysis_plan`; `not_ready` → `fail_analysis` (sets
`scan.status = analysis_failed`, `scan_events.event_type = analysis_failed` with the specific
missing-precondition error code from `phase3.md` §20: `MISSING_SCAN_FILES` /
`MISSING_CODE_CHUNKS` / `MISSING_QDRANT_POINTS` / `MISSING_NEO4J_GRAPH`).

### 6.3 `build_analysis_plan` (hybrid deep planning supervisor)

Async node, uses the supervisor's dedicated `OpenRouterClient`.

1. Fetch structural metadata for the scan via `asyncio.to_thread`-wrapped Supabase/Neo4j tool
   calls: directory/file tree (all `scan_files` paths, no content), symbol names/types/LOC
   (capped to the top ~500 symbols by LOC — 2026-07-06 decision — with a note that
   additional lower-ranked symbols exist), import/dependency edges (from Neo4j), and detected
   languages/technologies (from `repo_stats.language_breakdown`). No raw code or chunk content
   is included in this prompt.
2. Call the LLM with this structural summary to produce a scoped `AnalysisTask` list — one or
   more tasks per agent, each with `target_file_ids`/`target_chunk_ids`/`target_symbol_ids`
   populated from the structural data (not invented IDs).
3. Persist each task as an `analysis_tasks` row (`status = "pending"`), then write the full
   `list[AnalysisTask]` (with `task_id` = each row's UUID) into `state["analysis_tasks"]`.
4. The structural metadata itself is never written into `AnalysisState` — only the resulting
   task list is, keeping the state lightweight per `phase3.md` §5/§8.
5. If the LLM call fails after `AGENT_MAX_RETRIES`, fall back to a deterministic plan (file
   extension / LOC / naming-heuristic based scoping per `phase3.md` §10.3) rather than failing
   the whole analysis — this fallback path is a pragmatic addition to keep the workflow
   resilient to a single supervisor LLM outage.

### 6.4 Dispatch (`Send`-based conditional edges, not a node)

Per the 2026-07-06 decision, `dispatch_agent_workers` is implemented exactly as `phase3.md`
§15's pseudocode: a routing function passed to `graph.add_conditional_edges("build_analysis_plan", dispatch_agent_workers, [...])`
that returns a list of `Send(agent_node_name, worker_input)` objects — it is not registered via
`graph.add_node(...)`.

### 6.5 Agent nodes (`security_agent`, `performance_agent`, `complexity_agent`,
`duplication_agent`, `reliability_agent`)

Each is `async def(worker_input) -> {"raw_findings": [...]}`:

1. Create/update its `analysis_tasks` row to `status = "running"`, `started_at = now()`.
2. Retrieve scoped context via the three tool wrappers (§7), each call wrapped in
   `asyncio.to_thread`:
   - Supabase metadata for its `target_file_ids`/`target_symbol_ids`.
   - Qdrant semantic search / similarity search scoped by `scan_id`, capped at
     `MAX_AGENT_CONTEXT_CHUNKS`.
   - Neo4j relationship queries scoped by `scan_id` (shallow depth, per `phase3.md` §12.3).
3. Build a compact prompt (objective + retrieved context only, per `phase3.md` §11's per-agent
   responsibilities and retrieval hints).
4. Call its dedicated `OpenRouterClient`, expecting a strict JSON array per `phase3.md` §14.
5. Validate the JSON against the `agent_output` schema; on invalid JSON, retry once with a
   stricter "return only a JSON array" repair prompt (still within `AGENT_MAX_RETRIES`).
6. On success: create an `agent_runs` row (`status = completed`, token counts if available),
   mark its `analysis_tasks` row `completed`, return findings capped at
   `MAX_FINDINGS_PER_AGENT`.
7. On exhausted retries/failure: create an `agent_runs` row (`status = failed` or `timeout`),
   mark its `analysis_tasks` row `failed`, log an `agent_failed` scan event, and return an
   empty findings list — **does not raise and does not fail the overall workflow** (partial
   results from the other agents still proceed to normalization).
8. Complexity Agent specifically: builds its prompt from the LLM + whatever `code_symbols`
   metadata Phase 2 already stored (`start_line`/`end_line`/LOC/`raw_code`/`metadata jsonb`);
   it does **not** re-parse `raw_code` with Tree-sitter to compute branch/nesting/parameter
   counts (2026-07-06 decision).

### 6.6 `normalize_findings`

For each `RawFinding` in `state["raw_findings"]`:
1. Validate JSON shape (already mostly validated per-agent in §6.5, this is a defense-in-depth
   pass across the merged list).
2. Map severity labels to the internal 4-value enum (`phase3.md` §10.6's mapping table).
3. Clamp `confidence` to `[0, 1]`.
4. Drop malformed findings (missing required fields) — log a count, don't fail the workflow.
5. Attach `scan_id`, `agent` (already present), compute `fingerprint` (per §10 formula:
   `scan_id` + `agent_name` + `file_path` + `symbol_name` + `start_line` + `end_line` +
   normalized `title`).
6. **Resolve `file_id`/`symbol_id`** (2026-07-06 decision — this node owns resolution, not a
   separate node): look up `scan_files`/`code_symbols` by `scan_id` + `file_path` (and
   `symbol_name` when present) via the Supabase tool; leave `null` if no match is found rather
   than failing.
7. Normalize file paths (strip leading `./`, normalize separators) and line numbers (clamp
   negative/`None` sensibly).

Output: `state["normalized_findings"]`.

### 6.7 `deduplicate_findings`

Groups `normalized_findings` by fingerprint plus the cross-agent merge rule from `phase3.md`
§10.7 (same file, same/overlapping symbol and line range, similar root cause title/description
→ merge). Merged findings get `primary_agent` = the first/highest-severity contributing agent
and `related_agents` = the rest. Output: `state["deduped_findings"]`.

### 6.8 `rank_findings`

Sorts `deduped_findings` by:
1. Severity (`extreme` → `high` → `medium` → `low`).
2. Confidence score (descending) — tie-breaker 1.
3. Evidence-item count (descending) — tie-breaker 2.
4. Related-agent count (descending) — tie-breaker 3.

(2026-07-06 decision: `phase3.md` §10.8's tie-breakers #4 Neo4j centrality and #5 high-risk
file path are deferred, not implemented in v1.)

### 6.9 `persist_findings`

Upserts each ranked finding into `findings` using `on conflict (scan_id, fingerprint) do
update` (idempotent per `phase3.md` §21). Only this node writes to the `findings` table.
Logs a `findings_stored` scan event with the total count.

### 6.10 `mark_scan_analyzed`

Sets `scans.status = "analyzed"`, `scans.updated_at = now()`, logs
`scan_events.event_type = "analysis_completed"`.

### 6.11 `fail_analysis`

Sets `scans.status = "analysis_failed"`, `scans.error_message` to the specific error code/
message, logs `scan_events.event_type = "analysis_failed"`. Reached from
`validate_analysis_ready`'s `not_ready` route or from unrecoverable errors in
`load_scan_context`.

## 7. Agent Tool Contracts

`backend/app/workflows/analysis/tools/`:

- `supabase_metadata_tool.py` — `get_scan`, `get_repo_stats`, `list_files`, `list_symbols`,
  `list_chunks`, `get_chunk_metadata`, `get_symbol_context`. All accept `scan_id` as a
  mandatory first argument; all paginate (no unbounded `select *`).
- `qdrant_retrieval_tool.py` — `search_code_chunks(scan_id, query, limit, ...)`,
  `find_similar_chunks(scan_id, chunk_id, limit)`. Every call includes a `scan_id` filter in
  the Qdrant query; never searches cross-scan.
- `neo4j_graph_tool.py` — `get_symbol_neighbors`, `get_file_imports`, `get_call_chain`,
  `get_central_symbols`, `find_external_call_sites`, `find_database_call_sites`. Every Cypher
  query is scoped by `scan_id`; depth kept small (1–2) per `phase3.md` §12.3.

All three wrap the existing Phase 2 sync clients (`supabase_client.py`, `qdrant_client.py`,
`neo4j_client.py`) unchanged — no new client libraries. Callers (async nodes) are responsible
for wrapping calls in `asyncio.to_thread`; the tools themselves stay plain sync functions so
they're trivially unit-testable without an event loop.

## 8. Error Handling & Idempotency

- Error codes per `phase3.md` §20, raised via the existing `AppError` pattern from Phase 1/2.
- `findings` upsert on `(scan_id, fingerprint)` makes `persist_findings` safe to retry.
- Already-`analyzed` scans are silently skipped (§6.2), not treated as `SCAN_ALREADY_ANALYZED`
  failures, mirroring Phase 2's `duplicate_job_skipped` pattern.
- A single agent's failure (LLM error, invalid JSON after retries, timeout) does not fail the
  whole analysis — it degrades to zero findings from that agent, logged via `agent_failed` and
  reflected in its `analysis_tasks`/`agent_runs` rows. Only `load_scan_context` /
  `validate_analysis_ready` failures fail the entire workflow.

## 9. Folder Structure

```
backend/
  app/
    workflows/
      analysis/
        graph.py
        state.py
        nodes/
          load_scan_context.py
          validate_analysis_ready.py
          build_analysis_plan.py
          normalize_findings.py
          deduplicate_findings.py
          rank_findings.py
          persist_findings.py
          mark_scan_analyzed.py
          fail_analysis.py
        agents/
          security_agent.py
          performance_agent.py
          complexity_agent.py
          duplication_agent.py
          reliability_agent.py
        tools/
          supabase_metadata_tool.py
          qdrant_retrieval_tool.py
          neo4j_graph_tool.py
        schemas/
          analysis_task.py
          finding.py
          agent_output.py
    services/
      openrouter_client.py
  db/
    migrations/
      0002_phase3.sql
  tests/
    test_openrouter_client.py
    test_load_scan_context.py
    test_validate_analysis_ready.py
    test_build_analysis_plan.py
    test_agents.py            # parametrized across the 5 agents
    test_normalize_findings.py
    test_deduplicate_findings.py
    test_rank_findings.py
    test_persist_findings.py
    test_analysis_graph.py     # end-to-end graph run with fully mocked tools/LLM
```

## 10. Testing Strategy

- `pytest-asyncio` added as a dev dependency for async node/graph tests.
- `respx` (already a dev dependency) mocks `httpx.AsyncClient` calls to OpenRouter — both
  success and failure/rate-limit/invalid-JSON scenarios.
- `pytest-mock` mocks the Supabase/Qdrant/Neo4j sync clients at the tool-function boundary
  (no real network calls).
- A `FakeLLMClient` implementing the `LLMClient` protocol is used for node/graph tests that
  don't specifically need to test HTTP-layer behavior (e.g., `test_analysis_graph.py`'s
  end-to-end run), returning canned strict-JSON responses per agent.
- `test_analysis_graph.py` runs the full compiled graph against a fully mocked scan (fixture
  Supabase rows, fixture Qdrant/Neo4j responses, fixture LLM responses for all 6 LLM roles)
  and asserts: all 5 agents ran, findings were normalized/deduped/ranked/persisted in the
  right order, and `scan.status == "analyzed"` at the end.
- Existing 53 Phase 1/2 tests must continue passing unchanged (`task backend:test`).

## 11. Implementation Order

1. Add `langgraph` dependency + `pytest-asyncio` dev dependency; verify existing tests pass.
2. Add `0002_phase3.sql` migration (`analysis_tasks`, `agent_runs`, `findings`).
3. Build `openrouter_client.py` (`LLMClient` protocol + `OpenRouterClient` + `FakeLLMClient`
   test double) and config/env wiring.
4. Build `state.py` and the three Pydantic schema modules.
5. Build `load_scan_context` + `validate_analysis_ready` + `fail_analysis`.
6. Build the three tool wrapper modules.
7. Build `build_analysis_plan` (supervisor).
8. Build the 5 agent nodes.
9. Build `normalize_findings` → `deduplicate_findings` → `rank_findings` → `persist_findings`
   → `mark_scan_analyzed`.
10. Assemble `graph.py` (`Send`-based dispatch) and expose `run_analysis(scan_id)`.
11. Wire `run_analysis` into `repo_scan_worker.py` after `status = parsed`.
12. Write/run full test suite (`task backend:test`).
13. Update `handoff.md` with this session's evidence.
