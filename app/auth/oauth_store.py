"""In-memory OAuth session storage (single-process demo / dev)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

_lock = threading.Lock()

_oauth_access_token: str | None = None
_oauth_token_type: str | None = None
_oauth_scope: str | None = None
# GitHub user access tokens typically do not expire unless revoked; we track received time for observability.
_token_received_at_monotonic: float | None = None

# CSRF: single pending state per process (good enough for local dev; use distributed store in production).
_pending_state: str | None = None
_state_created_at: float | None = None

_STATE_TTL_SEC = 600.0


@dataclass(frozen=True)
class OAuthTokenSnapshot:
    access_token: str
    token_type: str
    scope: str | None
    received_at_monotonic: float


def set_pending_oauth_state(state: str) -> None:
    global _pending_state, _state_created_at
    with _lock:
        _pending_state = state
        _state_created_at = time.monotonic()


def pop_and_validate_oauth_state(state: str | None) -> bool:
    """Return True if state matches a non-expired pending login."""
    global _pending_state, _state_created_at
    with _lock:
        if not state or not _pending_state or state != _pending_state:
            return False
        if _state_created_at is None or (time.monotonic() - _state_created_at) > _STATE_TTL_SEC:
            _pending_state = None
            _state_created_at = None
            return False
        _pending_state = None
        _state_created_at = None
        return True


def set_oauth_token(access_token: str, *, token_type: str = "bearer", scope: str | None = None) -> None:
    global _oauth_access_token, _oauth_token_type, _oauth_scope, _token_received_at_monotonic
    with _lock:
        _oauth_access_token = access_token
        _oauth_token_type = token_type or "bearer"
        _oauth_scope = scope
        _token_received_at_monotonic = time.monotonic()


def get_oauth_token_snapshot() -> OAuthTokenSnapshot | None:
    with _lock:
        if not _oauth_access_token:
            return None
        return OAuthTokenSnapshot(
            access_token=_oauth_access_token,
            token_type=_oauth_token_type or "bearer",
            scope=_oauth_scope,
            received_at_monotonic=_token_received_at_monotonic or time.monotonic(),
        )


def clear_oauth_session() -> None:
    global _oauth_access_token, _oauth_token_type, _oauth_scope, _token_received_at_monotonic
    global _pending_state, _state_created_at
    with _lock:
        _oauth_access_token = None
        _oauth_token_type = None
        _oauth_scope = None
        _token_received_at_monotonic = None
        _pending_state = None
        _state_created_at = None
