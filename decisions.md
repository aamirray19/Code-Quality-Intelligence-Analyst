
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

## 2026-07-10: LLM model switched from paid DeepSeek v3 to free Gemma models (supersedes 2026-07-06 model decision)

- Decision: `AGENT_LLM_MODEL` changed from `deepseek/deepseek-chat-v3-0324` to `google/gemma-4-31b-it:free`, with a new `AGENT_LLM_MODEL_FALLBACK=google/gemma-4-26b-a4b-it:free` tried on the same key when the primary model is rate-limited.
- Reason: The paid DeepSeek key ran out of credits during this session's first live end-to-end test, confirmed via a live `402 Payment Required` response from OpenRouter mid-report-generation. Switched to free-tier models to keep verifying the pipeline without a billing dependency.
- Alternatives rejected: Topping up the DeepSeek key's credits (not actioned this session); staying on a single free model with no fallback (rejected once free-tier `429 Too Many Requests` responses proved frequent under real 5-agent concurrent load).
- Consequences: Free-tier models carry much tighter per-minute rate limits than the paid key did. `agent_runs.model_name` now legitimately varies per call (primary or fallback model) instead of always being the single configured model. Some agents/report-generation runs will still hit exhausted rate limits under sustained load — see the next decision for the mitigation, and "Still broken or unverified" in the 2026-07-10 handoff entry for current gaps.
- Revisit when: A paid key with credits is available again, or free-tier limits prove too disruptive for real usage.

## 2026-07-10: Supersede "no cross-key fallback" — added model + key fallback cascade per specialist agent

- Decision: Supersedes the 2026-07-06 "One dedicated OpenRouter API key per agent + supervisor, no cross-key fallback" decision. Each of the 5 specialist agents now tries, in order: primary key + primary model → primary key + fallback model → (if configured) fallback key + primary model → fallback key + fallback model. New config: `AGENT_LLM_MODEL_FALLBACK` plus 5 optional `OPENROUTER_API_KEY_<AGENT>_FALLBACK` settings (security/performance/complexity/duplication/reliability only — supervisor and chatbot keep a single key each, no fallback tier for those). On a `429` specifically, the client backs off (2s/5s/10s across retries) and retries the same candidate before moving to the next one; other error types move to the next candidate immediately without waiting. `report_builder_service.py`'s final report-generation call got the same model-fallback + backoff treatment (no key fallback there, single chatbot key only, by explicit scope).
- Reason: The original "no fallback" decision assumed a single working key per agent under normal conditions. Live testing on free-tier models showed `429`s frequent enough that a single key/model combination can exhaust mid-scan, silently dropping that agent's findings entirely (observed directly: 4/5 agents failing simultaneously with identical errors when fired concurrently). Fallback absorbs this without abandoning the agent's task.
- Alternatives rejected: Keeping strict per-agent key isolation as originally decided — now considered too fragile against free-tier rate limits for practical live testing; sharing one pooled key across all agents — rejected, defeats the original decision's per-agent blast-radius-isolation benefit entirely.
- Consequences: Fallback keys are fully optional — `_llm_candidates()` (`agent_factory.py`) only includes configured, non-empty keys, so leaving the 5 fallback vars unset degrades gracefully to the original 2-model/1-key cascade. `RATE_LIMIT_BACKOFF_SECONDS` was moved from `agent_factory.py` to `openrouter_client.py` as a shared constant since both callers now need it.
- Revisit when: A paid key removes rate-limit pressure entirely, or the fallback cascade's timing/retry counts need tuning against real sustained traffic.

## 2026-07-10: Agent-turn concurrency capped at 2 (root-caused a Windows-dev-only failure mode)

