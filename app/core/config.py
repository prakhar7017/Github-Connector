"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """GitHub API and app settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    auth_method: str = Field(
        default="PAT",
        description="Authentication mode: PAT (Personal Access Token) or OAUTH.",
    )
    github_token: str = Field(
        default="",
        description="GitHub PAT — required when AUTH_METHOD=PAT.",
    )
    github_api_base_url: str = Field(
        default="https://api.github.com",
        description="GitHub REST API base URL.",
    )
    github_client_id: str = Field(default="", description="OAuth App client ID (AUTH_METHOD=OAUTH).")
    github_client_secret: str = Field(
        default="",
        description="OAuth App client secret (AUTH_METHOD=OAUTH).",
    )
    github_redirect_uri: str = Field(
        default="",
        description="OAuth redirect URI registered on the GitHub OAuth App.",
    )

    @property
    def auth_method_normalized(self) -> Literal["PAT", "OAUTH"]:
        m = self.auth_method.strip().upper()
        if m in ("PAT", "OAUTH"):
            return m  # type: ignore[return-value]
        raise ValueError(f"AUTH_METHOD must be PAT or OAUTH, got {self.auth_method!r}")

    @property
    def github_api_base_url_normalized(self) -> str:
        return self.github_api_base_url.rstrip("/")

    @model_validator(mode="after")
    def validate_auth_configuration(self) -> Settings:
        if self.auth_method_normalized == "PAT":
            if not (self.github_token and self.github_token.strip()):
                raise ValueError("GITHUB_TOKEN is required when AUTH_METHOD=PAT")
        else:
            missing: list[str] = []
            if not (self.github_client_id and self.github_client_id.strip()):
                missing.append("GITHUB_CLIENT_ID")
            if not (self.github_client_secret and self.github_client_secret.strip()):
                missing.append("GITHUB_CLIENT_SECRET")
            if not (self.github_redirect_uri and self.github_redirect_uri.strip()):
                missing.append("GITHUB_REDIRECT_URI")
            if missing:
                raise ValueError(
                    "When AUTH_METHOD=OAUTH, the following must be set: " + ", ".join(missing)
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
