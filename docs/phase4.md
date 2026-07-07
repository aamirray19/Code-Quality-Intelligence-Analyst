# Phase 4 — Output Generation and RAG Chatbot

## 1. Purpose

Phase 4 is the final phase of the Code Quality Intelligence Agent pipeline.

It starts only after the LangGraph workflow in Phase 3 has completed and all agent findings have been stored in Supabase.

The goal of this phase is to:

1. Generate the final code quality report.
2. Rank findings by severity.
3. Store report outputs in Supabase.
4. Store report and finding summaries in Qdrant for retrieval.
5. Expose report data to the frontend.
6. Enable a RAG chatbot that can answer questions about the scanned repository, generated findings, and final report.

Phase 4 does not clone repositories, parse code, generate chunks, create code graphs, or run analysis agents again.

---

## 2. Phase 4 Entry Condition

Phase 4 starts only when the scan has already completed Phase 3.

```txt
scan.status = analyzed
        ↓
Phase 4 starts
```

The backend or worker must confirm that the scan is in the correct state before report generation begins.

If the scan is not in the `analyzed` state, Phase 4 should not run.

---

## 3. Phase 4 Responsibilities

Phase 4 is responsible for two major areas:

```txt
1. Output generation
2. RAG chatbot
```

### 3.1 Output Generation

Output generation consumes findings from Phase 3 and produces a final frontend-ready report.

It handles:

```txt
- Fetching all agent findings
- Normalizing findings
- Deduplicating overlapping findings
- Ranking issues by severity
- Creating summary metrics
- Generating JSON report
- Generating Markdown report
- Storing the report in Supabase
- Embedding report context into Qdrant
- Marking scan as completed
```

### 3.2 RAG Chatbot

The RAG chatbot allows users to ask questions about:

```txt
- Repository structure
- Files and functions
- Agent findings
- Security issues
- Performance issues
- Complexity problems
- Reliability concerns
- Duplicated logic
- Final report summary
- Fix recommendations
- File and function relationships
```

The chatbot retrieves context from:

```txt
- Qdrant Cloud
- Neo4j Aura
- Supabase
```

---

## 4. High-Level Phase 4 Flow

```txt
Phase 3 completed
        ↓
scan.status = analyzed
        ↓
Worker starts Phase 4
        ↓
Update scan.status = generating_report
        ↓
Fetch all findings from Supabase
        ↓
Normalize findings
        ↓
Deduplicate findings
        ↓
Rank findings by severity
        ↓
Generate report metrics
        ↓
Generate final JSON report
        ↓
Generate final Markdown report
        ↓
Store report in Supabase
        ↓
Embed report summary and findings in Qdrant
        ↓
Update scan.status = completed
        ↓
Frontend displays report
        ↓
User interacts with RAG chatbot
```

---

## 5. Complete Phase 4 Flow Diagram

```txt
Supabase
scan_findings table
        ↓
Report Generation Service
        ↓
Finding Normalization Service
        ↓
Severity Ranking Service
        ↓
Report Builder Service
        ↓
        ├── JSON Report
        └── Markdown Report
        ↓
Supabase
scan_reports table
        ↓
Qdrant Cloud
agent_findings + scan_reports collections
        ↓
scan.status = completed
        ↓
Next.js Frontend
        ↓
Report UI + RAG Chatbot
```

---

## 6. Phase 4 Detailed Execution Flow

### Step 1 — Start Phase 4

The worker receives the `scan_id` after Phase 3 completes.

```txt
Worker receives scan_id
        ↓
Fetch scan from Supabase
        ↓
Check scan.status == analyzed
        ↓
Update scan.status = generating_report
```

If the scan is not in the `analyzed` state, the worker should stop execution.

Example status update:

```sql
update scans
set status = 'generating_report',
    updated_at = now()
where id = '<scan_id>';
```

---

### Step 2 — Fetch Agent Findings

The worker fetches all findings created by the LangGraph agents in Phase 3.

```txt
Supabase
scan_findings
        ↓
Fetch all findings where scan_id = current scan
```

Expected finding fields:

```txt
id
scan_id
agent_name
file_path
symbol_name
symbol_type
severity
title
description
recommendation
evidence
confidence
created_at
```

The findings should already be normalized by Phase 3 as much as possible, but Phase 4 performs a final cleanup before generating the report.

---

### Step 3 — Normalize Findings

