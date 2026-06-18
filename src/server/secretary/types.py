from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PullRequestSummary:
    repo: str
    number: int
    title: str
    state: str
    draft: bool
    html_url: str
    author: str | None
    head_sha: str
    head_ref: str
    base_ref: str
    mergeable: bool | None = None
    mergeable_state: str | None = None


@dataclass(frozen=True)
class ChangedFile:
    filename: str
    status: str | None
    additions: int
    deletions: int
    changes: int
    patch: str | None = None


@dataclass(frozen=True)
class PullRequestContext:
    summary: PullRequestSummary
    body: str
    files: list[ChangedFile]
    reviews: list[dict[str, Any]]
    comments: list[dict[str, Any]]
    review_comments: list[dict[str, Any]]
    check_runs: list[dict[str, Any]]
    statuses: list[dict[str, Any]]


@dataclass(frozen=True)
class CheckSummary:
    available: bool
    pending: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    successful: list[str] = field(default_factory=list)

    @property
    def all_successful(self) -> bool:
        """Return whether every available check/status succeeded."""
        return self.available and not self.pending and not self.failed
