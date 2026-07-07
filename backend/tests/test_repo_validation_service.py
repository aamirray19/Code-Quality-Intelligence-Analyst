import httpx
import pytest
import respx

from app.core.errors import AppError
from app.services.repo_validation_service import validate_repository

REPO_JSON = {
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
}


@respx.mock
def test_validate_repository_success_uses_default_branch():
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=httpx.Response(200, json=REPO_JSON)
    )

    result = validate_repository("https://github.com/owner/repo")

    assert result.owner == "owner"
    assert result.branch == "main"
    assert result.size_kb == 1277


@respx.mock
def test_validate_repository_checks_requested_branch():
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=httpx.Response(200, json=REPO_JSON)
    )
    respx.get("https://api.github.com/repos/owner/repo/branches/dev").mock(
        return_value=httpx.Response(200, json={"name": "dev"})
    )

    result = validate_repository("https://github.com/owner/repo/tree/dev")

    assert result.branch == "dev"


@respx.mock
def test_validate_repository_branch_not_found():
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=httpx.Response(200, json=REPO_JSON)
    )
    respx.get("https://api.github.com/repos/owner/repo/branches/missing").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )

    with pytest.raises(AppError) as exc_info:
        validate_repository("https://github.com/owner/repo/tree/missing")

    assert exc_info.value.error_code == "BRANCH_NOT_FOUND"


@respx.mock
def test_validate_repository_rejects_private():
    private_json = {**REPO_JSON, "private": True, "visibility": "private"}
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=httpx.Response(200, json=private_json)
    )

    with pytest.raises(AppError) as exc_info:
        validate_repository("https://github.com/owner/repo")

    assert exc_info.value.error_code == "PRIVATE_REPOSITORY"


@respx.mock
def test_validate_repository_rejects_archived():
    archived_json = {**REPO_JSON, "archived": True}
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=httpx.Response(200, json=archived_json)
    )

    with pytest.raises(AppError) as exc_info:
        validate_repository("https://github.com/owner/repo")

    assert exc_info.value.error_code == "ARCHIVED_REPOSITORY"


@respx.mock
def test_validate_repository_rejects_too_large(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_repo_size_kb", 100)
    large_json = {**REPO_JSON, "size": 200}
    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=httpx.Response(200, json=large_json)
    )

    with pytest.raises(AppError) as exc_info:
        validate_repository("https://github.com/owner/repo")

    assert exc_info.value.error_code == "REPO_TOO_LARGE"
