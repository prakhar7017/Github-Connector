"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """GitHub API and app settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    github_token: str = Field(
        ...,
        description="GitHub Personal Access Token (classic or fine-grained).",
    )
    github_api_base_url: str = Field(
        default="https://api.github.com",
        description="GitHub REST API base URL.",
    )

    @property
    def github_api_base_url_normalized(self) -> str:
        return self.github_api_base_url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
