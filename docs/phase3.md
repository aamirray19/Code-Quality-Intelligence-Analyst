# Phase 3 — LangGraph Analysis Workflow

## 1. Goal

Phase 3 is responsible for running the code-quality analysis workflow after the repository has already been cloned, parsed, chunked, embedded, and indexed by Phase 2.

Phase 3 uses LangGraph to orchestrate a supervisor-worker analysis flow. The supervisor creates scoped analysis tasks, five specialized agents analyze the prepared repository context, and the workflow normalizes, deduplicates, ranks, and stores findings in Supabase.

Phase 3 prepares structured findings for Phase 4.

Phase 3 does **not** clone repositories, parse files, create embeddings, build the Neo4j graph, generate the final human-readable report, or answer chatbot questions. Those responsibilities belong to earlier or later phases.

---

## 2. Phase 3 Scope

### Included in Phase 3

- Consume a Phase 3 analysis job using `scan_id`.
- Load lightweight scan context from Supabase.
- Verify that Phase 2 has completed successfully.
- Verify that required Supabase, Qdrant, and Neo4j data exists.
- Update scan status throughout the analysis lifecycle.
- Run a LangGraph supervisor-worker workflow.
- Create a scoped analysis plan.
- Run five specialized agents:
  - Security Agent
  - Performance Agent
  - Complexity Agent
  - Duplication Agent
  - Reliability / Fault Tolerance Agent
- Allow each agent to retrieve relevant context using:
  - Supabase metadata
  - Qdrant semantic retrieval
  - Neo4j graph queries
- Require strict JSON findings from each agent.
- Normalize findings into one schema.
- Deduplicate overlapping findings.
- Rank findings by severity.
- Store final findings in Supabase.
- Store agent execution records in Supabase.
- Mark the scan as `analyzed`.

### Not Included in Phase 3

- GitHub URL validation.
- Scan creation.
- Redis job creation for repository scanning.
- Repository cloning.
- File discovery.
- Tree-sitter parsing.
- Symbol extraction.
- Code chunk creation.
- Embedding generation.
- Qdrant indexing.
- Neo4j graph creation.
- Final report generation.
- RAG chatbot response generation.
- Frontend report rendering.
- Automatic code fixing.

---

## 3. Phase 3 Start Condition

Phase 3 should only start when Phase 2 has completed successfully.

Required condition:

```text
scan.status == parsed
```

Additional readiness checks:

```text
Supabase has scan metadata
Supabase has scan_files rows
Supabase has code_symbols rows
Supabase has code_chunks rows
Qdrant has chunk vectors scoped by scan_id
Neo4j has graph nodes and relationships scoped by scan_id
```

If any of these checks fail, Phase 3 should not run agent analysis.

---

## 4. Final Phase 3 Worker Flow

```text
Analysis job received by worker
        ↓
Worker reads scan_id
        ↓
Load lightweight scan context from Supabase
        ↓
Check Phase 2 completion
        ↓
Update scan status = analyzing
        ↓
Create scan event = analysis_started
        ↓
LangGraph workflow starts
        ↓
Supervisor creates scoped analysis plan
        ↓
Run 5 analysis agents in parallel:
  ├── Security Agent
  ├── Performance Agent
  ├── Complexity Agent
  ├── Duplication Agent
  └── Reliability / Fault Tolerance Agent
        ↓
Each agent retrieves relevant context:
  ├── Supabase metadata tool
  ├── Qdrant retrieval tool
  └── Neo4j graph query tool
        ↓
Agents return strict JSON findings
        ↓
Normalize agent outputs
        ↓
Deduplicate overlapping findings
        ↓
Rank severity:
  Extreme → High → Medium → Low
        ↓
Store findings in Supabase
        ↓
Store agent run summaries in Supabase
        ↓
Update scan status = analyzed
        ↓
Create scan event = analysis_completed
        ↓
Phase 4 begins
```

---

## 5. Important Design Rule

Phase 3 should not load the whole repository into LangGraph state.

Correct:

```text
Load only control metadata into LangGraph state.
Retrieve detailed code context inside agent tools when needed.
Scope every retrieval by scan_id.
```

Incorrect:

```text
Load every source file into state.
Load every code chunk into state.
Load the full Neo4j graph into state.
Ask every agent to analyze the whole repository blindly.
```

Reason:

```text
LangGraph state should coordinate the workflow.
Supabase should store permanent metadata.
Qdrant should store semantic code chunks.
Neo4j should store structural relationships.
Agents should retrieve only the context needed for their assigned task.
```

---

## 6. Phase 3 Architecture

```text
Redis Cloud / Analysis Queue
        ↓
Render Worker
        ↓
LangGraph Analysis Workflow
        ↓
Supervisor Node
        ↓
Specialized Agent Workers
  ├── Security Agent
  ├── Performance Agent
  ├── Complexity Agent
  ├── Duplication Agent
  └── Reliability Agent
        ↓
Analysis Tools
  ├── Supabase Metadata Tool
  ├── Qdrant Retrieval Tool
  └── Neo4j Graph Query Tool
        ↓
Post-processing Nodes
  ├── Normalize Findings
  ├── Deduplicate Findings
  ├── Rank Findings
  └── Persist Findings
        ↓
Supabase Findings Tables
        ↓
status = analyzed
```

---

## 7. Queue Model

Phase 1 uses the repository scan queue to start Phase 2.

Phase 3 can be started in either of two ways:

### Option A — Same Worker Continues Immediately

```text
Phase 2 completes
        ↓
status = parsed
        ↓
Same worker directly invokes Phase 3 LangGraph workflow
```

This is simpler for the first implementation.

### Option B — Separate Analysis Queue

```text
Phase 2 completes
        ↓
status = parsed
        ↓
Push analysis job to Redis
        ↓
Analysis worker consumes job
        ↓
Phase 3 begins
```

This is better for production because parsing/indexing and agent analysis can scale independently.

Recommended production queue:

```text
analysis_queue
```

### Expected Analysis Job Payload

```json
{
  "job_type": "repo_analysis",
  "scan_id": "9f3c7c5a-7b90-4a6f-b56e-3bfa02d8f091",
  "repo": {
    "full_name": "owner/repo",
    "branch": "main",
    "commit_sha": "abc123"
  },
  "created_at": "2026-07-01T13:50:00Z"
}
```

---

## 8. Lightweight Scan Context

The `load_scan_context` node should not load all code.

It should load only metadata needed to plan the workflow.

### Load from Supabase

```text
scan_id
repo_full_name
repo_owner
repo_name
branch
default_branch
commit_sha
scan.status
repo_size_kb
total_files
total_symbols
total_chunks
language_distribution
qdrant_collection_name
neo4j_database
created_at
updated_at
```

### Optional Planning Metadata

```text
largest files by LOC
largest symbols by LOC
files with parse errors
files with external API calls
files with database-related imports
files with auth/security-related names
high-complexity symbol candidates
duplicate candidate groups if precomputed
```

### Do Not Load

```text
all raw code
all AST dumps
all embeddings
all Qdrant vectors
full Neo4j graph
all file contents
```

---

## 9. What the Supervisor Does

The supervisor is the planning node.

It does not deeply analyze the repository. It decides which parts of the repository each agent should inspect.

The supervisor creates an analysis plan like this:

```text
Security Agent:
  inspect auth files, config files, database query files, shell command usage, token/secret-like chunks.

Performance Agent:
  inspect large functions, loops, repeated IO calls, database-heavy code, network-heavy code.

Complexity Agent:
  inspect large functions, deep nesting, many branches, large classes, high LOC symbols.

Duplication Agent:
  inspect semantically similar chunks from Qdrant and repeated structural patterns.

Reliability Agent:
  inspect external service calls, file IO, database transactions, missing retry/timeout handling, missing exception handling.
```

The supervisor output is a list of scoped tasks.

Example:

```json
[
  {
    "task_id": "security_001",
    "agent": "security",
    "objective": "Find security vulnerabilities in authentication, configuration, database access, and command execution code.",
    "target_file_ids": ["file_uuid_1", "file_uuid_2"],
    "target_chunk_ids": ["chunk_uuid_7", "chunk_uuid_9"],
    "target_symbol_ids": ["symbol_uuid_3"],
    "priority": 1
  },
  {
    "task_id": "complexity_001",
    "agent": "complexity",
    "objective": "Analyze large functions and classes with high branch count or nesting depth.",
    "target_file_ids": ["file_uuid_8"],
    "target_chunk_ids": ["chunk_uuid_21"],
    "target_symbol_ids": ["symbol_uuid_11"],
    "priority": 2
  }
]
```

Important rule:

```text
The supervisor creates scoped work.
The agents execute scoped work.
The normalizer cleans the result.
The persister writes the result.
```

---

## 10. LangGraph Nodes

## 10.1 `load_scan_context`

Purpose:

```text
Load lightweight scan and repository metadata from Supabase.
```

Reads:

```text
scans
scan_files
code_symbols
code_chunks
repo_stats
parse_errors
```

Writes to graph state:

```text
repo_context
status
```

Failure cases:

```text
scan not found
scan has failed status
scan has no files
scan has no chunks
```

---

## 10.2 `validate_analysis_ready`

Purpose:

```text
Ensure Phase 2 completed and all required stores are ready.
```

Checks:

```text
scan.status == parsed
Supabase file records exist
Supabase chunk records exist
Qdrant collection exists
Qdrant contains points for scan_id
Neo4j graph contains Scan node for scan_id
```

Routes:

```text
ready       → build_analysis_plan
not_ready   → fail_analysis
```

---

## 10.3 `build_analysis_plan`

Purpose:

```text
Create scoped analysis tasks for each agent.
```

The plan should be based on deterministic metadata first:

```text
file paths
file extensions
LOC
symbol types
symbol LOC
imports
call expressions
chunk metadata
parse errors
language distribution
```

The LLM can help prioritize, but it should not be the only planner.

---

## 10.4 `dispatch_agent_workers`

Purpose:

```text
Send scoped tasks to matching agent worker nodes.
```

Routing:

```text
security task     → security_agent
performance task  → performance_agent
complexity task   → complexity_agent
duplication task  → duplication_agent
reliability task  → reliability_agent
```

---

## 10.5 Agent Worker Nodes

Agent nodes:

```text
security_agent
performance_agent
complexity_agent
duplication_agent
reliability_agent
```

Each agent should:

```text
1. Receive one scoped task.
2. Retrieve relevant Supabase metadata.
3. Retrieve relevant Qdrant chunks using scan_id filter.
4. Retrieve useful Neo4j relationships using scan_id filter.
5. Build a compact prompt with only relevant context.
6. Call the LLM with a strict output schema.
7. Return raw findings.
```

Each agent should not write findings directly to Supabase.

---

## 10.6 `normalize_findings`

Purpose:

```text
Validate, clean, and standardize all agent outputs.
```

Responsibilities:

```text
validate JSON shape
convert severity labels
clamp confidence between 0 and 1
remove malformed findings
attach scan_id
attach agent name
attach finding fingerprint
normalize file paths
normalize line numbers
```

Severity mapping:

```text
Critical → extreme
Blocker  → extreme
Extreme  → extreme
High     → high
Medium   → medium
Low      → low
Minor    → low
Info     → low
```

Internal severity values:

```text
extreme
high
medium
low
```

---

## 10.7 `deduplicate_findings`

Purpose:

```text
Merge duplicate or overlapping findings.
```

Fingerprint input:

```text
scan_id
agent_name
file_path
symbol_name
start_line
end_line
normalized_title
```

Cross-agent merge rule:

```text
If two findings refer to the same file, same symbol, similar lines, and similar root cause, merge them.
```

Example:

```text
Complexity Agent:
  Large function with too many branches.

Reliability Agent:
  Function has many edge cases but limited error handling.

Merged finding:
  primary_agent = complexity
  related_agents = ["reliability"]
```

---

