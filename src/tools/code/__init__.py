
from src.tools.code.github import admin, issues, prs, notifications, GithubTools

# tool json schema
GITHUB_TOOLS_SCHEMA = [*issues, *prs, *notifications]
GITHUB_ADMIN_TOOLS_SCHEMA = [*admin]

__all__ = [
    "GithubTools",
    "GITHUB_TOOLS_SCHEMA",
    "GITHUB_ADMIN_TOOLS_SCHEMA",
]
