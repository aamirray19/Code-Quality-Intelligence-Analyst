import pytest

from app.core.errors import AppError
from app.services.github_url_parser import parse_github_url


@pytest.mark.parametrize(
    "url,expected_owner,expected_repo,expected_branch",
    [
        ("https://github.com/owner/repo", "owner", "repo", None),
        ("https://github.com/owner/repo/", "owner", "repo", None),
        ("https://github.com/owner/repo.git", "owner", "repo", None),
        ("https://github.com/owner/repo/tree/branch-name", "owner", "repo", "branch-name"),
    ],
)
def test_parses_supported_url_formats(url, expected_owner, expected_repo, expected_branch):
    result = parse_github_url(url)

    assert result.owner == expected_owner
    assert result.repo == expected_repo
    assert result.branch == expected_branch
    assert result.normalized_url == f"https://github.com/{expected_owner}/{expected_repo}"


@pytest.mark.parametrize(
    "url,expected_error_code",
    [
        ("https://github.com/owner/repo/pull/1", "UNSUPPORTED_GITHUB_URL"),
        ("https://github.com/owner/repo/issues/1", "UNSUPPORTED_GITHUB_URL"),
        ("https://github.com/owner/repo/blob/main/file.py", "UNSUPPORTED_GITHUB_URL"),
        ("https://gitlab.com/owner/repo", "INVALID_GITHUB_URL"),
        ("https://bitbucket.org/owner/repo", "INVALID_GITHUB_URL"),
        ("https://github.com/owner", "INVALID_GITHUB_URL"),
        ("not-a-url", "INVALID_GITHUB_URL"),
    ],
)
def test_rejects_unsupported_or_invalid_urls(url, expected_error_code):
    with pytest.raises(AppError) as exc_info:
        parse_github_url(url)

    assert exc_info.value.error_code == expected_error_code