Raw findings from multiple agents may have small inconsistencies.

The normalization service should standardize:

```txt
- Severity names
- Agent names
- File paths
- Symbol names
- Empty fields
- Confidence scores
- Recommendation text
```

Accepted severity values:

```txt
Extreme
High
Medium
Low
```

Any unexpected severity should be mapped safely.

Example:

```txt
Critical → Extreme
Severe   → High
Moderate → Medium
Info     → Low
```

Accepted agent names:

```txt
security
performance
complexity
duplication
reliability
```

---

### Step 4 — Deduplicate Findings

Multiple agents or repeated runs may produce overlapping findings.

Deduplication prevents duplicate issues from appearing in the final report.

Use a combination of:

```txt
scan_id
agent_name
file_path
symbol_name
severity
normalized_title
```

If two findings are highly similar, keep the one with:

```txt
1. Higher severity
2. Higher confidence
3. More complete recommendation
4. More detailed evidence
```

Example:

```txt
Security Agent:
Hardcoded secret found in config.py

Security Agent:
API key found in config.py
```

Final output:

```txt
Keep one security finding with the clearest evidence and recommendation.
```

---

### Step 5 — Rank Findings by Severity

Findings should be sorted using this severity order:

```txt
Extreme → High → Medium → Low
```

Internally, use a numeric score:

```txt
Extreme = 4
High    = 3
Medium  = 2
Low     = 1
```

This ranking is used for:

```txt
- Final report ordering
- Frontend issue display
- Overall risk calculation
- Prioritized fix recommendations
```

---

### Step 6 — Generate Report Metrics

Before creating the final report, calculate summary metrics.

Required metrics:

```txt
- Total findings
- Findings by severity
- Findings by agent
- Findings by file
- Top risky files
- Top issue categories
- Overall project risk
```

Example summary:

```json
{
  "total_findings": 42,
  "severity_counts": {
    "extreme": 2,
    "high": 8,
    "medium": 20,
    "low": 12
  },
  "agent_counts": {
    "security": 6,
    "performance": 8,
    "complexity": 12,
    "duplication": 7,
    "reliability": 9
  },
  "overall_risk": "High"
}
```

---

### Step 7 — Calculate Overall Risk

The overall risk should be calculated from the final normalized findings.

Recommended logic:

```txt
If one or more Extreme findings exist:
    overall_risk = Extreme

Else if three or more High findings exist:
    overall_risk = High

Else if one or more High findings exist:
    overall_risk = Medium

Else if Medium findings exist:
    overall_risk = Medium

Else:
    overall_risk = Low
```

This keeps the risk score simple and explainable.

---

### Step 8 — Generate Final JSON Report

The JSON report is used by the frontend.

It should be structured, filterable, and easy to render.

Example structure:

```json
{
  "scan_id": "uuid",
  "overall_risk": "High",
  "summary": {
    "total_findings": 42,
    "severity_counts": {
      "extreme": 2,
      "high": 8,
      "medium": 20,
      "low": 12
    },
    "agent_counts": {
      "security": 6,
      "performance": 8,
      "complexity": 12,
      "duplication": 7,
      "reliability": 9
    }
  },
  "top_findings": [],
  "findings_by_agent": {},
  "findings_by_file": {},
  "recommendations": []
}
```

The JSON report should include:

```txt
- scan_id
- repository metadata
- branch
- commit SHA
- overall risk
- summary metrics
- top findings
- findings by severity
- findings by agent
- findings by file
- prioritized recommendations
```

---

### Step 9 — Generate Final Markdown Report

The Markdown report is used for:

```txt
- Human-readable display
- Export
- Copying into documentation
- Sharing with developers
```

Example Markdown report:

```md
# Code Quality Report

## Overall Risk: High

## Summary

- Total findings: 42
- Extreme: 2
- High: 8
- Medium: 20
- Low: 12

## Top Issues

### 1. Hardcoded Secret in config.py

- Severity: Extreme
- Agent: Security
- Location: config.py
- Description: A hardcoded API key was found in the source code.
- Recommendation: Move secrets to environment variables or a secret manager.

### 2. High Complexity in payment_processor.py

- Severity: High
- Agent: Complexity
- Location: services/payment_processor.py
- Description: The function has deeply nested conditional logic.
- Recommendation: Split the function into smaller focused units.

## Recommended Fix Order

1. Fix all Extreme issues.
2. Fix High security and reliability issues.
3. Refactor complex functions.
4. Remove duplicated logic.
5. Address Medium and Low issues.
```

