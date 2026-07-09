from urllib.parse import urlparse

from app.core.errors import AppError
from app.schemas.repos import ParsedGitHubURL

_UNSUPPORTED_SEGMENTS = {"pull", "issues", "blob"}


def parse_github_url(url: str) -> ParsedGitHubURL:
    """Parse a GitHub repository URL into owner, repo, and optional branch.

    Raises AppError(INVALID_GITHUB_URL) for malformed input or non-GitHub hosts,
    and AppError(UNSUPPORTED_GITHUB_URL) for GitHub URLs pointing at unsupported
    paths such as /pull, /issues, or /blob.
    """
    try:
        parsed = urlparse(url.strip())
    except ValueError as exc:
        raise AppError(
            "INVALID_GITHUB_URL",
            "Repository is invalid. Please enter a valid GitHub repository URL.",
            422,
        ) from exc

    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise AppError(
            "INVALID_GITHUB_URL",
            "Repository is invalid. Please enter a valid GitHub repository URL.",
            422,
        )

    segments = [segment for segment in parsed.path.split("/") if segment]

    if len(segments) < 2:
        raise AppError(
            "INVALID_GITHUB_URL",
            "Repository is invalid. Please enter a valid GitHub repository URL.",
            422,
        )

    owner, repo = segments[0], segments[1]
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]

    remaining = segments[2:]
    branch: str | None = None

    if remaining:
        if remaining[0] in _UNSUPPORTED_SEGMENTS:
            raise AppError(
                "UNSUPPORTED_GITHUB_URL",
                "This type of GitHub URL is not supported. Use a repository URL.",
                422,
            )
        if remaining[0] == "tree" and len(remaining) > 1:
            branch = "/".join(remaining[1:])
        else:
            raise AppError(
                "UNSUPPORTED_GITHUB_URL",
                "This type of GitHub URL is not supported. Use a repository URL.",
                422,
            )

    normalized_url = f"https://github.com/{owner}/{repo}"

    return ParsedGitHubURL(owner=owner, repo=repo, branch=branch, normalized_url=normalized_url)
