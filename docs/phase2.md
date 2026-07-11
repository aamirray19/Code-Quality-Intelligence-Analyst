# Phase 2 — Repository Cloning, Parsing, Chunking, and Index Storage

## 1. Goal

Phase 2 is responsible for consuming the queued scan job from Redis, cloning the validated GitHub repository, discovering useful source files, parsing supported files with Tree-sitter, extracting code structure, creating code chunks, and storing the prepared repository data in Supabase, Qdrant Cloud, and Neo4j Aura.

Phase 2 prepares the repository for later analysis.

Phase 2 does **not** run code-quality agents, execute LangGraph workflows, generate the final report, or answer chatbot questions. Those responsibilities start from Phase 3 and Phase 4.

---

## 2. Phase 2 Scope

### Included in Phase 2

- Consume the Redis job created in Phase 1.
- Load scan metadata from Supabase using `scan_id`.
- Update scan status throughout the worker lifecycle.
- Clone the GitHub repository into a temporary workspace.
- Resolve the selected branch and exact commit SHA.
- Walk the repository file tree.
- Apply directory, file, extension, binary, and size filters.
- Store discovered file metadata in Supabase.
- Parse supported source files with Tree-sitter.
- Extract symbols such as modules, classes, functions, methods, imports, and basic call expressions.
- Store parsed metadata in Supabase.
- Create AST-aware code chunks.
- Store chunk metadata in Supabase.
- Generate embeddings for chunks.
- Store embedded chunks in Qdrant Cloud.
- Create repository code graph in Neo4j Aura.
- Cleanup the temporary workspace.
- Mark the scan as `parsed` when Phase 2 completes.

### Not Included in Phase 2

- Running Security, Performance, Complexity, Duplication, or Reliability agents.
- Running the LangGraph supervisor-worker workflow.
- Ranking issues by severity.
- Generating the final report.
- Serving RAG chatbot answers.
- Frontend report rendering.
- Fix suggestion generation.

---

## 3. Final Phase 2 Worker Flow

```text
Redis job received by worker
        ↓
Worker loads scan metadata from Supabase
        ↓
Update scan status = cloning
        ↓
Clone GitHub repo into temporary workspace
        ↓
Resolve branch + commit SHA
        ↓
Update scan status = discovering_files
        ↓
Walk repository files
        ↓
Apply file filters
        ↓
Store file metadata in Supabase
        ↓
Update scan status = parsing
        ↓
Parse supported files with Tree-sitter
        ↓
Extract symbols
        ↓
Store parsed metadata in Supabase
        ↓
Update scan status = chunking
        ↓
Create code chunks
        ↓
Store chunk metadata in Supabase
        ↓
Update scan status = storing_indexes
        ↓
Run in parallel:
  ├── Generate embeddings + store chunks in Qdrant
  └── Create code graph in Neo4j
        ↓
Cleanup temporary repo directory
        ↓
Update scan status = parsed
```

---

## 4. Phase 2 Architecture

```text
Redis Cloud
    ↓
Render Worker
    ↓
Temporary GitHub Repo Workspace
    ↓
File Discovery Service
    ↓
Tree-sitter Parser Service
    ↓
Symbol Extraction Service
    ↓
Chunk Builder Service
    ↓
Storage Layer
    ├── Supabase
    ├── Qdrant Cloud
    └── Neo4j Aura
```

### Storage Responsibility

```text
Supabase:
  Stores permanent scan metadata, file metadata, symbol metadata, chunk metadata, parse errors, and repo statistics.

Qdrant Cloud:
  Stores vector embeddings for code chunks and metadata needed for filtered semantic retrieval.

Neo4j Aura:
  Stores structural code graph nodes and relationships.
```

---

## 5. Worker Flow Details

## 5.1 Redis Job Consumption

Phase 2 starts when the worker receives a job from Redis.

### Queue Name

```text
repo_scan_queue
```

### Expected Redis Job Payload

