import httpx
import pytest
import respx

from app.core.errors import AppError
from app.services import github_metadata_service


@respx.mock
def test_get_repo_metadata_success():
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=httpx.Response(
            200,
            json={
                "owner": {"login": "owner"},
                "name": "repo",
                "full_name": "owner/repo",
                "default_branch": "main",
                "clone_url": "https://github.com/owner/repo.git",
                "html_url": "https://github.com/owner/repo",
                "size": 1277,
                "private": False,
                "visibility": "public",
                "archived": False,
            },
        )
    )

    metadata = github_metadata_service.get_repo_metadata("owner", "repo")

    assert metadata.full_name == "owner/repo"
    assert metadata.size_kb == 1277
    assert metadata.private is False
    assert metadata.archived is False


@respx.mock
def test_get_repo_metadata_not_found():
    respx.get("https://api.github.com/repos/owner/missing").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )

    with pytest.raises(AppError) as exc_info:
        github_metadata_service.get_repo_metadata("owner", "missing")

    assert exc_info.value.error_code == "REPO_NOT_FOUND"


@respx.mock
def test_get_repo_metadata_rate_limited():
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=httpx.Response(403, json={"message": "API rate limit exceeded"})
    )

    with pytest.raises(AppError) as exc_info:
        github_metadata_service.get_repo_metadata("owner", "repo")

    assert exc_info.value.error_code == "GITHUB_RATE_LIMITED"


@respx.mock
def test_branch_exists_true():
    respx.get("https://api.github.com/repos/owner/repo/branches/main").mock(
        return_value=httpx.Response(200, json={"name": "main"})
    )

    assert github_metadata_service.branch_exists("owner", "repo", "main") is True


@respx.mock
def test_branch_exists_false():
    respx.get("https://api.github.com/repos/owner/repo/branches/missing").mock(
        return_value=httpx.Response(404, json={"message": "Branch not found"})
    )

    assert github_metadata_service.branch_exists("owner", "repo", "missing") is False