---

### Step 10 — Store Report in Supabase

The final report should be stored in a dedicated table.

Table: `scan_reports`

```sql
create table scan_reports (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid references scans(id) on delete cascade,
  overall_risk text not null,
  summary jsonb not null,
  report_json jsonb not null,
  report_markdown text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
```

Each scan should have one final report.

Recommended uniqueness constraint:

```sql
alter table scan_reports
add constraint unique_scan_report unique (scan_id);
```

---

### Step 11 — Store Report Context in Qdrant

After the report is generated, store report-level documents in Qdrant.

These documents improve chatbot responses.

Recommended Qdrant collections:

```txt
code_chunks
repo_symbols
agent_findings
scan_reports
```

Phase 4 writes mainly to:

```txt
agent_findings
scan_reports
```

Documents to embed:

```txt
- Final report summary
- Top findings
- Individual finding summaries
- File-level risk summaries
- Agent-level summaries
- Recommended fix plan
```

Example Qdrant payload:

```json
{
  "scan_id": "uuid",
  "doc_type": "scan_report",
  "repo_full_name": "owner/repo",
  "branch": "main",
  "overall_risk": "High",
  "content": "Final report summary text..."
}
```

---

### Step 12 — Mark Scan as Completed

After the report and embeddings are successfully stored:

```txt
Update scan.status = completed
```

Example:

```sql
update scans
set status = 'completed',
    updated_at = now()
where id = '<scan_id>';
```

At this point, the frontend can display the final report.

---

## 7. RAG Chatbot Flow

The chatbot becomes available only after the scan is completed.

```txt
scan.status = completed
        ↓
RAG chatbot enabled
```

The chatbot should not run while the scan is still being analyzed or while the report is still being generated.

---

## 7.1 Chatbot Data Sources

The chatbot should retrieve from three sources.

```txt
Qdrant Cloud
  - code chunks
  - repo symbols
  - agent findings
  - scan reports

Neo4j Aura
  - file relationships
  - import relationships
  - function calls
  - class relationships
  - dependency graph

Supabase
  - scan metadata
  - repo metadata
  - file metadata
  - findings
  - final report
  - chat history
```

---

## 7.2 Chatbot Request Flow

```txt
User asks question
        ↓
POST /scans/{scan_id}/chat
        ↓
Validate scan exists
        ↓
Check scan.status == completed
        ↓
Create or reuse chat session
        ↓
Classify question type
        ↓
Retrieve semantic context from Qdrant
        ↓
Optionally retrieve graph context from Neo4j
        ↓
Fetch exact metadata from Supabase
        ↓
Build grounded context
        ↓
Call LLM
        ↓
Store user message and assistant response
        ↓
Return answer with sources
```

---

## 7.3 Question Classification

Before retrieval, classify the user question.

Example categories:

```txt
code_explanation
issue_explanation
security_findings
performance_findings
complexity_findings
duplication_findings
reliability_findings
file_relationship
fix_recommendation
report_summary
general_repo_question
```

The category determines which retrieval sources should be prioritized.

---

## 7.4 Retrieval Strategy

### Code Explanation Questions

Example:

```txt
What does the authentication module do?
```

Retrieval:

```txt
Qdrant: code_chunks + repo_symbols
Neo4j: related functions/files
Supabase: file metadata
```

### Issue Explanation Questions

Example:

```txt
Why is this project marked high risk?
```

Retrieval:

```txt
Qdrant: scan_reports + agent_findings
Supabase: final report + findings
```

### File Relationship Questions

Example:

```txt
Which files depend on database.py?
```

Retrieval:

```txt
Neo4j: dependency graph
Supabase: file metadata
Qdrant: related chunks if explanation is needed
```

### Fix Recommendation Questions

Example:

```txt
How should I fix the security issues first?
```

Retrieval:

```txt
Supabase: findings filtered by agent = security
Qdrant: finding summaries
Sort: Extreme → High → Medium → Low
```

---

## 7.5 Prompt Context Format

The chatbot should receive structured context, not a raw dump.

Example:

```txt
Repository:
- owner/repo
- Branch: main
- Commit: abc123

Scan Summary:
- Overall Risk: High
- Total Findings: 42

Relevant Findings:
1. [Extreme] Hardcoded secret in config.py
   Recommendation: Move secrets to environment variables.

Relevant Code Context:
File: config.py
Lines: 10-18
...

Graph Context:
- auth.py imports config.py
- user_service.py calls authenticate_user()

User Question:
How do I fix the most serious security issue?
```

---

## 7.6 Chatbot Response Requirements

The chatbot should:

```txt
- Answer only using retrieved scan context
- Mention when context is unavailable
- Include source references
- Prefer exact file paths
- Prefer exact function or class names
- Avoid unsupported claims
- Give prioritized recommendations
```

The chatbot should not:

```txt
- Invent files
- Invent findings
- Assume code that was not retrieved
- Re-run agents
- Modify repository code
```

---

## 8. Required API Endpoints

### 8.1 Get Final Report

```txt
GET /scans/{scan_id}/report
```

Returns the final generated report.

Example response:

```json
{
  "scan_id": "uuid",
  "status": "completed",
  "overall_risk": "High",
  "summary": {},
  "report_json": {},
  "report_markdown": ""
}
```

---

### 8.2 Get Findings

```txt
GET /scans/{scan_id}/findings
```

Optional filters:

```txt
?severity=High
?agent=security
?file_path=app/main.py
```

Example response:

```json
{
  "scan_id": "uuid",
  "findings": []
}
```

---

### 8.3 Chat With Repository

```txt
POST /scans/{scan_id}/chat
```

Example request:

```json
{
  "message": "What are the most critical issues in this repo?",
  "session_id": "optional-session-id"
}
```

Example response:

```json
{
  "answer": "The most critical issues are...",
  "sources": [
    {
      "type": "finding",
      "file_path": "app/main.py",
      "severity": "Extreme"
    }
  ],
  "session_id": "uuid"
}
```

---

### 8.4 Get Chat History

```txt
GET /scans/{scan_id}/chat/sessions/{session_id}
```

Example response:

```json
{
  "session_id": "uuid",
  "scan_id": "uuid",
  "messages": [
    {
      "role": "user",
      "content": "What are the security issues?"
    },
    {
      "role": "assistant",
      "content": "The main security issues are..."
    }
  ]
}
```

---

## 9. Required Supabase Tables

### 9.1 `scan_reports`

Stores the generated report.

```sql
create table scan_reports (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid references scans(id) on delete cascade,
  overall_risk text not null,
  summary jsonb not null,
  report_json jsonb not null,
  report_markdown text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
```

---

### 9.2 `chat_sessions`

Stores chatbot sessions.

```sql
create table chat_sessions (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid references scans(id) on delete cascade,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
```

---

### 9.3 `chat_messages`

Stores user and assistant messages.

```sql
create table chat_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references chat_sessions(id) on delete cascade,
  role text not null,
  content text not null,
  sources jsonb,
  created_at timestamptz default now()
);
```

---

## 10. Backend Folder Structure

Recommended Phase 4 backend structure:

```txt
backend/
  app/
    api/
      routes/
        reports.py
        findings.py
        chat.py

    services/
      report_generation_service.py
      finding_normalization_service.py
      finding_deduplication_service.py
      severity_ranking_service.py
      risk_scoring_service.py
      rag_retrieval_service.py
      graph_context_service.py
      chatbot_service.py
      source_builder_service.py

    repositories/
      scan_repository.py
      finding_repository.py
      report_repository.py
      chat_repository.py

    schemas/
      report.py
      finding.py
      chat.py
```

---

## 11. Service Responsibilities

### `report_generation_service.py`

Responsible for creating the final JSON and Markdown reports.

```txt
Input:
- scan metadata
- normalized findings

Output:
- report_json
- report_markdown
- summary metrics
- overall risk
```

### `finding_normalization_service.py`

Responsible for cleaning and standardizing findings.

```txt
Tasks:
- Normalize severity
- Normalize agent names
- Normalize file paths
- Fill missing fields
```

### `finding_deduplication_service.py`

Responsible for removing duplicate or overlapping findings.

```txt
Tasks:
- Detect duplicate findings
- Keep strongest finding
- Preserve unique findings
```

### `severity_ranking_service.py`

Responsible for sorting issues by importance.

```txt
Sort order:
Extreme → High → Medium → Low
```

### `risk_scoring_service.py`

Responsible for calculating the overall project risk.