- Decision: Added `AGENT_LLM_CONCURRENCY_LIMIT = 2` (`agent_factory._llm_semaphore`), wrapping each agent's *entire* turn — Supabase/Neo4j reads, the LLM call, and bookkeeping writes, not just the LLM call — so at most 2 of the 5 `Send`-dispatched agents are ever mid-turn concurrently. Also added a small retry-with-delay (`_run_with_retry`: 2 retries, 1s delay) specifically around `_gather_context`'s Supabase/Neo4j reads.
- Reason: Live testing surfaced `WinError 10035` (WSAEWOULDBLOCK) killing agent turns whenever all 5 agents fired concurrently. Root-caused via direct traceback inspection to Windows' `ProactorEventLoop` choking under a burst of simultaneous async OpenRouter connections, compounded by multiple threads hitting the single shared synchronous Supabase client via `asyncio.to_thread` at the same moment. Confirmed Windows-development-machine-specific: Linux's epoll-based event loop (e.g. Render, the originally-considered deploy target) does not have this particular overlapped-I/O failure mode, but the bug was blocking all local verification on this machine.
- Alternatives rejected: Switching the worker process to `WindowsSelectorEventLoopPolicy` (bigger blast radius — unconfirmed whether any code path relies on `asyncio` subprocess support, which `SelectorEventLoop` lacks on Windows; deferred rather than risk it blind); giving each concurrent thread its own Supabase client instance instead of sharing one singleton (a more invasive change to `app/db/supabase_client.py`'s existing singleton pattern, deferred in favor of the smaller, verified-working semaphore fix).
- Consequences: Agent turns now run in pairs rather than all 5 truly in parallel, so a full Phase 3 analysis takes longer wall-clock time locally than genuine 5-way concurrency would. Supabase/Neo4j context reads get one retry-with-delay on transient failure rather than failing the whole agent turn immediately.
- Revisit when: Deploying to a Linux host removes the root cause entirely — this cap could reasonably be raised or removed there, since the reason for it won't exist on that platform. Worth testing at higher concurrency once verified off Windows.

## 2026-07-10: Unhandled Phase 3 / agent exceptions no longer silently strand a scan

- Decision: Two blast-radius fixes, both bugs found live during this session's testing: (1) `agent_factory.run_agent`'s final failure-bookkeeping block (`_record_agent_run` / `_mark_task_failed` / `_log_agent_failed_event`) is now wrapped in its own try/except. Previously, a Supabase write failure occurring *during* failure-recording itself was unhandled and would escape `run_agent`, which LangGraph propagates as a fatal error for the entire `Send` fan-out step — killing all 5 concurrent agents instead of just the one agent's bookkeeping. (2) `repo_scan_worker.py`'s catch-all around `asyncio.run(run_analysis(scan_id))` now sets `scan.status = "analysis_failed"` and logs an `analysis_failed` scan_event on an uncaught exception. Previously it only logged server-side (`logger.exception(...)`), leaving the scan stuck at `status = "parsed"` forever with no error visible via any API the frontend polls.
- Reason: Both were observed directly — a scan got silently and permanently stuck mid-session with zero user-visible error signal before either fix was in place. `analysis_failed` was already a documented status value in `phase3.md` §17 but had never actually been wired up to fire from this code path.
- Alternatives rejected: None considered — both are straightforward correctness gaps, not design tradeoffs.
- Consequences: None negative. Scans that hit an unrecoverable Phase 3 exception now surface it properly (status + event) instead of hanging indefinitely at `parsed`.
- Revisit when: N/A — considered settled bug fixes.

## 2026-07-10: LLM provider switched from OpenRouter to Google AI Studio (Gemini)

- Decision: Replaced OpenRouter with Google AI Studio (Gemini API) as the LLM provider for all 5 specialist agents, the supervisor, and the chatbot/report-generation calls. `openrouter_client.py` was replaced by `google_ai_client.py` implementing an identical `GoogleAIClient`/`build_llm_client`/`AGENT_KEY_ATTR`/`RATE_LIMIT_BACKOFF_SECONDS` surface, so the retry/backoff/candidate-cascade flow and the `AGENT_LLM_CONCURRENCY_LIMIT` semaphore (both added in the 2026-07-10 fallback-cascade and concurrency-fix decisions above) are completely unchanged. Primary model `gemma-4-31b-it`, fallback `gemma-4-26b-a4b-it` (Gemma models served via the same Google AI Studio `generateContent` endpoint/shape as Gemini — confirmed via Google's own docs that Gemma 4 uses the identical API, so no client-code changes were needed for this model choice, only the two config values). `GoogleAIClient.last_usage` maps Gemini's native `usageMetadata` field names to the same OpenAI-style keys (`prompt_tokens`/`completion_tokens`/`total_tokens`) the old client used, so `agent_runs`'s existing columns keep populating with zero downstream changes. `agent_factory.py`'s `_record_agent_run` calls now pass `model_provider="google"` instead of `"openrouter"`.
- Reason: User-requested provider switch. Kept the whole flow (cascade, semaphore, error codes, retry/backoff) explicitly unchanged per instruction — this is a provider-adapter swap, not a redesign. Implemented via `docs/superpowers/plans/2026-07-10-google-ai-studio-migration.md` (8 TDD tasks, inline execution), all tests updated per-consumer and verified passing before the old files were deleted.
- Alternatives rejected: Keeping the `OpenRouterClient` name and just repointing its internals at Gemini's API — rejected as more confusing long-term than a clean rename, since every call site needed touching regardless of whether the class was renamed.
- Consequences: Google AI Studio's free tier applies rate limits **per Google Cloud project, not per API key** — unlike OpenRouter, provisioning multiple `GOOGLE_API_KEY_*_FALLBACK` values under the same GCP project will NOT provide real fallback headroom; each fallback key needs to come from a separate GCP project to actually isolate quota. This is a meaningful setup difference from the OpenRouter fallback-key architecture and has not yet been verified live (no real Google AI Studio credentials were exercised during the migration — full backend suite passed with mocked/respx-mocked HTTP calls only).
- Revisit when: Live-tested against real Google AI Studio keys (not yet done as of this decision); or if the per-project quota-sharing behavior proves too limiting even with separate projects.

## 2026-07-10: Embedding provider also switched — HuggingFace to Google AI Studio (Gemini Embedding 2)

- Decision: `embedding_service.py` (`embed_chunks`/`embed_texts`/`embed_text`) rewritten to call Google AI Studio's `batchEmbedContents` endpoint with model `gemini-embedding-2`, replacing the HuggingFace Inference API (`BAAI/bge-large-en-v1.5`). New setting `google_api_key_embedding` (separate from the 7 agent/supervisor/chatbot keys). Every request explicitly sets `outputDimensionality: 1024` (matching the existing Qdrant collections' vector size from the prior HF/BAAI model) and the service now L2-normalizes every returned vector before use, since Google's docs state vectors below the model's native 3072-dim aren't normalized by default when truncated via Matryoshka Representation Learning — skipping normalization would silently degrade Qdrant's cosine-distance search quality without erroring.
- Reason: User-requested provider switch, same motivation as the LLM/agent switch (consolidate everything onto Google AI Studio). Discovered live: the first scan after switching failed with a clean Qdrant 400 (`Vector dimension error: expected dim: 1024, got 3072`) — Gemini Embedding 2 defaults to 3072-dim, incompatible with the already-populated 1024-dim collections from tonight's earlier BAAI-embedded runs.
- Alternatives rejected: Deleting and recreating the Qdrant collections fresh at 3072-dim (rejected by explicit user choice — see the AskUserQuestion in this session; kept prior collections' dimension instead of resetting them).
- Consequences: `_normalize_embedding`/`_mean_pool` (needed for HF's ambiguous pooled-vs-per-token response shape) were removed entirely — Google's API always returns a single flat vector per input, no pooling ambiguity. `hf_api_token` setting is now dead/unused in `config.py` but was left in place (not deleting a working setting nobody asked to remove). `docs/phase2.md`'s embeddings env var block, previously already-stale pointing at a never-implemented `openai`/`text-embedding-3-small`, corrected to match.
- Revisit when: If Qdrant collections are ever reset/recreated from scratch, the 1024-dim truncation could be reconsidered in favor of a larger, more information-preserving dimension (768/1536/3072 are Google's "recommended" presets).

## 2026-07-10: Fixed two Gemma-specific response/request-shape bugs in `google_ai_client.py`

- Decision: Two related bugs found and fixed during live testing of the 5 specialist agents against real Gemma models: (1) Gemma's "thinking" mode can return multiple `parts` per response — a reasoning-trace part marked `"thought": true` followed by the real answer — and the client was naively taking `parts[0]["text"]`, silently returning the reasoning trace (not valid JSON) instead of the agent's actual findings. Fixed via a new `_extract_answer_text()` helper that filters out any part where `part.get("thought")` is truthy before concatenating the rest. (2) An attempted fix — setting `generationConfig.thinkingConfig.thinkingBudget: 0` to disable thinking mode at the request level (the officially documented way to do this for Gemini models) — was tried first and confirmed live to fail with a clean `400 Bad Request: "Thinking budget is not supported for this model."` Gemma does not support `thinkingConfig` at all; it was removed from the request payload entirely, leaving `_extract_answer_text()`'s response-side filtering as the only defense.
- Reason: Both found live, not from documentation — Google's docs describe `thinkingConfig` as a general `generateContent` config option without calling out that Gemma model variants reject it outright, and don't mention Gemma 4's thinking-mode response shape differing from a non-thinking model's single-part response.
- Alternatives rejected: None for (1) — straightforward correctness bug. For (2), no alternative considered since the isolated direct-API test immediately confirmed the 400 rejection; no reason to keep dead, actively-broken request config.
- Consequences: Every `complete()` call now inspects `part.get("thought")` on every response, adding negligible overhead. If Google ever adds `thinkingConfig` support to Gemma, or the project switches back to a Gemini model, the response-side filter still works correctly either way (it's a no-op when no part is marked `"thought"`), so no further change would be needed for that transition.
- Revisit when: N/A — considered settled bug fixes, confirmed via a live 5/5-agent clean-success run after both fixes landed.

## 2026-07-10: Fixed cross-event-loop semaphore reuse crash (`reset_llm_semaphore`)

- Decision: `agent_factory._llm_semaphore` is an `asyncio.Semaphore` created once at module-import time. `repo_scan_worker.py` invokes Phase 3 via a fresh `asyncio.run(run_analysis(scan_id))` per scan — each call gets its own new event loop, and an `asyncio.Semaphore` binds to whichever loop first acquires it. The second scan processed by the same long-lived RQ worker process (without a process restart in between) crashed immediately with `<Semaphore ... [locked]> is bound to a different event loop`. Fixed by adding `agent_factory.reset_llm_semaphore()`, which reassigns the module-level `_llm_semaphore` to a brand-new `asyncio.Semaphore` instance, called once at the top of `graph.run_analysis()` before the graph runs — so every scan gets a semaphore freshly bound to its own loop.
- Reason: Found live — this is the first time in the whole session two scans were processed by the same worker process without an intervening restart (every earlier live test restarted both backend and worker before each scan), so the bug was latent all along but never triggered until tonight.
- Alternatives rejected: None considered — this is a correctness bug in how the semaphore's lifecycle relates to `asyncio.run()`'s per-call event loop, not a design tradeoff.
- Consequences: None negative. A production deployment where the RQ worker processes many scans in its lifetime (the normal case) would have hit this crash on every second-and-later scan; now confirmed fixed via two consecutive scans on the same worker process, the second one running clean.
- Revisit when: N/A — considered a settled bug fix.

## 2026-07-10: Hour-long hang left unresolved — chose to retry rather than investigate the root cause

- Decision: One live scan hung for over an hour (`scan_parsed` to `analysis_failed` was ~63 minutes) before finally erroring with `WinError 10054` ("An existing connection was forcibly closed by the remote host"), meaning `asyncio.wait_for(timeout=120)` in `google_ai_client.py` did not actually bound wall-clock time for that request — something held a connection open (or silently dead) for over 30x the configured timeout. Given the choice between investigating the timeout-enforcement gap immediately versus just retrying, the user chose to retry first. The retry (and every subsequent scan) completed normally, suggesting this was a one-off network-level event rather than a reliably reproducible bug — but the underlying gap (client-side timeouts not reliably bounding a stalled/dead TCP connection on Windows) was never actually fixed or root-caused, just not re-observed.
- Reason: User's explicit choice among presented options, prioritizing forward progress over investigating a possibly-transient issue late in a long session.
- Alternatives rejected: Adding explicit granular `httpx.Timeout(connect=, read=, write=, pool=)` timeouts instead of the current blanket `timeout=` value, and investigating why `wait_for`'s cancellation didn't free the stalled connection — both deferred, not done.
- Consequences: This class of hang could recur in production with no code-level guard against it beyond the (apparently insufficient) `wait_for` wrapper. Since it self-resolved into a proper `analysis_failed` status rather than corrupting data or crashing the worker (thanks to the earlier "unhandled exceptions no longer silently strand a scan" fix), the blast radius of a recurrence is contained to one slow/stuck scan, not a systemic outage.
- Revisit when: If this hang recurs, especially if it recurs reproducibly (same repo, same agent, same conditions) rather than as an apparent one-off.
