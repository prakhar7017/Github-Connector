"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import sys

from fastapi import FastAPI

from app.routes import github as github_routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

app = FastAPI(
    title="GitHub Cloud Connector",
    description="REST API that proxies selected GitHub REST operations using a Personal Access Token.",
    version="1.0.0",
)

app.include_router(github_routes.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