```txt
Input:
- normalized findings

Output:
- Low
- Medium
- High
- Extreme
```

### `rag_retrieval_service.py`

Responsible for semantic retrieval from Qdrant.

```txt
Reads from:
- code_chunks
- repo_symbols
- agent_findings
- scan_reports
```

### `graph_context_service.py`

Responsible for graph-based context from Neo4j.

```txt
Reads from:
- files
- imports
- calls
- classes
- functions
- dependencies
```

### `chatbot_service.py`

Responsible for handling chatbot orchestration.

```txt
Tasks:
- Validate scan status
- Classify user query
- Retrieve Qdrant context
- Retrieve Neo4j context when needed
- Fetch Supabase metadata
- Build prompt context
- Call LLM
- Store messages
- Return answer with sources
```

### `source_builder_service.py`

Responsible for formatting answer sources.

```txt
Source types:
- file
- code_chunk
- symbol
- finding
- report
- graph_relation
```

---

## 12. Worker Flow

Phase 4 should run inside the worker after Phase 3 completes.

```txt
run_phase_4(scan_id)
        ↓
Fetch scan metadata
        ↓
Validate scan.status == analyzed
        ↓
Update status = generating_report
        ↓
Fetch findings
        ↓
Normalize findings
        ↓
Deduplicate findings
        ↓
Rank findings
        ↓
Calculate summary metrics
        ↓
Calculate overall risk
        ↓
Generate JSON report
        ↓
Generate Markdown report
        ↓
Store scan report in Supabase
        ↓
Store report context in Qdrant
        ↓
Update status = completed
```

If any step fails:

```txt
Update scan.status = failed
Store error_message
Stop execution
```

---

## 13. Final Scan Lifecycle

After Phase 4 is added, the full scan lifecycle becomes:

```txt
queued
  ↓
cloning
  ↓
discovering_files
  ↓
parsing
  ↓
storing_indexes
  ↓
parsed
  ↓
analyzing
  ↓
analyzed
  ↓
generating_report
  ↓
completed
```

Failure can happen at any point:

```txt
failed
```

---

## 14. Frontend Flow

After the scan is completed:

```txt
Frontend polls GET /scans/{scan_id}
        ↓
Receives status = completed
        ↓
Frontend calls GET /scans/{scan_id}/report
        ↓
Displays:
  - Overall risk
  - Summary metrics
  - Findings by severity
  - Findings by agent
  - Findings by file
  - Final Markdown report
        ↓
Enables RAG chatbot
```

Chatbot flow:

```txt
User sends message
        ↓
Frontend calls POST /scans/{scan_id}/chat
        ↓
Backend returns grounded answer + sources
        ↓
Frontend displays answer and sources
```

---

## 15. Phase 4 Output

At the end of Phase 4, the system should have:

```txt
Supabase:
- Completed scan status
- Final report
- Chat sessions
- Chat messages

Qdrant:
- Report summary embeddings
- Finding summary embeddings

Neo4j:
- Existing code graph from Phase 2 used for chatbot context

Frontend:
- Report page
- Filterable findings
- RAG chatbot
```

---

## 16. Phase 4 Boundary

Phase 4 consumes:

```txt
- Supabase scan metadata
- Supabase agent findings
- Qdrant code chunks
- Qdrant report/finding embeddings
- Neo4j code graph
```

Phase 4 produces:

```txt
- Final JSON report
- Final Markdown report
- Ranked issue list
- Overall risk score
- Report embeddings
- Chatbot responses
- Chat history
```

Phase 4 must not:

```txt
- Clone the GitHub repository again
- Parse source files again
- Generate Tree-sitter chunks again
- Rebuild Neo4j graph again
- Re-run LangGraph agents again
```

---

## 17. Completion Criteria

Phase 4 is complete when:

```txt
- scan.status is completed
- scan_reports row exists for the scan
- report_json is available
- report_markdown is available
- findings are ranked by severity
- report/finding summaries are embedded in Qdrant
- frontend can display the report
- chatbot can answer scan-specific questions
- chat history is stored
```

---

## 18. Summary

Phase 4 is the reporting and interaction layer of the project.

It takes the completed analysis from Phase 3, converts it into a useful final report, stores the output, and enables a RAG chatbot for interactive exploration of the scanned repository.

Final responsibility:

```txt
Phase 4 = Report generation + RAG chatbot
```
