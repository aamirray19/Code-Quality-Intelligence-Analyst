from app.core.config import settings
from app.core.errors import AppError
from app.schemas.repos import ValidatedRepository
from app.services import github_metadata_service
from app.services.github_url_parser import parse_github_url


def validate_repository(github_url: str) -> ValidatedRepository:
    parsed = parse_github_url(github_url)
    metadata = github_metadata_service.get_repo_metadata(parsed.owner, parsed.repo)

    if metadata.private:
        raise AppError("PRIVATE_REPOSITORY", "Only public GitHub repositories are supported.", 403)

    if metadata.archived:
        raise AppError("ARCHIVED_REPOSITORY", "Archived repositories are not supported.", 422)

    if metadata.size_kb > settings.max_repo_size_kb:
        raise AppError("REPO_TOO_LARGE", "Repository exceeds the allowed size limit.", 413)

    branch = parsed.branch or metadata.default_branch
    if parsed.branch and not github_metadata_service.branch_exists(parsed.owner, parsed.repo, parsed.branch):
        raise AppError("BRANCH_NOT_FOUND", "The specified branch does not exist.", 404)

    return ValidatedRepository(
        owner=metadata.owner,
        name=metadata.name,
        full_name=metadata.full_name,
        branch=branch,
        default_branch=metadata.default_branch,
        clone_url=metadata.clone_url,
        html_url=metadata.html_url,
        size_kb=metadata.size_kb,
        visibility=metadata.visibility,
    )