```json
{
  "job_type": "repo_scan",
  "scan_id": "9f3c7c5a-7b90-4a6f-b56e-3bfa02d8f091",
  "repo": {
    "owner": "owner",
    "name": "repo",
    "full_name": "owner/repo",
    "branch": "main",
    "default_branch": "main",
    "clone_url": "https://github.com/owner/repo.git",
    "html_url": "https://github.com/owner/repo",
    "size_kb": 1277
  },
  "created_at": "2026-07-01T13:30:00Z"
}
```

### First Worker Actions

```text
1. Read scan_id from job payload.
2. Load scan row from Supabase.
3. Verify scan exists.
4. Verify scan status is queued or retryable.
5. Mark status = cloning.
6. Create scan event = worker_started.
```

---

## 5.2 Clone Repository

The worker clones the repository into an isolated temporary workspace.

### Workspace Path

```text
/tmp/cqia/scans/{scan_id}/repo
```

### Clone Command

```bash
git clone --depth 1 --branch <branch> <clone_url> <workspace>
```

### Metadata To Capture

```text
branch
commit_sha
clone_url
repo_full_name
clone_started_at
clone_completed_at
```

### Failure Behavior

If cloning fails:

```text
status = failed
error_code = CLONE_FAILED
error_message = clone error summary
```

The worker should cleanup any partially created workspace.

---

## 5.3 Discover Files

After cloning, the worker recursively walks the repository and decides which files should be included.

### Ignored Directories

```text
.git
node_modules
venv
env
.venv
__pycache__
dist
build
.next
.cache
coverage
target
vendor
.idea
.vscode
```

### Ignored File Types

```text
images
videos
audio files
archives
PDFs
Office documents
font files
binary files
lock files
large generated files
log files
```

### Recommended Initial Supported Extensions

```text
.py
.js
.jsx
.ts
.tsx
```

### Optional Later Supported Extensions

```text
.java
.go
.rs
.cpp
.c
.cs
.rb
.php
```

### File Metadata To Capture

```text
scan_id
relative_path
absolute_temp_path
file_name
extension
language
size_bytes
line_count
content_hash
is_supported
skip_reason
```

---

## 5.4 Store File Metadata in Supabase

Every discovered source file should have a record in `scan_files`.

Recommended behavior:

```text
Accepted supported file:
  parse_status = pending

Accepted unsupported text file:
  parse_status = unsupported

Skipped file:
  parse_status = skipped
  skip_reason = reason
```

This makes the scan progress auditable and allows the frontend to show repository statistics even before parsing finishes.

---

## 5.5 Parse Files with Tree-sitter

The worker parses supported files using the correct Tree-sitter grammar.

### Parsing Flow

```text
For each supported file:
  read source content
  select parser by language
  parse with Tree-sitter
  if parse succeeds:
    extract syntax tree
    extract symbols
    mark file parse_status = parsed
  if parse fails:
    mark file parse_status = failed
    store parse error
    continue with next file
```

### Important Rule

A single file parse failure must **not** fail the entire scan.

Correct:

```text
File parse failed
        ↓
Store parse error
        ↓
Continue parsing remaining files
```

Incorrect:

```text
File parse failed
        ↓
Fail entire scan
```

---

## 5.6 Extract Symbols

Symbols are structured code entities extracted from parsed files.

### Minimum Symbols To Extract

```text
module
class
function
method
import
export
```

### Optional Symbols To Extract Later

```text
variable
constant
interface
type
call_expression
route_handler
api_endpoint
database_query
```

### Symbol Metadata

```text
scan_id
file_id
symbol_type
symbol_name
qualified_name
parent_symbol_id
start_line
end_line
start_byte
end_byte
raw_code
language
```

### Example Symbols

```text
File: app/services/repo_validation.py
  Function: validate_repository
  Function: check_repo_size
  Class: GitHubRepoValidator
  Method: GitHubRepoValidator.validate
```

---

## 5.7 Store Parsed Metadata in Supabase

After symbol extraction, store parsed metadata in Supabase.

Recommended tables:

```text
code_symbols
parse_errors
```

Supabase should store structured metadata and raw text snippets when useful.

Supabase should **not** store vector embeddings.

Embeddings belong in Qdrant.

---

## 5.8 Create Code Chunks

Chunks are the retrieval and analysis units used later by Qdrant, LangGraph agents, and the RAG chatbot.

### Chunking Priority