## 10.8 `rank_findings`

Purpose:

```text
Order findings by severity and importance.
```

Ranking order:

```text
1. extreme
2. high
3. medium
4. low
```

Tie-breakers:

```text
1. Confidence score
2. Number of evidence items
3. Number of related agents
4. Whether the affected symbol is central in the Neo4j call graph
5. Whether the file is high-risk, such as auth, config, database, network, or payments
```

---

## 10.9 `persist_findings`

Purpose:

```text
Write final deduplicated findings to Supabase.
```

Only this node writes findings.

Reason:

```text
Central persistence avoids duplicate rows.
Central persistence makes retries safer.
Central persistence ensures schema validation happens once.
```

---

## 10.10 `mark_scan_analyzed`

Purpose:

```text
Mark Phase 3 complete.
```

Updates:

```text
scans.status = analyzed
scans.updated_at = now()
scan_events.event_type = analysis_completed
```

---

## 11. Agent Responsibilities

## 11.1 Security Agent

Finds:

```text
hardcoded secrets
API keys and tokens
unsafe eval / exec
command injection
SQL injection
unsafe deserialization
missing input validation
weak authentication checks
weak authorization checks
insecure file upload patterns
```

Main tools:

```text
Qdrant:
  retrieve security-sensitive chunks.

Neo4j:
  inspect call chains around risky functions.

Supabase:
  load file, symbol, and dependency metadata.
```

Example retrieval hints:

```text
password
token
secret
api_key
private_key
eval
exec
subprocess
os.system
shell=True
raw SQL
query string interpolation
deserialize
pickle
jwt
auth
login
middleware
```

---

## 11.2 Performance Agent

Finds:

```text
nested loops over large data
repeated database calls
N+1 query patterns
repeated network calls
large memory allocations
blocking IO
unbounded processing
inefficient algorithms
expensive repeated computation
```

Main tools:

```text
Qdrant:
  retrieve performance-sensitive chunks.

Neo4j:
  inspect call graph and repeated call relationships.

Supabase:
  load LOC, symbol size, and file metadata.
```

---

## 11.3 Complexity Agent

Finds:

```text
large functions
large classes
deep nesting
too many branches
too many parameters
unclear control flow
god objects
mixed responsibilities
high cyclomatic complexity candidates
```

This agent should use deterministic metrics first.

Useful metadata from Phase 2:

```text
lines_of_code
symbol_type
function_count
method_count
class_count
branch_count
loop_count
nesting_depth
parameter_count
```

The LLM should explain and suggest improvements, but deterministic metrics should identify candidates.

---

## 11.4 Duplication Agent

Finds:

```text
near-identical functions
repeated validation logic
copy-pasted API handlers
duplicated utilities
repeated transformation logic
repeated error handling blocks
```

Main tools:

```text
Qdrant:
  find semantically similar chunks scoped by scan_id.

Supabase:
  load chunk and symbol metadata.

Neo4j:
  inspect related symbols and shared dependencies.
```

Important rule:

```text
Do not compare every file with every other file manually.
Use Qdrant similarity search to identify duplication candidates first.
```

---

## 11.5 Reliability / Fault Tolerance Agent

Finds:

```text
missing exception handling
missing retries
missing timeouts
unsafe external API calls
unsafe file IO
resource leaks
missing transaction rollback
single points of failure
poor fallback behavior
silent failure patterns
```

Main tools:

```text
Qdrant:
  retrieve IO, network, database, and exception-handling chunks.

Neo4j:
  inspect graph context around external calls and data flow.

Supabase:
  load symbol and file metadata.
```

---

## 12. Agent Tool Contracts

## 12.1 Supabase Metadata Tool

Purpose:

```text
Retrieve permanent scan, file, symbol, chunk, and finding metadata.
```

Example methods:

```python
get_scan(scan_id: str)
get_repo_stats(scan_id: str)
list_files(scan_id: str, filters: dict)
list_symbols(scan_id: str, filters: dict)
list_chunks(scan_id: str, filters: dict)
get_chunk_metadata(chunk_ids: list[str])
get_symbol_context(symbol_ids: list[str])
```

