"""Domain exceptions for GitHub integration."""


class GitHubAPIError(Exception):
    """Raised when the GitHub API returns an error or is unreachable."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)