```text
1. Function-level chunks
2. Method-level chunks
3. Class-level chunks
4. File-level fallback chunks
5. Line-based fallback chunks for unparsed files
```

### Chunk Types

```text
function_chunk
method_chunk
class_chunk
file_chunk
import_chunk
fallback_chunk
```

### Chunk Metadata

```text
scan_id
file_id
symbol_id
chunk_type
language
file_path
symbol_name
start_line
end_line
content
content_hash
token_count
```

### Example Chunk

```json
{
  "scan_id": "9f3c7c5a-7b90-4a6f-b56e-3bfa02d8f091",
  "file_id": "file_uuid",
  "symbol_id": "symbol_uuid",
  "chunk_type": "function_chunk",
  "language": "python",
  "file_path": "src/services/github_validator.py",
  "symbol_name": "validate_repository",
  "start_line": 25,
  "end_line": 88,
  "content": "def validate_repository(...): ..."
}
```

---

## 5.9 Store Chunk Metadata in Supabase

After chunks are created, store chunk metadata in Supabase.

Recommended table:

```text
code_chunks
```

The chunk row in Supabase is the permanent metadata record.

The matching Qdrant point should reference the Supabase `chunk_id`.

---

## 5.10 Store Indexes in Parallel

Once parsing and chunking are complete, Phase 2 stores two indexes in parallel.

```text
storing_indexes
  ├── Qdrant vector index
  └── Neo4j code graph index
```

This should run in parallel because Qdrant and Neo4j do not depend on each other once Supabase metadata is ready.

---

## 5.11 Generate Embeddings and Store in Qdrant

For every code chunk:

```text
chunk content
        ↓
embedding model
        ↓
vector
        ↓
Qdrant upsert
```

### Qdrant Collection

```text
code_chunks
```

### Qdrant Point ID

Use the Supabase `chunk_id` as the Qdrant point ID when possible.

### Qdrant Payload

```json
{
  "scan_id": "9f3c7c5a-7b90-4a6f-b56e-3bfa02d8f091",
  "file_id": "file_uuid",
  "symbol_id": "symbol_uuid",
  "chunk_id": "chunk_uuid",
  "repo_full_name": "owner/repo",
  "branch": "main",
  "commit_sha": "abc123",
  "file_path": "src/services/github_validator.py",
  "language": "python",
  "chunk_type": "function_chunk",
  "symbol_name": "validate_repository",
  "start_line": 25,
  "end_line": 88
}
```

### Important Retrieval Rule

Every RAG query must be scoped by `scan_id`.

Correct:

```text
Search Qdrant where scan_id = current_scan_id
```

Incorrect:

```text
Search all chunks globally
```

---

## 5.12 Create Code Graph in Neo4j Aura

Neo4j stores structural relationships in the scanned repository.

### Minimum Nodes

```text
Repository
Scan
File
Symbol
Import
CallExpression
```

### Optional Nodes Later

```text
Class
Function
Method
Package
Directory
APIEndpoint
DatabaseQuery
EnvironmentVariable
```

### Minimum Relationships

```text
(:Repository)-[:HAS_SCAN]->(:Scan)
(:Scan)-[:HAS_FILE]->(:File)
(:File)-[:DEFINES]->(:Symbol)
(:Symbol)-[:CONTAINS]->(:Symbol)
(:File)-[:IMPORTS]->(:Import)
(:Symbol)-[:CALLS]->(:CallExpression)
```

### Better Typed Relationships Later

```text
(:Class)-[:HAS_METHOD]->(:Method)
(:Function)-[:CALLS]->(:Function)
(:File)-[:IMPORTS_FILE]->(:File)
(:APIEndpoint)-[:HANDLED_BY]->(:Function)
```

### Important Rule

Start with a simple graph first.

Do not try to perfectly resolve every function call in the first implementation.

Recommended first version:

```text
Extract call expression names
Store unresolved call nodes
Resolve exact call targets later
```

---

## 5.13 Cleanup Temporary Workspace

After Supabase, Qdrant, and Neo4j storage complete successfully, delete the temporary repository directory.

```text
/tmp/cqia/scans/{scan_id}/repo
```

Cleanup should also run on failure when possible.