Rules:

```text
Always filter by scan_id.
Never return all rows without pagination.
Return metadata first, not full raw code unless specifically required.
```

---

## 12.2 Qdrant Retrieval Tool

Purpose:

```text
Retrieve semantically relevant code chunks.
```

Example methods:

```python
search_code_chunks(
    scan_id: str,
    query: str,
    limit: int = 10,
    file_ids: list[str] | None = None,
    symbol_ids: list[str] | None = None,
    chunk_types: list[str] | None = None,
)

find_similar_chunks(
    scan_id: str,
    chunk_id: str,
    limit: int = 10,
)
```

Rules:

```text
Every Qdrant query must include scan_id filter.
Return chunk_id, file_path, symbol_name, start_line, end_line, content, and score.
Do not search across all scans globally.
```

---

## 12.3 Neo4j Graph Query Tool

Purpose:

```text
Retrieve structural code relationships.
```

Example methods:

```python
get_symbol_neighbors(scan_id: str, symbol_id: str, depth: int = 1)
get_file_imports(scan_id: str, file_id: str)
get_call_chain(scan_id: str, symbol_id: str, depth: int = 2)
get_central_symbols(scan_id: str, limit: int = 20)
find_external_call_sites(scan_id: str)
find_database_call_sites(scan_id: str)
```

Rules:

```text
Every Neo4j query must be scoped by scan_id.
Keep graph query depth small in the first version.
Do not require perfect call resolution in v1.
```

---

## 13. LangGraph State

Recommended shared state:

```python
from typing import Annotated, Literal, TypedDict
import operator


Severity = Literal["extreme", "high", "medium", "low"]
AgentName = Literal[
    "security",
    "performance",
    "complexity",
    "duplication",
    "reliability",
]


class RepoContext(TypedDict):
    scan_id: str
    repo_full_name: str
    branch: str
    commit_sha: str
    total_files: int
    total_symbols: int
    total_chunks: int
    qdrant_collection: str
    neo4j_database: str


class AnalysisTask(TypedDict):
    task_id: str
    agent: AgentName
    objective: str
    target_file_ids: list[str]
    target_chunk_ids: list[str]
    target_symbol_ids: list[str]
    priority: int


class RawFinding(TypedDict):
    agent: AgentName
    file_path: str
    symbol_name: str | None
    start_line: int | None
    end_line: int | None
    title: str
    description: str
    severity: Severity
    confidence: float
    evidence: list[str]
    recommendation: str


class NormalizedFinding(TypedDict):
    finding_id: str
    scan_id: str
    agent: AgentName
    file_path: str
    symbol_name: str | None
    start_line: int | None
    end_line: int | None
    title: str
    description: str
    severity: Severity
    confidence: float
    evidence: list[str]
    recommendation: str
    fingerprint: str
    related_agents: list[str]


class AnalysisState(TypedDict):
    scan_id: str
    repo_context: RepoContext | None
    analysis_tasks: list[AnalysisTask]
    raw_findings: Annotated[list[RawFinding], operator.add]
    normalized_findings: list[NormalizedFinding]
    deduped_findings: list[NormalizedFinding]
    errors: Annotated[list[str], operator.add]
    status: str
```

Important:

```text
raw_findings uses operator.add because multiple agent workers append results into shared state.
```

---

## 14. Strict Finding Schema

Every agent should return a JSON array.

Example:

```json
[
  {
    "agent": "security",
    "file_path": "src/auth/login.py",
    "symbol_name": "login_user",
    "start_line": 42,
    "end_line": 71,
    "title": "Hardcoded token used during login validation",
    "description": "The function appears to compare user input against a hardcoded token-like value.",
    "severity": "high",
    "confidence": 0.82,
    "evidence": [
      "Token-like string appears inside login_user",
      "The value is used in authentication control flow"
    ],
    "recommendation": "Move secrets to environment variables or a managed secrets store. Compare credentials using a secure authentication provider."
  }
]
```

