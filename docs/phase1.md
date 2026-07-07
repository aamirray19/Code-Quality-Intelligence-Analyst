# Phase 1 — GitHub Repository Ingestion and Scan Queueing

## 1. Goal

Phase 1 is responsible for accepting a GitHub repository URL from the frontend, validating that the repository can be scanned, creating a scan record, and sending the scan job to Redis for background processing.

Phase 1 does **not** clone, parse, embed, analyze, or generate reports. Those responsibilities start from Phase 2 onward.

---

## 2. Phase 1 Scope

### Included in Phase 1

- Accept GitHub repository URL from the Next.js frontend.
- Validate GitHub URL format.
- Extract repository owner, repository name, and optional branch from the URL.
- Call GitHub metadata API.
- Check whether the repository exists.
- Check whether the repository is public.
- Check whether the repository size is within the configured limit.
- Check whether the requested branch exists if a branch is present in the URL.
- Create a scan record in Supabase only after validation succeeds.
- Push a scan job to Redis Cloud.
- Return `scan_id` to the frontend.
- Allow frontend to poll scan status.

### Not Included in Phase 1

- Cloning the repository.
- Filtering files.
- Tree-sitter parsing.
- Storing code chunks in Qdrant.
- Storing code graph in Neo4j.
- Running LangGraph agents.
- Generating final report.
- RAG chatbot logic.

---

## 3. Final Phase 1 User Flow

```text
User enters GitHub repository URL
        ↓
User presses Enter
        ↓
Frontend calls POST /scans
        ↓
FastAPI validates GitHub URL format
        ↓
FastAPI extracts owner, repo, and optional branch
        ↓
FastAPI calls GitHub metadata API
        ↓
Validation checks run:
  - repo exists
  - repo is public
  - repo is not archived, optional but recommended
  - repo size is within limit
  - branch exists if branch is provided
        ↓
If validation fails:
  return error response to frontend
        ↓
Frontend shows:
  "Repository is invalid. Please enter a valid public GitHub repository URL."
        ↓
If validation passes:
  create scan row in Supabase
  status = queued
        ↓
Push job to Redis Cloud
        ↓
Return scan_id to frontend
        ↓
Frontend polls GET /scans/{scan_id} inline on the same page
        ↓
Worker picks Redis job
        ↓
Phase 2 begins
```

---

## 4. Frontend Flow

### Input Behavior

The user provides a GitHub URL and presses Enter.

There is no separate `Start Scan` button.

The form submit event directly calls:

```http
POST /scans
```

### Frontend UI States

```text
Idle
  ↓
Validating repository...
  ↓
If valid:
  Repository valid. Scan started.
  Polling scan status inline...
  ↓
If invalid:
  Repository is invalid. Please enter a valid public GitHub repository URL.
```

### Frontend Redirect

> **Design decision:** Phase 1 does not navigate to a separate `/scans/{scan_id}` page.
> There is no `/scans/:id` route. Instead, the landing page component
> (`RepoAnalyzer.tsx`) stays on `/`, polls `GET /scans/{scan_id}` on an interval,
> and renders the current status inline (queued, cloning, parsing, ..., completed,
> failed) until a terminal status is reached. A dedicated scan page may be
> introduced in a later phase if needed.

---

## 5. Backend Flow

### Main Backend Flow

```text
POST /scans
        ↓
ScanController receives github_url
        ↓
RepoValidationService validates the repository
        ↓
If invalid:
  raise structured validation error
        ↓
If valid:
  ScanService creates scan row in Supabase
        ↓
QueueService pushes Redis job
        ↓
Return scan_id and queued status
```

### Important Rule

The backend must create a `scan_id` only after repository validation succeeds.

Correct:

```text
Validate repo
        ↓
Create scan_id
        ↓
Queue Redis job
```

Incorrect:

```text
Create scan_id
        ↓
Validate repo
        ↓
Fail validation
```

A scan record should represent an accepted scan job, not an invalid URL attempt.

---

## 6. API Contracts

## 6.1 `POST /scans`

Creates a scan only if the GitHub repository is valid.

### Request