---

## 5.14 Mark Phase 2 Complete

When all Phase 2 work finishes:

```text
status = parsed
```

This means the repository is ready for Phase 3.

Phase 3 should only start when:

```text
scan.status == parsed
```

---

## 6. API Contracts

Phase 2 is mostly a background worker phase. It does not require a new public endpoint to start the work because the Redis job starts it.

However, the frontend needs to track progress using existing or extended scan APIs.

---

## 6.1 `GET /scans/{scan_id}`

Returns current scan status and high-level progress.

### Request

```http
GET /scans/{scan_id}
```

### Successful Response

```json
{
  "scan_id": "9f3c7c5a-7b90-4a6f-b56e-3bfa02d8f091",
  "status": "parsing",
  "phase": "phase_2",
  "repo": {
    "owner": "owner",
    "name": "repo",
    "full_name": "owner/repo",
    "branch": "main",
    "commit_sha": "abc123",
    "html_url": "https://github.com/owner/repo"
  },
  "progress": {
    "files_discovered": 120,
    "files_indexed": 83,
    "files_skipped": 37,
    "symbols_extracted": 410,
    "chunks_created": 390
  },
  "created_at": "2026-07-01T13:30:00Z",
  "updated_at": "2026-07-01T13:35:00Z",
  "error_message": null
}
```

---

## 6.2 `GET /scans/{scan_id}/files`

Returns discovered file inventory for a scan.

This is useful for debugging and for showing what was indexed.

### Request

```http
GET /scans/{scan_id}/files
```

### Query Parameters

```text
status=parsed|pending|failed|skipped|unsupported
language=python|javascript|typescript
limit=100
offset=0
```

### Successful Response

```json
{
  "scan_id": "9f3c7c5a-7b90-4a6f-b56e-3bfa02d8f091",
  "items": [
    {
      "file_id": "file_uuid",
      "relative_path": "src/services/github_validator.py",
      "language": "python",
      "extension": ".py",
      "size_bytes": 4210,
      "line_count": 132,
      "parse_status": "parsed",
      "skip_reason": null
    }
  ],
  "limit": 100,
  "offset": 0,
  "total": 1
}
```

---

## 6.3 `GET /scans/{scan_id}/events`

Returns status events for progress tracking and debugging.

### Request

```http
GET /scans/{scan_id}/events
```

### Successful Response

```json
{
  "scan_id": "9f3c7c5a-7b90-4a6f-b56e-3bfa02d8f091",
  "events": [
    {
      "event_type": "clone_started",
      "message": "Repository clone started.",
      "metadata": {},
      "created_at": "2026-07-01T13:31:00Z"
    },
    {
      "event_type": "parsing_started",
      "message": "Tree-sitter parsing started.",
      "metadata": {
        "supported_files": 83
      },
      "created_at": "2026-07-01T13:32:00Z"
    }
  ]
}
```

---

## 6.4 Internal Worker Contract

The worker entrypoint should expose one main function.

```python
def process_repo_scan(job_payload: RepoScanJob) -> None:
    ...
```

This function is called by RQ or the selected Redis worker library.

It should not return the final report.

It should update Supabase status and events as it progresses.

---

## 7. Services To Be Made

Recommended backend and worker structure:

```text
backend/
  app/
    workers/
      repo_scan_worker.py
      redis_connection.py
    services/
      scan_service.py
      scan_event_service.py
      repo_clone_service.py
      file_discovery_service.py
      file_filter_service.py
      tree_sitter_parser_service.py
      symbol_extraction_service.py
      chunk_builder_service.py
      embedding_service.py
      qdrant_index_service.py
      neo4j_graph_service.py
      repo_stats_service.py
      workspace_service.py
    schemas/
      jobs.py
      files.py
      symbols.py
      chunks.py
      indexes.py
    db/
      supabase_client.py
      qdrant_client.py
      neo4j_client.py
```

---

## 7.1 `repo_scan_worker.py`

### Responsibility

Main Phase 2 orchestration entrypoint.

### Function

```python
def process_repo_scan(job_payload: RepoScanJob) -> None:
    pass
```

### Responsibilities