No extra text should be returned outside the JSON array.

---

## 15. LangGraph Pseudocode

```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from app.workflows.analysis.state import AnalysisState
from app.workflows.analysis.nodes.load_scan_context import load_scan_context
from app.workflows.analysis.nodes.validate_analysis_ready import validate_analysis_ready
from app.workflows.analysis.nodes.build_analysis_plan import build_analysis_plan
from app.workflows.analysis.nodes.normalize_findings import normalize_findings
from app.workflows.analysis.nodes.deduplicate_findings import deduplicate_findings
from app.workflows.analysis.nodes.rank_findings import rank_findings
from app.workflows.analysis.nodes.persist_findings import persist_findings
from app.workflows.analysis.nodes.mark_scan_analyzed import mark_scan_analyzed

from app.workflows.analysis.agents.security_agent import security_agent
from app.workflows.analysis.agents.performance_agent import performance_agent
from app.workflows.analysis.agents.complexity_agent import complexity_agent
from app.workflows.analysis.agents.duplication_agent import duplication_agent
from app.workflows.analysis.agents.reliability_agent import reliability_agent


def route_after_validation(state: AnalysisState):
    if state["status"] == "ready_for_analysis":
        return "build_analysis_plan"
    return "fail_analysis"


def dispatch_agent_workers(state: AnalysisState):
    sends = []

    for task in state["analysis_tasks"]:
        worker_input = {
            "scan_id": state["scan_id"],
            "repo_context": state["repo_context"],
            "task": task,
        }

        if task["agent"] == "security":
            sends.append(Send("security_agent", worker_input))

        elif task["agent"] == "performance":
            sends.append(Send("performance_agent", worker_input))

        elif task["agent"] == "complexity":
            sends.append(Send("complexity_agent", worker_input))

        elif task["agent"] == "duplication":
            sends.append(Send("duplication_agent", worker_input))

        elif task["agent"] == "reliability":
            sends.append(Send("reliability_agent", worker_input))

    return sends


def build_analysis_graph():
    graph = StateGraph(AnalysisState)

    graph.add_node("load_scan_context", load_scan_context)
    graph.add_node("validate_analysis_ready", validate_analysis_ready)
    graph.add_node("build_analysis_plan", build_analysis_plan)

    graph.add_node("security_agent", security_agent)
    graph.add_node("performance_agent", performance_agent)
    graph.add_node("complexity_agent", complexity_agent)
    graph.add_node("duplication_agent", duplication_agent)
    graph.add_node("reliability_agent", reliability_agent)

    graph.add_node("normalize_findings", normalize_findings)
    graph.add_node("deduplicate_findings", deduplicate_findings)
    graph.add_node("rank_findings", rank_findings)
    graph.add_node("persist_findings", persist_findings)
    graph.add_node("mark_scan_analyzed", mark_scan_analyzed)

    graph.add_edge(START, "load_scan_context")
    graph.add_edge("load_scan_context", "validate_analysis_ready")

    graph.add_conditional_edges(
        "validate_analysis_ready",
        route_after_validation,
        {
            "build_analysis_plan": "build_analysis_plan",
            "fail_analysis": END,
        },
    )

    graph.add_conditional_edges(
        "build_analysis_plan",
        dispatch_agent_workers,
        [
            "security_agent",
            "performance_agent",
            "complexity_agent",
            "duplication_agent",
            "reliability_agent",
        ],
    )

    graph.add_edge("security_agent", "normalize_findings")
    graph.add_edge("performance_agent", "normalize_findings")
    graph.add_edge("complexity_agent", "normalize_findings")
    graph.add_edge("duplication_agent", "normalize_findings")
    graph.add_edge("reliability_agent", "normalize_findings")

    graph.add_edge("normalize_findings", "deduplicate_findings")
    graph.add_edge("deduplicate_findings", "rank_findings")
    graph.add_edge("rank_findings", "persist_findings")
    graph.add_edge("persist_findings", "mark_scan_analyzed")
    graph.add_edge("mark_scan_analyzed", END)

    return graph.compile()
```

