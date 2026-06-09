from __future__ import annotations

import httpx


_GITHUB_RESPONSE_HEADERS = (
    "x-github-request-id",
    "x-ratelimit-remaining",
    "x-ratelimit-limit",
    "x-ratelimit-reset",
    "retry-after",
    "x-oauth-scopes",
    "x-accepted-oauth-scopes",
    "x-accepted-github-permissions",
    "x-github-sso",
)


def collect_github_response(response: httpx.Response) -> str:
    """Collect a token-safe GitHub response summary for task errors."""
    body = response.text.strip().replace("\n", " ")[:500]
    headers = "; ".join(
        f"{name}={value}"
        for name in _GITHUB_RESPONSE_HEADERS
        if (value := response.headers.get(name))
    )
    suffix = f"; {headers}" if headers else ""
    return f"GitHub returned {response.status_code}; body={body}{suffix}"