```http
POST /scans
Content-Type: application/json
```

```json
{
  "github_url": "https://github.com/owner/repo"
}
```

### Supported URL Formats

```text
https://github.com/owner/repo
https://github.com/owner/repo/
https://github.com/owner/repo.git
https://github.com/owner/repo/tree/branch-name
```

### Unsupported URL Formats

```text
https://github.com/owner/repo/pull/1
https://github.com/owner/repo/issues/1
https://github.com/owner/repo/blob/main/file.py
https://gitlab.com/owner/repo
https://bitbucket.org/owner/repo
```

### Successful Response

Status code:

```http
201 Created
```

Response body:

```json
{
  "success": true,
  "scan_id": "9f3c7c5a-7b90-4a6f-b56e-3bfa02d8f091",
  "status": "queued",
  "message": "Repository is valid. Scan has been started.",
  "repo": {
    "owner": "owner",
    "name": "repo",
    "full_name": "owner/repo",
    "branch": "main",
    "default_branch": "main",
    "clone_url": "https://github.com/owner/repo.git",
    "html_url": "https://github.com/owner/repo",
    "size_kb": 1277,
    "visibility": "public"
  }
}
```

### Invalid URL Response

Status code:

```http
422 Unprocessable Entity
```

Response body:

```json
{
  "success": false,
  "error_code": "INVALID_GITHUB_URL",
  "message": "Repository is invalid. Please enter a valid GitHub repository URL."
}
```

### Repository Not Found Response

Status code:

```http
404 Not Found
```

Response body:

```json
{
  "success": false,
  "error_code": "REPO_NOT_FOUND",
  "message": "Repository does not exist."
}
```

### Private Repository Response

Status code:

```http
403 Forbidden
```

Response body:

```json
{
  "success": false,
  "error_code": "PRIVATE_REPOSITORY",
  "message": "Only public GitHub repositories are supported."
}
```

### Repository Too Large Response

Status code:

```http
413 Payload Too Large
```

Response body:

```json
{
  "success": false,
  "error_code": "REPO_TOO_LARGE",
  "message": "Repository exceeds the allowed size limit."
}
```

### Branch Not Found Response

Status code:

```http
404 Not Found
```

Response body:

```json
{
  "success": false,
  "error_code": "BRANCH_NOT_FOUND",
  "message": "The specified branch does not exist."
}
```

### Archived Repository Response

Status code:

```http
422 Unprocessable Entity
```

Response body:

```json
{
  "success": false,
  "error_code": "ARCHIVED_REPOSITORY",
  "message": "Archived repositories are not supported."
}
```

---

## 6.2 `GET /scans/{scan_id}`

Returns current scan status.

The frontend uses this endpoint on the scan progress page.

### Request

```http
GET /scans/{scan_id}
```

Example:

```http
GET /scans/9f3c7c5a-7b90-4a6f-b56e-3bfa02d8f091
```

### Successful Response

Status code:

```http
200 OK
```

Response body:

```json
{
  "scan_id": "9f3c7c5a-7b90-4a6f-b56e-3bfa02d8f091",
  "status": "queued",
  "repo": {
    "owner": "owner",
    "name": "repo",
    "full_name": "owner/repo",
    "branch": "main",
    "html_url": "https://github.com/owner/repo"
  },
  "created_at": "2026-07-01T13:30:00Z",
  "updated_at": "2026-07-01T13:30:00Z",
  "error_message": null
}
```

### Not Found Response

Status code:

```http
404 Not Found
```

Response body:

```json
{
  "success": false,
  "error_code": "SCAN_NOT_FOUND",
  "message": "Scan not found."
}
```

---

## 6.3 `GET /health`

Basic backend health check.

### Request

```http
GET /health
```

### Response

```json
{
  "status": "ok",
  "service": "code-quality-intelligence-backend"
}
```

---

## 7. Backend Services To Be Made

Recommended backend structure:

```text
backend/
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
```

---

## 7.1 `github_url_parser.py`

### Responsibility

Parse the GitHub URL and extract clean repository information.

### Input

```text
https://github.com/owner/repo
https://github.com/owner/repo/tree/dev
```