```text
1. Load scan metadata.
2. Update scan status.
3. Call clone service.
4. Call file discovery service.
5. Call parser service.
6. Call chunk builder service.
7. Store metadata in Supabase.
8. Run Qdrant and Neo4j indexing in parallel.
9. Cleanup workspace.
10. Mark scan as parsed.
11. Handle failures.
```

---

## 7.2 `workspace_service.py`

### Responsibility

Create and cleanup temporary directories for each scan.

### Functions

```python
create_workspace(scan_id: UUID) -> Path
```

```python
cleanup_workspace(scan_id: UUID) -> None
```

---

## 7.3 `repo_clone_service.py`

### Responsibility

Clone the GitHub repository and resolve commit metadata.

### Function

```python
clone_repository(repo: RepoJobInfo, workspace: Path) -> ClonedRepository
```

### Output

```python
ClonedRepository(
    scan_id=scan_id,
    repo_path=Path("/tmp/cqia/scans/{scan_id}/repo"),
    branch="main",
    commit_sha="abc123",
)
```

---

## 7.4 `file_filter_service.py`

### Responsibility

Decide whether a file should be included, skipped, or marked unsupported.

### Function

```python
classify_file(path: Path) -> FileClassification
```

### Output

```python
FileClassification(
    include=True,
    is_supported=True,
    language="python",
    skip_reason=None,
)
```

---

## 7.5 `file_discovery_service.py`

### Responsibility

Walk the repository and produce file inventory records.

### Function

```python
discover_files(scan_id: UUID, repo_path: Path) -> list[DiscoveredFile]
```

---

## 7.6 `tree_sitter_parser_service.py`

### Responsibility

Parse supported files using Tree-sitter.

### Function

```python
parse_file(file: ScanFileRecord) -> ParsedFileResult
```

### Should Handle

```text
Python
JavaScript
TypeScript
JSX
TSX
```

---

## 7.7 `symbol_extraction_service.py`

### Responsibility

Extract structured symbols from Tree-sitter parse trees.

### Function

```python
extract_symbols(parsed_file: ParsedFileResult) -> list[CodeSymbol]
```

---

## 7.8 `chunk_builder_service.py`

### Responsibility

Create retrieval and analysis chunks from parsed symbols and fallback file sections.

### Function

```python
build_chunks(file: ScanFileRecord, symbols: list[CodeSymbol]) -> list[CodeChunk]
```

---

## 7.9 `embedding_service.py`

### Responsibility

Generate embeddings for code chunks.

### Function

```python
embed_chunks(chunks: list[CodeChunk]) -> list[EmbeddedChunk]
```

### Initial Recommendation

Use a single embedding provider consistently across the project.

Possible choices:

```text
OpenAI embeddings
Voyage embeddings
BGE code embeddings
Sentence-transformers for local prototype
```

For production cloud deployment, prefer an API-based embedding model to avoid heavy model memory usage on Render.

---

## 7.10 `qdrant_index_service.py`

### Responsibility

Store embedded chunks in Qdrant Cloud.

### Function

```python
upsert_chunks(scan_id: UUID, embedded_chunks: list[EmbeddedChunk]) -> QdrantIndexResult
```

---

## 7.11 `neo4j_graph_service.py`

### Responsibility

Create or update code graph nodes and relationships in Neo4j Aura.

### Function

```python
upsert_code_graph(scan: ScanRecord, files: list[ScanFileRecord], symbols: list[CodeSymbol]) -> Neo4jIndexResult
```

---

## 7.12 `repo_stats_service.py`

### Responsibility

Compute repository statistics after discovery, parsing, chunking, and indexing.

### Function

```python
compute_repo_stats(scan_id: UUID) -> RepoStats
```

---

## 7.13 `scan_event_service.py`

### Responsibility

Create progress/debug events for the scan.

### Function

```python
create_event(scan_id: UUID, event_type: str, message: str, metadata: dict | None = None) -> None
```

---

## 8. Data Models

## 8.1 Pydantic Worker Models

### `RepoScanJob`

```python
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class RepoJobInfo(BaseModel):
    owner: str
    name: str
    full_name: str
    branch: str
    default_branch: str
    clone_url: str
    html_url: str
    size_kb: int

class RepoScanJob(BaseModel):
    job_type: str
    scan_id: UUID
    repo: RepoJobInfo
    created_at: datetime
```

