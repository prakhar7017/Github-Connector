"""GitHub-related HTTP routes."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.exceptions import GitHubAPIError
from app.models.schemas import (
    CommitSummary,
    CreateIssueRequest,
    CreatePullRequestRequest,
    IssueSummary,
    PullRequestSummary,
    RepositorySummary,
)
from app.services.github_service import GitHubService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["github"])


def get_github_service() -> GitHubService:
    return GitHubService()


GitHubSvc = Annotated[GitHubService, Depends(get_github_service)]


@router.get(
    "/repos/{username}",
    response_model=list[RepositorySummary],
    summary="List repositories for a GitHub user",
)
async def list_user_repositories(username: str, svc: GitHubSvc) -> list[RepositorySummary]:
    if not username.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username must not be empty.",
        )
    try:
        raw = await svc.list_user_repositories(username)
    except GitHubAPIError as e:
        logger.info("list_user_repositories failed: %s", e.message)
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    out: list[RepositorySummary] = []
    for item in raw:
        try:
            out.append(RepositorySummary.model_validate(item))
        except Exception:  # noqa: BLE001 — skip malformed entries
            logger.warning("Skipping repo item that failed validation: %s", item.get("full_name"))
    return out


@router.get(
    "/issues/{owner}/{repo}",
    response_model=list[IssueSummary],
    summary="List issues for a repository",
)
async def list_repository_issues(owner: str, repo: str, svc: GitHubSvc) -> list[IssueSummary]:
    if not owner.strip() or not repo.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Owner and repository name must not be empty.",
        )
    try:
        raw = await svc.list_repository_issues(owner, repo)
    except GitHubAPIError as e:
        logger.info("list_repository_issues failed: %s", e.message)
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    out: list[IssueSummary] = []
    for item in raw:
        try:
            out.append(IssueSummary.model_validate(item))
        except Exception:  # noqa: BLE001
            logger.warning("Skipping issue item id=%s", item.get("id"))
    return out


@router.post(
    "/create-issue",
    response_model=IssueSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create an issue in a repository",
)
async def create_issue(payload: CreateIssueRequest, svc: GitHubSvc) -> IssueSummary:
    try:
        raw = await svc.create_issue(
            payload.owner,
            payload.repo,
            payload.title,
            payload.body,
        )
    except GitHubAPIError as e:
        logger.info("create_issue failed: %s", e.message)
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    try:
        return IssueSummary.model_validate(raw)
    except Exception as e:  # noqa: BLE001
        logger.exception("GitHub returned issue payload we could not validate")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub returned an unexpected issue payload.",
        ) from e


@router.get(
    "/commits/{owner}/{repo}",
    response_model=list[CommitSummary],
    summary="List recent commits for a repository",
)
async def list_repository_commits(
    owner: str,
    repo: str,
    svc: GitHubSvc,
    sha: str | None = Query(
        default=None,
        description="Branch name or commit SHA to list from (GitHub `sha` query param).",
    ),
    per_page: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Number of commits to return (GitHub max 100 per request).",
    ),
) -> list[CommitSummary]:
    if not owner.strip() or not repo.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Owner and repository name must not be empty.",
        )
    try:
        raw = await svc.list_repository_commits(owner, repo, sha=sha, per_page=per_page)
    except GitHubAPIError as e:
        logger.info("list_repository_commits failed: %s", e.message)
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    return [CommitSummary.model_validate(row) for row in raw]


@router.post(
    "/create-pull-request",
    response_model=PullRequestSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Open a pull request",
)
async def create_pull_request(
    payload: CreatePullRequestRequest,
    svc: GitHubSvc,
) -> PullRequestSummary:
    try:
        raw = await svc.create_pull_request(
            payload.owner,
            payload.repo,
            payload.title,
            payload.head,
            payload.base,
            payload.body,
        )
    except GitHubAPIError as e:
        logger.info("create_pull_request failed: %s", e.message)
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    try:
        return PullRequestSummary.model_validate(raw)
    except Exception as e:  # noqa: BLE001
        logger.exception("GitHub returned pull request payload we could not validate")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub returned an unexpected pull request payload.",
        ) from e
