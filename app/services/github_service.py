"""Async GitHub REST API client and business logic."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import Settings, get_settings
from app.core.exceptions import GitHubAPIError

logger = logging.getLogger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, GitHubAPIError):
        return exc.status_code in (429, 500, 502, 503, 504)
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout))


def _github_error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
        if isinstance(data, dict) and "message" in data:
            return str(data["message"])
    except Exception:  # noqa: BLE001 — best-effort parse
        pass
    return response.text or response.reason_phrase


class GitHubService:
    """Encapsulates all GitHub REST calls."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._settings.github_api_base_url_normalized,
            headers=self._headers(),
            timeout=httpx.Timeout(30.0),
        )

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        @retry(
            reraise=True,
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
            retry=retry_if_exception(_is_retryable),
        )
        async def _do(
            client: httpx.AsyncClient,
            *,
            req_params: dict[str, Any] | None,
        ) -> httpx.Response:
            logger.debug("GitHub %s %s params=%s", method, url, req_params)
            response = await client.request(method, url, params=req_params, json=json)
            if response.is_error:
                msg = _github_error_message(response)
                logger.warning(
                    "GitHub API error %s %s -> %s: %s",
                    method,
                    url,
                    response.status_code,
                    msg,
                )
                raise GitHubAPIError(response.status_code, msg)
            return response

        async with self._client() as client:
            resp = await _do(client, req_params=params)
            if resp.content:
                return resp.json()
            return None

    async def list_user_repositories(self, username: str) -> list[dict[str, Any]]:
        username = username.strip()
        if not username:
            raise GitHubAPIError(400, "Username is required.")
        path = f"/users/{username}/repos"
        data = await self._request(
            "GET",
            path,
            params={"per_page": 100, "sort": "updated"},
        )
        if not isinstance(data, list):
            raise GitHubAPIError(502, "Unexpected response from GitHub.")
        return data

    async def list_repository_issues(self, owner: str, repo: str) -> list[dict[str, Any]]:
        owner, repo = owner.strip(), repo.strip()
        if not owner or not repo:
            raise GitHubAPIError(400, "Owner and repository name are required.")
        path = f"/repos/{owner}/{repo}/issues"
        data = await self._request(
            "GET",
            path,
            params={"per_page": 100, "state": "all"},
        )
        if not isinstance(data, list):
            raise GitHubAPIError(502, "Unexpected response from GitHub.")
        # GitHub's issues endpoint also returns pull requests; keep true issues only.
        return [item for item in data if isinstance(item, dict) and "pull_request" not in item]

    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str | None,
    ) -> dict[str, Any]:
        owner, repo = owner.strip(), repo.strip()
        title = title.strip()
        if not owner or not repo:
            raise GitHubAPIError(400, "Owner and repository name are required.")
        if not title:
            raise GitHubAPIError(400, "Issue title is required.")
        path = f"/repos/{owner}/{repo}/issues"
        payload: dict[str, Any] = {"title": title}
        if body is not None and body.strip():
            payload["body"] = body
        data = await self._request("POST", path, json=payload)
        if not isinstance(data, dict):
            raise GitHubAPIError(502, "Unexpected response from GitHub.")
        return data

    async def list_repository_commits(
        self,
        owner: str,
        repo: str,
        *,
        sha: str | None = None,
        per_page: int = 10,
    ) -> list[dict[str, Any]]:
        """List commits as simplified DTO dicts (sha, author_name, message, date)."""
        owner, repo = owner.strip(), repo.strip()
        if not owner or not repo:
            raise GitHubAPIError(400, "Owner and repository name are required.")
        if per_page < 1:
            raise GitHubAPIError(400, "per_page must be at least 1.")
        per_page = min(per_page, 100)

        path = f"/repos/{owner}/{repo}/commits"
        qp: dict[str, Any] = {"per_page": per_page}
        if sha is not None and sha.strip():
            qp["sha"] = sha.strip()

        logger.info("Fetching commits for %s/%s (per_page=%s, sha=%s)", owner, repo, per_page, sha)
        data = await self._request("GET", path, params=qp)
        if not isinstance(data, list):
            raise GitHubAPIError(502, "Unexpected response from GitHub.")

        simplified: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            simplified.append(_commit_item_to_dto(item))
        return simplified

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str | None,
    ) -> dict[str, Any]:
        owner, repo = owner.strip(), repo.strip()
        title = (title or "").strip()
        head = (head or "").strip()
        base = (base or "").strip()
        if not owner or not repo:
            raise GitHubAPIError(400, "Owner and repository name are required.")
        if not title:
            raise GitHubAPIError(400, "Pull request title is required.")
        if not head:
            raise GitHubAPIError(400, "Head branch (head) is required.")
        if not base:
            raise GitHubAPIError(400, "Base branch (base) is required.")

        path = f"/repos/{owner}/{repo}/pulls"
        payload: dict[str, Any] = {"title": title, "head": head, "base": base}
        if body is not None and body.strip():
            payload["body"] = body

        logger.info("Creating pull request %s/%s %s <- %s", owner, repo, base, head)
        data = await self._request("POST", path, json=payload)
        if not isinstance(data, dict):
            raise GitHubAPIError(502, "Unexpected response from GitHub.")
        return data


def _commit_item_to_dto(item: dict[str, Any]) -> dict[str, Any]:
    inner = item.get("commit")
    if not isinstance(inner, dict):
        inner = {}
    author = inner.get("author")
    if not isinstance(author, dict):
        author = inner.get("committer") if isinstance(inner.get("committer"), dict) else {}
    if not isinstance(author, dict):
        author = {}
    sha = item.get("sha")
    return {
        "sha": sha if isinstance(sha, str) else "",
        "author_name": author.get("name") if isinstance(author.get("name"), str) else None,
        "message": inner.get("message") if isinstance(inner.get("message"), str) else "",
        "date": author.get("date") if isinstance(author.get("date"), str) else None,
    }
