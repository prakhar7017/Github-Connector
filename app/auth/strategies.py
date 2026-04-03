"""Strategy pattern for GitHub API authentication headers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.auth import oauth_store
from app.core.config import Settings

logger = logging.getLogger(__name__)


class GitHubAuthStrategy(ABC):
    """Produces HTTP headers for authenticated GitHub REST requests."""

    @abstractmethod
    def get_headers(self) -> dict[str, str]:
        """Return headers including Authorization and Accept for api.github.com."""


class PATAuthStrategy(GitHubAuthStrategy):
    """Uses a Personal Access Token from configuration."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_headers(self) -> dict[str, str]:
        token = (self._settings.github_token or "").strip()
        if not token:
            logger.error("PAT missing at request time")
            raise AuthHeadersUnavailableError(
                "GitHub PAT is not configured. Set GITHUB_TOKEN when AUTH_METHOD=PAT.",
                status_code=401,
            )
        return _github_api_auth_headers(token)


class OAuthStrategy(GitHubAuthStrategy):
    """Uses an OAuth access token stored after the /auth/callback flow."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_headers(self) -> dict[str, str]:
        info = oauth_store.get_oauth_token_snapshot()
        if not info:
            logger.warning("OAuth API call attempted before login completed")
            raise AuthHeadersUnavailableError(
                "OAuth access token is not available. Complete the flow: GET /auth/login, "
                "then authorize in the browser, then GET /auth/callback?code=...&state=....",
                status_code=401,
            )
        return _github_api_auth_headers(info.access_token)


def _github_api_auth_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


class AuthHeadersUnavailableError(RuntimeError):
    """Raised when headers cannot be built (missing PAT or OAuth session)."""

    def __init__(self, message: str, *, status_code: int = 401) -> None:
        self.status_code = status_code
        super().__init__(message)