---

## 16. Supabase Tables for Phase 3

## 16.1 `analysis_tasks`

Stores the supervisor-created work plan.

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

Recommended status values:

```text
pending
running
completed
failed
skipped
```

---

## 16.2 `agent_runs`

Tracks each agent execution.

```sql
create table agent_runs (
  id uuid primary key default gen_random_uuid(),

  scan_id uuid not null references scans(id) on delete cascade,
  analysis_task_id uuid references analysis_tasks(id) on delete set null,

  agent_name text not null,
  status text not null,

  model_provider text,
  model_name text,

  input_task jsonb,
  output_summary jsonb,

  prompt_tokens integer,
  completion_tokens integer,
  total_tokens integer,

  error_message text,

  started_at timestamptz not null default now(),
  completed_at timestamptz
);
```

Recommended status values:

```text
running
completed
failed
timeout
rate_limited
```

---

## 16.3 `findings`

Stores normalized and deduplicated findings.

```sql
create table findings (
  id uuid primary key default gen_random_uuid(),

  scan_id uuid not null references scans(id) on delete cascade,

  primary_agent text not null,
  related_agents jsonb not null default '[]',

  title text not null,
  description text not null,
  severity text not null,
  confidence numeric,

  file_path text,
  file_id uuid,
  symbol_name text,
  symbol_id uuid,
  start_line integer,
  end_line integer,

  evidence jsonb not null default '[]',
  recommendation text,

  fingerprint text not null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

Recommended unique index:

```sql
create unique index findings_scan_fingerprint_idx
on findings(scan_id, fingerprint);
```

Recommended severity constraint:

```sql
alter table findings
add constraint findings_severity_check
check (severity in ('extreme', 'high', 'medium', 'low'));
```

---

## 16.4 `scan_events`

Use the existing `scan_events` table from Phase 1.

Recommended Phase 3 events:

```text
analysis_queued
analysis_started
analysis_context_loaded
analysis_plan_created
agent_started
agent_completed
agent_failed
findings_normalized
findings_deduplicated
findings_ranked
findings_stored
analysis_completed
analysis_failed
```

---

## 17. Scan Status Values Used in Phase 3

Phase 3 starts from:

```text
parsed
```

Recommended Phase 3 statuses:

```text
analysis_queued
analyzing
planning_analysis
running_agents
normalizing_findings
storing_findings
analyzed
analysis_failed
```

Minimum v1 statuses:

```text
parsed
analyzing
analyzed
analysis_failed
```

Recommended final Phase 3 success status:

```text
analyzed
```

Phase 4 starts when:

```text
scan.status == analyzed
```

---

## 18. Backend Folder Structure

Recommended structure:

```text
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

    workers/
      analysis_worker.py

    services/
      scan_status_service.py
      scan_event_service.py
```

---

## 19. Environment Variables

```env
# Redis
REDIS_URL=
ANALYSIS_QUEUE_NAME=analysis_queue

# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# Qdrant Cloud
QDRANT_URL=
QDRANT_API_KEY=
QDRANT_COLLECTION_CODE_CHUNKS=code_chunks

# Neo4j Aura
NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=
NEO4J_DATABASE=neo4j

# Agent LLM
AGENT_LLM_PROVIDER=deepseek
AGENT_LLM_MODEL=deepseek-reasoner
DEEPSEEK_API_KEY=

# LangGraph
LANGGRAPH_RECURSION_LIMIT=50
AGENT_MAX_RETRIES=2
AGENT_TIMEOUT_SECONDS=120

