"""GitHub OAuth 2.0 authorization endpoints."""

from __future__ import annotations

import logging
import secrets
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse

from app.auth import oauth_store
from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/login", summary="Start GitHub OAuth (redirects to github.com)")
async def oauth_login(settings: SettingsDep) -> RedirectResponse:
    if settings.auth_method_normalized != "OAUTH":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GET /auth/login is only used when AUTH_METHOD=OAUTH. "
            "You are configured for PAT authentication.",
        )

    state = secrets.token_urlsafe(32)
    oauth_store.set_pending_oauth_state(state)
    params = {
        "client_id": settings.github_client_id.strip(),
        "redirect_uri": settings.github_redirect_uri.strip(),
        "scope": "repo",
        "state": state,
    }
    authorize_url = "https://github.com/login/oauth/authorize?" + urlencode(params)
    logger.info("Redirecting to GitHub OAuth authorize (state set)")
    return RedirectResponse(authorize_url, status_code=status.HTTP_302_FOUND)


@router.get("/callback", summary="OAuth callback — exchange code for access token")
async def oauth_callback(
    settings: SettingsDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> dict:
    if settings.auth_method_normalized != "OAUTH":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GET /auth/callback is only valid when AUTH_METHOD=OAUTH.",
        )
    if error:
        msg = error_description or error
        logger.warning("OAuth error from GitHub: %s — %s", error, msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub OAuth denied or failed: {msg}",
        )
    if not code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing query parameter `code`. After authorizing, GitHub redirects here with ?code=...",
        )
    if not oauth_store.pop_and_validate_oauth_state(state):
        logger.warning("OAuth callback with invalid or expired state")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state. Start again at GET /auth/login.",
        )

    logger.info("Exchanging OAuth code for access token")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={
                    "Accept": "application/json",
                },
                data={
                    "client_id": settings.github_client_id.strip(),
                    "client_secret": settings.github_client_secret.strip(),
                    "code": code,
                    "redirect_uri": settings.github_redirect_uri.strip(),
                },
                timeout=httpx.Timeout(30.0),
            )
        except httpx.RequestError as e:
            logger.exception("OAuth token request failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Could not reach GitHub to exchange code: {e}",
            ) from e

    if response.is_error:
        logger.warning("OAuth token exchange HTTP error: %s %s", response.status_code, response.text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub token exchange failed. Check client id, secret, redirect URI, and code validity.",
        )

    try:
        payload = response.json()
    except Exception:  # noqa: BLE001
        logger.warning("Non-JSON OAuth response: %s", response.text[:500])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unexpected response from GitHub during token exchange.",
        )

    if isinstance(payload, dict) and payload.get("error"):
        desc = payload.get("error_description") or payload["error"]
        logger.warning("OAuth token exchange rejected: %s", desc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub rejected the code: {desc}",
        )

    access_token = payload.get("access_token") if isinstance(payload, dict) else None
    if not access_token or not isinstance(access_token, str):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub did not return an access_token.",
        )

    token_type = str(payload.get("token_type") or "bearer")
    scope = payload.get("scope")
    scope_str = str(scope) if scope is not None else None

    oauth_store.set_oauth_token(access_token, token_type=token_type, scope=scope_str)
    logger.info("OAuth access token stored in memory (type=%s, scope=%s)", token_type, scope_str)

    # Demo / local dev: returning the token in JSON. Do not do this in production frontends over public networks.
    return {
        "status": "ok",
        "message": "Token stored server-side. Subsequent API calls use it automatically.",
        "access_token": "xxxxxxxxxxxxx",
        "token_type": token_type,
        "scope": scope_str,
    }
