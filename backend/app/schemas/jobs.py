from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel


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


class ClonedRepository(BaseModel):
    scan_id: UUID
    repo_path: Path
    branch: str
    commit_sha: str