### Output

```python
ParsedGitHubURL(
    owner="owner",
    repo="repo",
    branch="dev",
    normalized_url="https://github.com/owner/repo",
)
```

### Should Handle

- `.git` suffix.
- Trailing slash.
- Branch URL.
- Invalid hosts.
- Missing owner or repo.
- Unsupported GitHub paths such as `/pull`, `/issues`, `/blob`.

---

## 7.2 `github_metadata_service.py`

### Responsibility

Call GitHub APIs to fetch repository and branch metadata.

### Functions

```python
get_repo_metadata(owner: str, repo: str) -> GitHubRepoMetadata
```

```python
branch_exists(owner: str, repo: str, branch: str) -> bool
```

### GitHub Data Needed

```text
repo exists
repo full name
public/private visibility
default branch
repo size
archived status
clone URL
HTML URL
```

### Notes

Use a GitHub token if available to avoid low unauthenticated rate limits.

Environment variable:

```text
GITHUB_TOKEN
```

---

## 7.3 `repo_validation_service.py`

### Responsibility

Apply all repository validation rules before a scan is created.

### Validation Rules

```text
1. URL must be a supported GitHub repository URL.
2. Repository must exist.
3. Repository must be public.
4. Repository should not be archived.
5. Repository size must be within configured limit.
6. If branch is provided, branch must exist.
7. If branch is not provided, use default branch.
```

### Function

```python
validate_repository(github_url: str) -> ValidatedRepository
```

### Output Example

```python
ValidatedRepository(
    owner="owner",
    name="repo",
    full_name="owner/repo",
    branch="main",
    default_branch="main",
    clone_url="https://github.com/owner/repo.git",
    html_url="https://github.com/owner/repo",
    size_kb=1277,
    visibility="public",
)
```

---

## 7.4 `scan_service.py`

### Responsibility

Create and retrieve scan records in Supabase.

### Functions

```python
create_scan(repo: ValidatedRepository, github_url: str) -> ScanRecord
```

```python
get_scan(scan_id: UUID) -> ScanRecord | None
```

```python
update_scan_status(scan_id: UUID, status: str, error_message: str | None = None) -> None
```

### Phase 1 Usage

In Phase 1, this service mainly creates the scan with:

```text
status = queued
```

---

## 7.5 `queue_service.py`

### Responsibility

Push scan jobs to Redis Cloud.

### Function

```python
enqueue_scan(scan: ScanRecord, repo: ValidatedRepository) -> str
```

### Redis Job Payload

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

### Queue Name

```text
repo_scan_queue
```

Recommended library:

```text
RQ or Celery
```

For your current architecture, RQ is simpler.

---

## 8. Data Models

## 8.1 Pydantic API Models

### `CreateScanRequest`

```python
from pydantic import BaseModel, Field

class CreateScanRequest(BaseModel):
    github_url: str = Field(..., min_length=10, max_length=500)
```

---

### `RepoInfoResponse`

```python
from pydantic import BaseModel

class RepoInfoResponse(BaseModel):
    owner: str
    name: str
    full_name: str
    branch: str
    default_branch: str
    clone_url: str
    html_url: str
    size_kb: int
    visibility: str
```

---

### `CreateScanResponse`

```python
from pydantic import BaseModel
from uuid import UUID

class CreateScanResponse(BaseModel):
    success: bool
    scan_id: UUID
    status: str
    message: str
    repo: RepoInfoResponse
```

---

### `ErrorResponse`

```python
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
```

---

### `ScanStatusResponse`

```python
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class ScanStatusRepoResponse(BaseModel):
    owner: str
    name: str
    full_name: str
    branch: str
    html_url: str

class ScanStatusResponse(BaseModel):
    scan_id: UUID
    status: str
    repo: ScanStatusRepoResponse
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
```

---

## 8.2 Internal Service Models

### `ParsedGitHubURL`

```python
from pydantic import BaseModel

class ParsedGitHubURL(BaseModel):
    owner: str
    repo: str
    branch: str | None = None
    normalized_url: str
```

---

### `GitHubRepoMetadata`