---

### `ClonedRepository`

```python
from pydantic import BaseModel
from pathlib import Path
from uuid import UUID

class ClonedRepository(BaseModel):
    scan_id: UUID
    repo_path: Path
    branch: str
    commit_sha: str
```

---

### `DiscoveredFile`

```python
from pydantic import BaseModel
from pathlib import Path
from uuid import UUID

class DiscoveredFile(BaseModel):
    scan_id: UUID
    relative_path: str
    absolute_path: Path
    file_name: str
    extension: str
    language: str | None
    size_bytes: int
    line_count: int
    content_hash: str
    is_supported: bool
    parse_status: str
    skip_reason: str | None = None
```

---

### `CodeSymbol`

```python
from pydantic import BaseModel
from uuid import UUID

class CodeSymbol(BaseModel):
    scan_id: UUID
    file_id: UUID
    symbol_type: str
    symbol_name: str
    qualified_name: str | None = None
    parent_symbol_id: UUID | None = None
    start_line: int
    end_line: int
    start_byte: int | None = None
    end_byte: int | None = None
    raw_code: str | None = None
    language: str
```

---

### `CodeChunk`

```python
from pydantic import BaseModel
from uuid import UUID

class CodeChunk(BaseModel):
    scan_id: UUID
    file_id: UUID
    symbol_id: UUID | None = None
    chunk_type: str
    language: str
    file_path: str
    symbol_name: str | None = None
    start_line: int
    end_line: int
    content: str
    content_hash: str
    token_count: int | None = None
```

---

### `EmbeddedChunk`

```python
from pydantic import BaseModel
from uuid import UUID

class EmbeddedChunk(BaseModel):
    chunk_id: UUID
    vector: list[float]
    payload: dict
```

---

## 8.2 Supabase Tables

## `scans` Updates From Phase 2

Phase 2 updates the existing `scans` table created in Phase 1.

Additional columns recommended for Phase 2:

```sql
alter table scans
add column if not exists commit_sha text,
add column if not exists phase text,
add column if not exists started_at timestamptz,
add column if not exists parsed_at timestamptz,
add column if not exists failed_at timestamptz,
add column if not exists error_code text;
```

### Phase 2 Status Values

```text
queued
cloning
discovering_files
parsing
chunking
storing_indexes
parsed
failed
```

---

## `scan_files`

Stores file inventory for each scan.

```sql
create table scan_files (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references scans(id) on delete cascade,

  relative_path text not null,
  file_name text not null,
  extension text,
  language text,

  size_bytes integer not null,
  line_count integer not null,
  content_hash text not null,

  is_supported boolean not null default false,
  parse_status text not null default 'pending',
  skip_reason text,
  parse_error text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique(scan_id, relative_path)
);
```

### `parse_status` Values

```text
pending
parsed
failed
skipped
unsupported
```

---

## `code_symbols`

Stores parsed classes, functions, methods, imports, and other code symbols.

```sql
create table code_symbols (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references scans(id) on delete cascade,
  file_id uuid not null references scan_files(id) on delete cascade,

  symbol_type text not null,
  symbol_name text not null,
  qualified_name text,
  parent_symbol_id uuid references code_symbols(id) on delete set null,

  start_line integer not null,
  end_line integer not null,
  start_byte integer,
  end_byte integer,

  raw_code text,
  language text not null,
  metadata jsonb,

  created_at timestamptz not null default now(),

  unique(scan_id, file_id, symbol_type, symbol_name, start_line, end_line)
);
```

---

## `code_chunks`

Stores metadata for chunks. Embeddings are stored in Qdrant, not Supabase.

```sql
create table code_chunks (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references scans(id) on delete cascade,
  file_id uuid not null references scan_files(id) on delete cascade,
  symbol_id uuid references code_symbols(id) on delete set null,

  chunk_type text not null,
  language text,
  file_path text not null,
  symbol_name text,

  start_line integer not null,
  end_line integer not null,

  content text not null,
  content_hash text not null,
  token_count integer,

  qdrant_point_id text,
  indexed_in_qdrant boolean not null default false,
  indexed_in_neo4j boolean not null default false,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique(scan_id, file_id, chunk_type, content_hash)
);
```

