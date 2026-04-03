"""Pydantic request/response models."""

from pydantic import BaseModel, ConfigDict, Field


class CreateIssueRequest(BaseModel):
    owner: str = Field(..., min_length=1, description="Repository owner (user or org).")
    repo: str = Field(..., min_length=1, description="Repository name.")
    title: str = Field(..., min_length=1, description="Issue title.")
    body: str | None = Field(default=None, description="Issue body (markdown).")


class RepositorySummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    full_name: str
    private: bool
    html_url: str
    description: str | None = None
    default_branch: str | None = None


class IssueSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    number: int
    title: str
    state: str
    html_url: str
    body: str | None = None


class CommitSummary(BaseModel):
    """Simplified commit row for API responses (DTO)."""

    sha: str
    author_name: str | None = None
    message: str
    date: str | None = Field(
        default=None,
        description="Author timestamp (ISO 8601) from Git commit metadata.",
    )


class CreatePullRequestRequest(BaseModel):
    owner: str = Field(..., min_length=1, description="Repository owner (user or org).")
    repo: str = Field(..., min_length=1, description="Repository name.")
    title: str = Field(..., min_length=1, description="Pull request title.")
    head: str = Field(
        ...,
        min_length=1,
        description="Branch containing changes (e.g. feature-branch or user:feature-branch).",
    )
    base: str = Field(..., min_length=1, description="Branch to merge into (e.g. main).")
    body: str | None = Field(default=None, description="PR description (markdown).")


class PullRequestSummary(BaseModel):
    """Subset of GitHub pull response for clients (DTO)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: int
    title: str
    state: str
    url: str = Field(alias="html_url")
