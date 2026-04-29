from __future__ import annotations

import uuid
from dataclasses import dataclass

from src.server.postgres.database import Database


@dataclass(frozen=True)
class NexusTaskContext:
    task_id: uuid.UUID
    database: Database
    repo: str
    current_work_item_id: uuid.UUID | None = None

    @property
    def default_local_path(self) -> str:
        repo_name = self.repo.rsplit("/", 1)[-1] if self.repo else "repo"
        return f"/workspace/{repo_name}"
