import operator
from typing import Annotated, TypedDict


class RepoContext(TypedDict):
    scan_id: str
    repo_full_name: str
    default_branch: str
    commit_sha: str | None
    total_files: int
    total_symbols: int
    language_breakdown: dict


class AnalysisTask(TypedDict):
    task_id: str
    agent_name: str
    objective: str
    priority: int
    target_file_ids: list[str]
    target_chunk_ids: list[str]
    target_symbol_ids: list[str]


class RawFinding(TypedDict):
    agent: str
    title: str
    description: str
    severity: str
    confidence: float
    file_path: str | None
    symbol_name: str | None
    start_line: int | None
    end_line: int | None
    evidence: list[str]
    recommendation: str | None


class NormalizedFinding(TypedDict):
    scan_id: str
    agent: str
    title: str
    description: str
    severity: str
    confidence: float
    file_id: str | None
    symbol_id: str | None
    file_path: str | None
    symbol_name: str | None
    start_line: int | None
    end_line: int | None
    evidence: list[str]
    recommendation: str | None
    fingerprint: str
    related_agents: list[str]


class AnalysisState(TypedDict, total=False):
    scan_id: str
    repo_context: RepoContext
    analysis_tasks: list[AnalysisTask]
    raw_findings: Annotated[list[RawFinding], operator.add]
    normalized_findings: list[NormalizedFinding]
    deduped_findings: list[NormalizedFinding]
    ranked_findings: list[NormalizedFinding]
    status: str
    errors: Annotated[list[str], operator.add]