```python
from pydantic import BaseModel

class GitHubRepoMetadata(BaseModel):
    owner: str
    name: str
    full_name: str
    default_branch: str
    clone_url: str
    html_url: str
    size_kb: int
    private: bool
    visibility: str
    archived: bool
```

---

### `ValidatedRepository`

```python
from pydantic import BaseModel

class ValidatedRepository(BaseModel):
    owner: str
    name: str
    full_name: str
    branch: str
    default_branch: str
    clone_url: str
    html_url: str
    size_kb: int
    visibility: str
```

---

## 8.3 Supabase Tables

## `scans`

Stores one row per accepted scan.

```sql
create table scans (
  id uuid primary key default gen_random_uuid(),

  github_url text not null,
  repo_owner text not null,
  repo_name text not null,
  repo_full_name text not null,
  branch text not null,
  default_branch text not null,
  clone_url text not null,
  html_url text not null,
  repo_size_kb integer not null,

  status text not null default 'queued',
  error_message text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

### Recommended Status Values

```text
queued
cloning
parsing
storing
analyzing
generating_report
completed
failed
```

Phase 1 creates scans only with:

```text
queued
```

Later phases update the status.

---

## `scan_events`

Optional but recommended for progress tracking and debugging.

```sql
create table scan_events (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references scans(id) on delete cascade,

  event_type text not null,
  message text not null,
  metadata jsonb,

  created_at timestamptz not null default now()
);
```

### Example Events

```text
scan_created
job_queued
worker_started
clone_started
clone_completed
parsing_started
parsing_completed
analysis_started
analysis_completed
scan_failed
scan_completed
```

Phase 1 should create at least:

```text
scan_created
job_queued
```

---

## 8.4 Redis Job Model

Redis stores temporary job messages. The permanent scan state remains in Supabase.

### Queue Name

```text
repo_scan_queue
```

### Job Payload

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

---

## 9. Error Codes

Recommended error codes:

```text
INVALID_GITHUB_URL
UNSUPPORTED_GITHUB_URL
REPO_NOT_FOUND
PRIVATE_REPOSITORY
ARCHIVED_REPOSITORY
REPO_TOO_LARGE
BRANCH_NOT_FOUND
GITHUB_RATE_LIMITED
GITHUB_API_ERROR
SCAN_NOT_FOUND
QUEUE_ERROR
INTERNAL_SERVER_ERROR
```

---

## 10. Environment Variables

```env
# Backend
APP_ENV=development
API_BASE_URL=http://localhost:8000

# GitHub
GITHUB_TOKEN=
MAX_REPO_SIZE_KB=51200

# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# Redis Cloud
REDIS_URL=
REDIS_QUEUE_NAME=repo_scan_queue

# CORS
FRONTEND_URL=http://localhost:8080
```

> **Design decision:** `FRONTEND_URL` defaults to `http://localhost:8080` (not `3000`)
> to match this project's actual Vite dev server port.

Recommended initial size limit:

```text
MAX_REPO_SIZE_KB=51200
```

That equals 50 MB according to GitHub repository metadata size units.

---

## 11. Recommended Phase 1 Implementation Order

```text
1. Create FastAPI project structure
2. Add environment config
3. Implement GitHub URL parser
4. Implement GitHub metadata service
5. Implement repo validation service
6. Create Supabase scans table
7. Create scan service
8. Connect Redis Cloud
9. Implement queue service
10. Build POST /scans
11. Build GET /scans/{scan_id}
12. Connect frontend Enter key submit to POST /scans
13. Poll GET /scans/{scan_id} inline on the landing page and show status
14. Add basic error handling
15. Add scan_events table if progress tracking is needed
```

---

## 12. Final Phase 1 Contract

Phase 1 is complete when this works end to end:

```text
User enters GitHub URL and presses Enter
        ↓
POST /scans validates the repo
        ↓
Invalid repo:
  frontend shows invalid repository message
        ↓
Valid repo:
  scan row is created in Supabase
  Redis job is created
  frontend receives scan_id
  frontend polls scan status inline on the landing page
```

Phase 1 should stop at job queueing. The worker consuming the job starts Phase 2.
