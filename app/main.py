"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import sys

from fastapi import FastAPI

from app.routes import auth as auth_routes
from app.routes import github as github_routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

app = FastAPI(
    title="GitHub Cloud Connector",
    description="REST API for GitHub: PAT or OAuth 2.0 (AUTH_METHOD), issues, commits, pull requests.",
    version="1.0.0",
)

app.include_router(auth_routes.router)
app.include_router(github_routes.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
