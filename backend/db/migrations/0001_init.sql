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

  commit_sha text,
  phase text,
  started_at timestamptz,
  parsed_at timestamptz,
  reported_at timestamptz,
  failed_at timestamptz,
  error_code text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table scan_events (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references scans(id) on delete cascade,

  event_type text not null,
  message text not null,
  metadata jsonb,

  created_at timestamptz not null default now()
);

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

create table parse_errors (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references scans(id) on delete cascade,
  file_id uuid references scan_files(id) on delete cascade,

  error_type text not null,
  error_message text not null,
  metadata jsonb,

  created_at timestamptz not null default now()
);

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

create table agent_runs (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references scans(id) on delete cascade,
  analysis_task_id uuid references analysis_tasks(id) on delete set null,

  agent_name text not null,
  status text not null default 'running',

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

create table findings (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references scans(id) on delete cascade,

  primary_agent text not null,
  title text not null,
  description text not null,
  severity text not null check (severity in ('extreme', 'high', 'medium', 'low')),
  confidence numeric not null,

  file_id uuid references scan_files(id) on delete set null,
  symbol_id uuid references code_symbols(id) on delete set null,
  file_path text,
  symbol_name text,
  start_line integer,
  end_line integer,

  evidence jsonb not null default '[]',
  recommendation text,

  fingerprint text not null,
  related_agents jsonb not null default '[]',

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique(scan_id, fingerprint)
);

create table reports (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references scans(id) on delete cascade,

  summary_markdown text not null,
  metrics jsonb not null default '{}',
  risk_score numeric not null,

  created_at timestamptz not null default now(),

  unique(scan_id)
);

create table chat_sessions (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references scans(id) on delete cascade,

  title text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table chat_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references chat_sessions(id) on delete cascade,

  role text not null check (role in ('user', 'assistant')),
  content text not null,
  sources jsonb not null default '[]',

  created_at timestamptz not null default now()
);

