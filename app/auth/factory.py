"""Select authentication strategy from configuration."""

from __future__ import annotations

import logging

from app.auth.strategies import GitHubAuthStrategy, OAuthStrategy, PATAuthStrategy
from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def get_auth_strategy(settings: Settings | None = None) -> GitHubAuthStrategy:
    """Return PAT or OAuth strategy based on AUTH_METHOD."""
    s = settings or get_settings()
    method = s.auth_method_normalized
    if method == "PAT":
        logger.debug("Using PAT authentication strategy")
        return PATAuthStrategy(s)
    if method == "OAUTH":
        logger.debug("Using OAuth authentication strategy")
        return OAuthStrategy(s)
    raise ValueError(f"Unsupported AUTH_METHOD: {s.auth_method!r}; use PAT or OAUTH")
