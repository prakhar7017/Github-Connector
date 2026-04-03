"""GitHub authentication strategies (PAT vs OAuth) and factory."""

from app.auth.factory import get_auth_strategy
from app.auth.strategies import GitHubAuthStrategy, OAuthStrategy, PATAuthStrategy

__all__ = [
    "GitHubAuthStrategy",
    "OAuthStrategy",
    "PATAuthStrategy",
    "get_auth_strategy",
]
