
from src.tools.code.github import issues, prs, notifications, GithubTools

# tool json schema
GITHUB_TOOLS_SCHEMA = [*issues, *prs, *notifications]

__all__ = [
    "GithubTools",
    "GITHUB_TOOLS_SCHEMA",
]