---

## `parse_errors`

Stores parse errors separately for debugging.

```sql
create table parse_errors (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references scans(id) on delete cascade,
  file_id uuid references scan_files(id) on delete cascade,

  error_type text not null,
  error_message text not null,
  metadata jsonb,

  created_at timestamptz not null default now()
);
```

---

## `repo_stats`

Stores summary statistics for the parsed repo.

```sql
create table repo_stats (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references scans(id) on delete cascade unique,

  total_files_found integer not null default 0,
  total_files_indexed integer not null default 0,
  total_files_skipped integer not null default 0,
  total_supported_files integer not null default 0,
  total_lines_of_code integer not null default 0,

  parse_success_count integer not null default 0,
  parse_failed_count integer not null default 0,
  symbol_count integer not null default 0,
  chunk_count integer not null default 0,

  qdrant_points_count integer not null default 0,
  neo4j_nodes_count integer not null default 0,
  neo4j_relationships_count integer not null default 0,

  language_breakdown jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

---

## 8.3 Qdrant Data Model

### Collection Name

```text
code_chunks
```

### Point ID

```text
chunk_id
```

### Vector

```text
Embedding generated from chunk content.
```

### Payload

```json
{
  "scan_id": "9f3c7c5a-7b90-4a6f-b56e-3bfa02d8f091",
  "file_id": "file_uuid",
  "symbol_id": "symbol_uuid",
  "chunk_id": "chunk_uuid",
  "repo_full_name": "owner/repo",
  "branch": "main",
  "commit_sha": "abc123",
  "file_path": "src/services/github_validator.py",
  "language": "python",
  "chunk_type": "function_chunk",
  "symbol_name": "validate_repository",
  "start_line": 25,
  "end_line": 88
}
```

### Required Payload Indexes

Create Qdrant payload indexes for:

```text
scan_id
repo_full_name
language
chunk_type
file_path
```

---

## 8.4 Neo4j Graph Model

### Nodes

```cypher
(:Repository {
  full_name: string,
  html_url: string
})

(:Scan {
  scan_id: string,
  branch: string,
  commit_sha: string
})

(:File {
  file_id: string,
  scan_id: string,
  path: string,
  language: string
})

(:Symbol {
  symbol_id: string,
  scan_id: string,
  name: string,
  qualified_name: string,
  type: string,
  start_line: integer,
  end_line: integer
})

(:Import {
  scan_id: string,
  file_id: string,
  name: string
})

(:CallExpression {
  scan_id: string,
  file_id: string,
  name: string,
  line: integer
})
```

### Relationships

```cypher
(:Repository)-[:HAS_SCAN]->(:Scan)
(:Scan)-[:HAS_FILE]->(:File)
(:File)-[:DEFINES]->(:Symbol)
(:Symbol)-[:CONTAINS]->(:Symbol)
(:File)-[:IMPORTS]->(:Import)
(:Symbol)-[:CALLS]->(:CallExpression)
```

### Uniqueness Constraints

```cypher
create constraint repository_full_name_unique if not exists
for (r:Repository)
require r.full_name is unique;

create constraint scan_id_unique if not exists
for (s:Scan)
require s.scan_id is unique;

create constraint file_id_unique if not exists
for (f:File)
require f.file_id is unique;

create constraint symbol_id_unique if not exists
for (s:Symbol)
require s.symbol_id is unique;
```

---

## 9. Error Codes

Recommended Phase 2 error codes:

```text
SCAN_NOT_FOUND
INVALID_JOB_PAYLOAD
CLONE_FAILED
BRANCH_CHECKOUT_FAILED
WORKSPACE_CREATE_FAILED
FILE_DISCOVERY_FAILED
FILE_READ_FAILED
TREE_SITTER_LANGUAGE_UNSUPPORTED
TREE_SITTER_PARSE_FAILED
SYMBOL_EXTRACTION_FAILED
CHUNKING_FAILED
EMBEDDING_FAILED
QDRANT_UPSERT_FAILED
NEO4J_UPSERT_FAILED
INDEX_STORAGE_FAILED
WORKSPACE_CLEANUP_FAILED
INTERNAL_WORKER_ERROR
```

File-level parse failures should usually create `parse_errors` rows and continue.

Worker-level failures should mark the scan as `failed`.

---

## 10. Environment Variables

```env
# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# Redis Cloud
REDIS_URL=
REDIS_QUEUE_NAME=repo_scan_queue

