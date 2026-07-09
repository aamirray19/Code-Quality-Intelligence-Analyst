import httpx

from app.core.config import settings
from app.core.errors import AppError
from app.schemas.repos import GitHubRepoMetadata

GITHUB_API_BASE = "https://api.github.com"


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def _request(url: str) -> httpx.Response:
    try:
        return httpx.get(url, headers=_headers(), timeout=10.0)
    except httpx.HTTPError as exc:
        raise AppError("GITHUB_API_ERROR", "Failed to reach GitHub API.", 502) from exc


def get_repo_metadata(owner: str, repo: str) -> GitHubRepoMetadata:
    response = _request(f"{GITHUB_API_BASE}/repos/{owner}/{repo}")

    if response.status_code == 404:
        raise AppError("REPO_NOT_FOUND", "Repository does not exist.", 404)
    if response.status_code == 403 and "rate limit" in response.text.lower():
        raise AppError("GITHUB_RATE_LIMITED", "GitHub API rate limit exceeded.", 429)
    if response.status_code != 200:
        raise AppError("GITHUB_API_ERROR", "GitHub API returned an unexpected error.", 502)

    data = response.json()
    return GitHubRepoMetadata(
        owner=data["owner"]["login"],
        name=data["name"],
        full_name=data["full_name"],
        default_branch=data["default_branch"],
        clone_url=data["clone_url"],
        html_url=data["html_url"],
        size_kb=data["size"],
        private=data["private"],
        visibility=data.get("visibility") or ("private" if data["private"] else "public"),
        archived=data["archived"],
    )


def branch_exists(owner: str, repo: str, branch: str) -> bool:
    response = _request(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/branches/{branch}")

    if response.status_code == 200:
        return True
    if response.status_code == 404:
        return False
    if response.status_code == 403 and "rate limit" in response.text.lower():
        raise AppError("GITHUB_RATE_LIMITED", "GitHub API rate limit exceeded.", 429)
    raise AppError("GITHUB_API_ERROR", "GitHub API returned an unexpected error.", 502)
