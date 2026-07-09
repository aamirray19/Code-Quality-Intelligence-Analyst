
# Decisions

## YYYY-MM-DD: Decision title

- Decision:
- Reason:
- Alternatives rejected:
- Consequences:
- Revisit when:

## 2026-07-06: Phase 3 queue trigger — same worker continues (Option A)

- Decision: Phase 3 analysis runs by having the same Phase 2 worker directly invoke the LangGraph analysis workflow after `status = parsed`, instead of pushing a separate job to a dedicated `analysis_queue`.
- Reason: Simpler for the first implementation; avoids standing up a second Redis queue/worker before the analysis workflow itself is proven out.
- Alternatives rejected: Option B (separate `analysis_queue` + dedicated analysis worker) — deferred as a production-scaling improvement, not needed for v1.
- Consequences: Parsing/indexing and agent analysis cannot scale independently yet; a slow/stuck analysis run blocks the same worker process that just finished Phase 2 for that scan.
- Revisit when: Analysis workload needs independent scaling from the scan/parse workload, or LLM latency starts bottlenecking Phase 2 throughput.

## 2026-07-06: Phase 3 LLM provider — build against mocked/abstracted interface first

- Decision: Implement agent LLM calls behind a swappable interface (mirroring Phase 2's approach to Qdrant/Neo4j/HF); no live `DEEPSEEK_API_KEY` is available yet, so live LLM calls are deferred.
- Reason: User has no working DeepSeek credentials yet; keeps Phase 3 unit-testable without live network/LLM dependencies, consistent with how Phase 2 was built and tested.
- Alternatives rejected: Waiting to implement agents until live credentials exist.
- Consequences: Agent output quality/prompt correctness cannot be verified end-to-end until real DeepSeek credentials are supplied and smoke-tested.
- Revisit when: A working `DEEPSEEK_API_KEY` is available for live smoke testing.

## 2026-07-06: Complexity Agent metrics — use LLM + existing metadata only, don't re-parse

- Decision: The Complexity Agent will rely on the LLM plus whatever metadata Phase 2 already stored (`start_line`/`end_line`/`raw_code`/generic `metadata jsonb`) rather than re-parsing `raw_code` with Tree-sitter to compute `branch_count`/`loop_count`/`nesting_depth`/`parameter_count`.
- Reason: Phase 2's `code_symbols` table and `symbol_extraction_service.py` do not compute or store these deterministic metrics (verified: only LOC via start/end line, no branch/nesting/parameter counts exist). Re-parsing in Phase 3 would duplicate Phase 2's parsing work and add complexity/latency.
- Alternatives rejected: Re-parsing `raw_code` with Tree-sitter inside Phase 3 to compute deterministic complexity metrics as `phase3.md` §11.3 originally assumed.
- Consequences: Complexity findings are LLM-judgment-driven rather than backed by precomputed deterministic metrics; less consistent/reproducible than the spec's original "deterministic metrics identify candidates" intent.
- Revisit when: Phase 2's symbol extraction is later extended to compute these metrics, or Complexity Agent output proves too inconsistent without them.

## 2026-07-06: `analysis_tasks.task_id` — use DB UUID only, no separate text column

- Decision: `AnalysisTask`/`analysis_tasks` rows are identified only by the Supabase-generated `id uuid`; no additional human-readable `task_id` text column (e.g. `"security_001"`) is added, despite `phase3.md` §9's example JSON showing one.
- Reason: Avoids a redundant identifier column; the UUID is sufficient for all internal references (agent_runs.analysis_task_id, LangGraph state, etc.).
- Alternatives rejected: Adding a `task_id text` column to `analysis_tasks` to match the spec's example payload literally.
- Consequences: LangGraph `AnalysisTask.task_id` (if kept in code) must be populated from the DB-generated UUID, not a custom string like the spec's example.
- Revisit when: A human-readable task identifier becomes necessary for debugging/logging across services.

## 2026-07-06: Finding file_id/symbol_id resolution happens in `normalize_findings`

- Decision: The `normalize_findings` node is responsible for resolving each raw finding's `file_path`/`symbol_name` (returned by agents per the strict JSON schema) back to Supabase `file_id`/`symbol_id`, in addition to its other responsibilities (JSON validation, severity mapping, fingerprinting, etc.).
- Reason: `phase3.md` specifies agents return only `file_path`/`symbol_name`, but the `findings` table stores `file_id`/`symbol_id` as well; the doc did not assign this resolution step to any specific node, so it's grouped with normalization since that node already does per-finding cleanup/attachment.
- Alternatives rejected: A separate dedicated resolution node between agents and normalize_findings.
- Consequences: `normalize_findings` needs Supabase lookup access (file/symbol tables scoped by scan_id), not just in-memory transformation.
- Revisit when: Resolution logic becomes complex enough (e.g. fuzzy path/symbol matching) to warrant its own node.

## 2026-07-06: Already-analyzed scans are silently skipped

- Decision: If the analysis workflow/worker is invoked for a scan whose `status` is already `analyzed` (or otherwise past the analyzable point), it logs a `duplicate_job_skipped`-style scan event and returns early, without raising `SCAN_ALREADY_ANALYZED` as a failure.
- Reason: Mirrors the existing Phase 2 design decision where the worker skips (rather than reprocesses or fails) jobs for scans already at `status = "parsed"`, logging a `duplicate_job_skipped` event instead of going through the `AppError`/failure path.
- Alternatives rejected: Treating re-triggered analysis on an `analyzed` scan as a hard error via `SCAN_ALREADY_ANALYZED`.
- Consequences: `SCAN_ALREADY_ANALYZED` (phase3.md §20) becomes an informational/logged case rather than a raised error code in the normal skip path; it may still be used if needed for stricter API-level rejections elsewhere.
- Revisit when: A use case requires explicit re-analysis (e.g. a "re-run analysis" feature), which would need a different status/flow than silent skip.

## 2026-07-06: `dispatch_agent_workers` implemented as conditional-edge routing (Send), not a graph node

- Decision: `dispatch_agent_workers` is implemented as the routing function passed to `graph.add_conditional_edges(...)` (returning a list of `Send(...)` objects), matching `phase3.md` §15's working pseudocode — it is not added to the graph via `graph.add_node(...)` despite being listed alongside other nodes in §10.4.
- Reason: §15's actual LangGraph pseudocode implements it this way, and this is the correct/idiomatic LangGraph pattern for fan-out to parallel agent workers via `Send`. §10.4 listing it as a "node" is a minor spec inconsistency.
- Alternatives rejected: Adding it as a real graph node per §10.4's literal wording.
- Consequences: None functionally; keeps the graph structure aligned with LangGraph's `Send`-based parallel dispatch pattern.
- Revisit when: N/A — this is considered settled unless LangGraph's API changes.

## 2026-07-06: Missing `code_symbols` rows does not block analysis; only `code_chunks` is required

- Decision: `validate_analysis_ready` requires that Supabase has `code_chunks` rows (and `scan_files` rows) for the scan, but does **not** hard-block analysis solely because a scan has zero `code_symbols` rows.
- Reason: A repo containing only unsupported-language files (e.g. all Markdown/JSON/config) can legitimately produce 0 symbols while still having discovered files and chunks; blocking analysis in that case would prevent any findings (e.g. security/duplication over plain-text/config content) for otherwise valid repos.
- Alternatives rejected: Treating "no `code_symbols` rows" as a hard readiness failure per `phase3.md` §3's literal listing of `code_symbols` as a required check.
- Consequences: Agents (especially Complexity, which leans on symbol-level metadata) may receive little or no symbol-level context for such repos and should degrade gracefully to chunk-level analysis instead of erroring.
- Revisit when: N/A — considered a deliberate relaxation of the spec's stricter wording.

## 2026-07-06: LLM provider switched to OpenRouter (DeepSeek v3, pinned slug)

- Decision: Phase 3 agent/supervisor LLM calls go through OpenRouter (not DeepSeek's API directly), using the pinned model slug `deepseek/deepseek-chat-v3-0324`. This supersedes `phase3.md` §19's `AGENT_LLM_PROVIDER=deepseek` / `AGENT_LLM_MODEL=deepseek-reasoner` / `DEEPSEEK_API_KEY`.
- Reason: User has 6 OpenRouter API keys available (one per agent + one for the supervisor), not a direct DeepSeek key. A version-pinned model slug avoids silent behavior changes if OpenRouter repoints a floating "latest" alias.
- Alternatives rejected: Direct DeepSeek API (`deepseek-reasoner`) per the original doc; floating `deepseek/deepseek-chat` alias (could change underlying model without notice).
- Consequences: New env vars replace the doc's `DEEPSEEK_API_KEY`: `OPENROUTER_API_KEY_SUPERVISOR`, `OPENROUTER_API_KEY_SECURITY`, `OPENROUTER_API_KEY_PERFORMANCE`, `OPENROUTER_API_KEY_COMPLEXITY`, `OPENROUTER_API_KEY_DUPLICATION`, `OPENROUTER_API_KEY_RELIABILITY`. `AGENT_LLM_PROVIDER=openrouter`, `AGENT_LLM_MODEL=deepseek/deepseek-chat-v3-0324`.
- Revisit when: OpenRouter deprecates this pinned slug, or a different DeepSeek v3 revision is preferred.

## 2026-07-06: One dedicated OpenRouter API key per agent + supervisor, no cross-key fallback

- Decision: Each of the 5 specialist agents and the supervisor uses its own dedicated OpenRouter API key (`OPENROUTER_API_KEY_<AGENT_NAME>` / `OPENROUTER_API_KEY_SUPERVISOR`). If an agent's dedicated key is rate-limited or fails, it retries only with its own key up to `AGENT_MAX_RETRIES`, then marks that agent's task as failed — no borrowing another agent's idle key.
- Reason: Keeps key/rate-limit isolation simple and predictable; avoids cross-agent contention or coordination logic for key selection.
- Alternatives rejected: Falling back to another agent's key when the assigned one is exhausted/failing.
- Consequences: A single agent's key outage/rate-limit only degrades that agent's findings for the run (task marked failed/skipped), not the whole analysis; overall analysis can still complete with partial findings from the other 4 agents.
- Revisit when: Key-sharing or a shared key pool becomes necessary (e.g. cost consolidation, or key provisioning changes).

## 2026-07-06: Rank_findings tie-breakers limited to 4 for v1 (drop graph-centrality and high-risk-path signals)

- Decision: `rank_findings` tie-breakers for v1 are, in order: (1) severity, (2) confidence score, (3) evidence-item count, (4) related-agent count. `phase3.md` §10.8's tie-breakers #4 (Neo4j call-graph centrality) and #5 (high-risk file path, e.g. auth/config/db/payments) are deferred, not implemented in v1.
- Reason: Simpler, fully deterministic ranking without needing a Neo4j centrality query or a maintained "high-risk path" heuristic list for the first version.
- Alternatives rejected: Implementing all 5 tie-breakers from the spec in v1.
- Consequences: Findings in files Neo4j would consider "central" or conventionally high-risk (auth/config/db) get no ranking boost beyond their own severity/confidence/evidence/related-agent signals.
- Revisit when: Ranking quality in practice shows ties need the graph-centrality or high-risk-path signals to break correctly.

## 2026-07-06: Async LangGraph agent/supervisor nodes; sync Phase 2 tool clients wrapped via asyncio.to_thread

- Decision: The 5 agent nodes and supervisor node are `async def`, using `httpx.AsyncClient` for OpenRouter LLM calls so the 5 agent LLM calls run concurrently via LangGraph's `Send`-based fan-out. Existing Phase 2 tool clients (Supabase `create_client`, Qdrant client, Neo4j driver — all synchronous, verified in `backend/app/db/supabase_client.py` and `embedding_service.py`) are reused as-is but every blocking call from within an async node is wrapped in `asyncio.to_thread(...)` rather than rewriting those clients as native async. The RQ worker (`process_repo_scan`, a plain sync function) bridges into the async graph via `asyncio.run(graph.ainvoke(...))` at the point Phase 3 is invoked.
- Reason: The dominant latency in agent nodes is the LLM HTTP round-trip (multi-second), so only that needs true async concurrency; wrapping the fast sync Supabase/Qdrant/Neo4j calls in `to_thread` prevents them from blocking the event loop during concurrent agent execution, without the effort/risk of rewriting already-tested Phase 2 clients as native async.
- Alternatives rejected: Rewriting Supabase/Qdrant/Neo4j clients as native async (bigger effort, touches tested Phase 2 code); keeping everything fully synchronous (loses concurrency benefit for the 5 parallel LLM calls).
- Consequences: Agent/supervisor node code must consistently wrap every sync tool-client call in `asyncio.to_thread`; the RQ worker entrypoint needs an `asyncio.run(...)` bridge since RQ jobs are sync.
- Revisit when: Phase 2 clients are ever migrated to native async libraries, or thread-pool overhead becomes a bottleneck.

## 2026-07-06: Hybrid deep planning — supervisor sees structural metadata only, never raw code

- Decision: The supervisor node fetches the full repository *structure* (directory hierarchy, file paths, symbol names/types/LOC, import/dependency edges, detected languages/technologies) from Supabase/Neo4j and feeds this structural metadata (not raw code or chunk content) to the LLM to produce an intelligent, architecture-aware scoped analysis plan per agent. This structural data is fetched and used locally within the supervisor node's own execution — it is not persisted into `AnalysisState` (only the resulting scoped task list is written to state), keeping `phase3.md` §5/§8's "don't load the whole repo into state" rule intact in spirit. Raw code/chunk content is retrieved later, only for the specific scope assigned, when each agent's tools run.
- Reason: User wants the supervisor to plan intelligently based on real architecture/dependency understanding rather than purely deterministic heuristics, while still avoiding blowing up LLM context size or violating the state-lightweighting design rule.
- Alternatives rejected: Pure deterministic-metadata-first planning per `phase3.md` §10.3's original literal wording (LLM only "helps prioritize"); sending raw code samples to the supervisor for planning.
- Consequences: For very large repos, structural metadata alone (all file paths + all symbols + all import edges) could still exceed the LLM context window. A cap/summarization strategy is required (see next decision). The supervisor node needs broader read access to Supabase/Neo4j metadata than a minimal "lightweight scan context" implies, though still no raw code.
- Revisit when: Cap sizes prove wrong in practice (too small = poor plans, too large = context overflow/cost), or a cheaper/faster structural-summarization approach becomes available.

## 2026-07-06: Structural metadata sent to supervisor is capped for large repos

- Decision: For repos whose full structural metadata would exceed a reasonable LLM context budget, the supervisor prompt includes the full lightweight directory/file tree, but caps symbol-level detail to roughly the top ~500 symbols by LOC, with a note that additional lower-ranked files/symbols exist but were not individually detailed.
- Reason: User agreed a sensible default cap is fine, deferring exact tuning to implementation; avoids unbounded prompt growth for large repos (up to the 50MB `MAX_REPO_SIZE_KB` limit) that could contain thousands of files/symbols.
- Alternatives rejected: Sending every file/symbol/import edge unconditionally regardless of repo size; having the user specify exact numeric caps up front.
- Consequences: For very large repos, the supervisor's plan is based on the most significant (largest) symbols/files rather than a truly complete picture; this cap may need tuning once tested against real medium/large repos.
- Revisit when: Real repo testing shows the cap is too aggressive (plans miss important small-but-critical files, e.g. a small auth config file) or too generous (context overflow/cost issues).

## 2026-07-07: Phase 4 findings source table is `findings`, not `scan_findings`

- Decision: Phase 4's report generation and RAG chatbot read findings from the existing `findings` table (created in `backend/db/migrations/0002_phase3.sql` for Phase 3), not a table named `scan_findings` as literally written in `docs/phase4.md` §3.1/§6/§9.1.
- Reason: `phase4.md` was written independently of the actual Phase 3 implementation and uses `scan_findings` as a placeholder/typo; no such table exists or was ever created. The real table is `findings`, scoped by `scan_id`, per the 2026-07-06 Phase 3 decisions.
- Alternatives rejected: Renaming/aliasing the existing `findings` table to `scan_findings` to match the doc literally.
- Consequences: All Phase 4 services/queries referencing "scan_findings" per the doc must be implemented against `findings` instead. `phase4.md` should be treated as descriptive intent, not a literal schema reference, for this table name.
- Revisit when: N/A — considered a settled spec correction.

## 2026-07-07: Migrations consolidated into a single `0001_init.sql` file

- Decision: `backend/db/migrations/0002_phase3.sql` (`analysis_tasks`, `agent_runs`, `findings`) was merged directly into `backend/db/migrations/0001_init.sql` and deleted, so the project maintains one running migration file instead of a new numbered file per phase.
- Reason: User requested consistency with the precedent already set for Phase 2 (whose tables were merged directly into `0001_init.sql` rather than split into their own migration), and neither `0001_init.sql` nor `0002_phase3.sql` had been applied to a live Supabase project yet, so merging carried no risk of breaking an already-migrated database.
- Alternatives rejected: Keeping numbered per-phase migration files (`0001`, `0002`, `0003`, ...) as originally started with Phase 3's `0002_phase3.sql`.
- Consequences: All future schema changes, including Phase 4's new tables (`reports`, `chat_sessions`, `chat_messages`), are added directly into `0001_init.sql` rather than as new numbered migration files — the project uses a single ever-growing schema file, not a versioned migration chain. Any documentation or specs referencing `0002_phase3.sql` or a future `0003_phase4.sql` (e.g. `docs/superpowers/specs/2026-07-06-phase3-implementation-design.md`, `docs/superpowers/specs/2026-07-07-phase4-implementation-design.md`, prior `handoff.md` entries) are historical session logs/specs and were intentionally left unchanged.
- Revisit when: If the project later adopts a formal migration-tool workflow (e.g. Alembic-style versioned migrations) that expects one file per change, this single-file approach should be reconsidered.

## 2026-07-07: Phase 4 tables added directly to `0001_init.sql`, no `0003_phase4.sql`

- Decision: Superseding the "Phase 4 will still get a separate `0003_phase4.sql`" note in the migration-consolidation decision above — Phase 4's `reports`, `chat_sessions`, `chat_messages` tables are added directly into `backend/db/migrations/0001_init.sql`, and no `0003_phase4.sql` file is created. `docs/superpowers/plans/2026-07-07-phase4-report-and-chatbot.md` Task 1 was updated to modify `0001_init.sql` in place instead of creating a new file.
- Reason: User explicitly requested this change after reviewing the consolidation decision, extending the single-migration-file approach to all future schema work, not just the Phase 1-3 backfill.
- Alternatives rejected: Creating `0003_phase4.sql` as a new incremental migration (the originally planned approach).
- Consequences: Every future phase's schema changes go into `0001_init.sql` going forward, not new numbered files. This must be applied to a live Supabase project as one full schema script (still not yet applied as of this decision).
- Revisit when: If the project later adopts a formal migration-tool workflow, or if `0001_init.sql` grows unwieldy enough that per-phase files become preferable again.