# GitHub clone behavior
REPO_WORKSPACE_ROOT=/tmp/cqia/scans
GIT_CLONE_TIMEOUT_SECONDS=120
MAX_FILE_SIZE_BYTES=500000
MAX_TOTAL_FILES=5000

# Qdrant Cloud
QDRANT_URL=
QDRANT_API_KEY=
QDRANT_COLLECTION_CODE_CHUNKS=code_chunks

# Neo4j Aura
NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=
NEO4J_DATABASE=neo4j

# Embeddings
# Superseded (see decisions.md 2026-07-10 "embedding model switched to Google
# AI Studio" entry): OpenAI was never actually implemented; the real
# implementation used HuggingFace first, then Google AI Studio's Gemini
# Embedding 2 model.
EMBEDDING_PROVIDER=google
EMBEDDING_MODEL=gemini-embedding-2
GOOGLE_API_KEY_EMBEDDING=

# Worker
WORKER_CONCURRENCY=2
```

---

## 11. Retry and Idempotency Strategy

Phase 2 should be safe to retry.

### Stable IDs

Use deterministic or unique-constrained records based on:

```text
scan_id
relative_path
content_hash
symbol_type
symbol_name
start_line
end_line
chunk_hash
```

### Supabase

Use upserts for:

```text
scan_files
code_symbols
code_chunks
repo_stats
```

### Qdrant

Use `chunk_id` as the point ID so repeated upserts replace the same vector point instead of creating duplicates.

### Neo4j

Use `MERGE` for nodes and relationships.

### Retryable Stages

```text
cloning
storing_indexes
embedding
qdrant upsert
neo4j upsert
```

### Non-Retryable or Manual-Review Failures

```text
invalid job payload
scan not found
repository no longer accessible
unsupported repository size
```

---

## 12. Recommended Phase 2 Implementation Order

```text
1. Create worker process with Redis connection.
2. Implement RepoScanJob schema validation.
3. Implement scan status updates and scan events.
4. Implement workspace creation and cleanup.
5. Implement repo clone service.
6. Implement file filter service.
7. Implement file discovery service.
8. Create scan_files table.
9. Store file metadata in Supabase.
10. Add Tree-sitter parser setup for Python, JavaScript, TypeScript, JSX, and TSX.
11. Implement symbol extraction service.
12. Create code_symbols and parse_errors tables.
13. Store parsed metadata in Supabase.
14. Implement chunk builder service.
15. Create code_chunks table.
16. Store chunk metadata in Supabase.
17. Connect embedding provider.
18. Connect Qdrant Cloud and create code_chunks collection.
19. Upsert chunk embeddings into Qdrant.
20. Connect Neo4j Aura.
21. Create graph constraints.
22. Upsert repository, scan, file, symbol, import, and call-expression graph.
23. Add repo_stats table and compute stats.
24. Add progress APIs for files/events if needed.
25. Mark scan as parsed.
26. Test retry behavior.
```

---

## 13. Final Phase 2 Contract

Phase 2 is complete when this works end to end:

```text
Worker receives Redis job
        ↓
Loads scan metadata from Supabase
        ↓
Clones selected GitHub branch
        ↓
Discovers useful files
        ↓
Stores file inventory in Supabase
        ↓
Parses supported files with Tree-sitter
        ↓
Extracts symbols
        ↓
Stores parsed metadata in Supabase
        ↓
Creates code chunks
        ↓
Stores chunk metadata in Supabase
        ↓
Stores vector index in Qdrant
        ↓
Stores code graph in Neo4j
        ↓
Cleans temporary workspace
        ↓
Marks scan status = parsed
```

Phase 2 should stop at `parsed`.

Phase 3 begins after the repository has been parsed, chunked, and indexed.