# Analysis
MAX_AGENT_CONTEXT_CHUNKS=12
MAX_FINDINGS_PER_AGENT=20
```

---

## 20. Error Codes

Recommended Phase 3 error codes:

```text
ANALYSIS_JOB_INVALID
SCAN_NOT_FOUND
SCAN_NOT_PARSED
SCAN_ALREADY_ANALYZED
SCAN_FAILED_BEFORE_ANALYSIS
MISSING_SCAN_FILES
MISSING_CODE_CHUNKS
MISSING_QDRANT_POINTS
MISSING_NEO4J_GRAPH
ANALYSIS_PLAN_FAILED
AGENT_TIMEOUT
AGENT_RATE_LIMITED
AGENT_INVALID_JSON
FINDING_NORMALIZATION_FAILED
FINDING_PERSISTENCE_FAILED
ANALYSIS_INTERNAL_ERROR
```

---

## 21. Retry and Idempotency Strategy

Phase 3 should be safe to retry.

### Idempotent Writes

Use deterministic fingerprints for findings.

```text
scan_id
primary_agent
file_path
symbol_name
start_line
end_line
normalized_title
```

Use unique index:

```text
findings(scan_id, fingerprint)
```

Use upsert behavior when persisting findings.

### Retryable Stages

```text
analysis_queued
analyzing
planning_analysis
running_agents
normalizing_findings
storing_findings
```

### Non-Retryable or Manual-Review Failures

```text
scan not found
scan was never parsed
missing Phase 2 storage records
invalid graph namespace
invalid Qdrant collection
unsupported scan status
```

### Agent Retries

Each agent should support:

```text
timeout retry
rate-limit retry
invalid JSON retry with stricter repair prompt
```

Do not retry forever.

Recommended:

```text
AGENT_MAX_RETRIES=2
```

---

## 22. Implementation Order

```text
1. Create Phase 3 Supabase tables:
   - analysis_tasks
   - agent_runs
   - findings

2. Add Phase 3 scan statuses and scan events.

3. Create analysis worker.

4. Add analysis queue or direct Phase 2 → Phase 3 handoff.

5. Implement lightweight scan context loader.

6. Implement readiness validation:
   - Supabase records exist
   - Qdrant points exist
   - Neo4j graph exists

7. Implement Supabase metadata tool.

8. Implement Qdrant retrieval tool with mandatory scan_id filtering.

9. Implement Neo4j graph query tool with mandatory scan_id filtering.

10. Define strict finding schema.

11. Implement supervisor planning node.

12. Implement Security Agent.

13. Implement Complexity Agent.

14. Implement Reliability Agent.

15. Implement Performance Agent.

16. Implement Duplication Agent.

17. Implement normalize_findings node.

18. Implement deduplicate_findings node.

19. Implement rank_findings node.

20. Implement persist_findings node.

21. Implement mark_scan_analyzed node.

22. Add agent run tracking.

23. Add error handling and retry behavior.

24. Test on a small repository.

25. Test on a medium repository.

26. Confirm final status changes to analyzed.

27. Confirm Phase 4 can start from analyzed status.
```

---

## 23. Final Phase 3 Contract

Phase 3 is complete when this works end to end:

```text
Analysis worker receives scan_id
        ↓
Loads lightweight scan context from Supabase
        ↓
Confirms scan.status == parsed
        ↓
Confirms Supabase, Qdrant, and Neo4j data exist
        ↓
Runs LangGraph supervisor-worker workflow
        ↓
Supervisor creates scoped tasks
        ↓
Five agents run in parallel with scoped context
        ↓
Agents use Supabase, Qdrant, and Neo4j tools
        ↓
Agents return strict JSON findings
        ↓
Findings are normalized
        ↓
Overlapping findings are deduplicated
        ↓
Findings are ranked:
  extreme → high → medium → low
        ↓
Findings are persisted in Supabase
        ↓
scan.status = analyzed
```

Phase 3 should stop at `analyzed`.

Phase 4 begins after findings have been stored and the scan is ready for final report generation and chatbot interaction.

---

## 24. Design References

These references support the architectural choices used in this phase.

- LangGraph workflows and agents documentation: https://docs.langchain.com/oss/python/langgraph/workflows-agents
- LangGraph thinking guide: https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph
- SonarQube metrics definitions: https://docs.sonarsource.com/sonarqube-server/user-guide/code-metrics/metrics-definition
- Snyk Code documentation: https://docs.snyk.io/scan-with-snyk/snyk-code
- Qodo code review documentation: https://docs.qodo.ai/code-review
