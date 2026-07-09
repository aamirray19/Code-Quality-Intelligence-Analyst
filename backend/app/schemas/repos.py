from pydantic import BaseModel


class ParsedGitHubURL(BaseModel):
    owner: str
    repo: str
    branch: str | None = None
    normalized_url: str


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


class ScanStatusRepoResponse(BaseModel):
    owner: str
    name: str
    full_name: str
    branch: str
    html_url: str
    commit_sha: str | None = None
