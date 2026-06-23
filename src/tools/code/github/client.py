from __future__ import annotations

import shlex

import httpx

from mwin import track

from src.sandbox import Sandbox
from src.tools.nexus import NexusTaskContext


def _github_error_detail(response: httpx.Response) -> str:
    """Extract a readable GitHub error message."""
    try:
        payload = response.json()
    except Exception:
        return response.text
    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, str):
            return message
    return response.text


def _github_headers(token: str) -> dict[str, str]:
    """Return standard GitHub API headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


class GithubTools:
    """GitHub/git operations bound to a sandbox container."""

    def __init__(
        self,
        sandbox: Sandbox,
        nexus_task_context: NexusTaskContext | None = None,
    ) -> None:
        """Initialize the object."""
        self._sandbox = sandbox
        self._nexus_task_context = nexus_task_context

    async def _clean_existing_checkout(self, local_path: str) -> dict:
        """Remove leftover checkout state before syncing a reused sandbox."""
        quoted_path = shlex.quote(local_path)
        return await self._sandbox.run_shell(
            f"(git -C {quoted_path} merge --abort >/dev/null 2>&1 || true) && "
            f"(git -C {quoted_path} rebase --abort >/dev/null 2>&1 || true) && "
            f"git -C {quoted_path} reset --hard && "
            f"git -C {quoted_path} clean -ffdx"
        )

    async def _remove_non_git_checkout(self, local_path: str) -> dict:
        """Remove a stale non-git checkout directory under /workspace."""
        quoted_path = shlex.quote(local_path)
        return await self._sandbox.run_shell(
            f"case {quoted_path} in "
            f"/workspace/*) rm -rf -- {quoted_path} ;; "
            f"*) echo 'Refusing to remove checkout outside /workspace' >&2; exit 1 ;; "
            f"esac"
        )

    async def _sync_main_branch(self, local_path: str) -> dict:
        """Synchronize local main branches with remotes."""
        quoted_path = shlex.quote(local_path)
        return await self._sandbox.run_shell(
            f"git -C {quoted_path} fetch upstream main && "
            f"git -C {quoted_path} checkout main && "
            f"git -C {quoted_path} reset --hard upstream/main && "
            f"git -C {quoted_path} push origin main --force-with-lease"
        )

    @track(step_type="tool")
    async def fetch_from_github(
        self,
        repo_url: str,
        local_path: str,
        branch: str = "main",
        token: str | None = None,
        upstream_url: str | None = None,
    ) -> dict:
        """Prepare a GitHub repository checkout inside the sandbox.

        The checkout is intentionally treated as disposable state. If
        ``local_path`` already contains the expected Git repository, this method
        aborts any in-progress merge or rebase, discards tracked changes, removes
        untracked and ignored files, fetches the requested branch, and resets the
        local branch to the matching remote ref. This makes reused Docker
        workspaces converge to a clean remote state before an agent starts work.

        If ``local_path`` does not contain a Git repository, any stale directory
        at that path is removed when it is under ``/workspace`` and the
        repository is cloned from ``repo_url``. If the existing checkout points
        at a different origin URL, the sandbox is recreated before cloning.

        Args:
            repo_url: Clone URL for the repository. Pass an authenticated URL
                when private repository access is required.
            local_path: Absolute sandbox path where the repository should exist.
            branch: Branch to prepare. Defaults to ``main``.
            token: Unused compatibility parameter. Authentication is expected to
                be embedded in ``repo_url`` when needed.
            upstream_url: Optional upstream repository URL for fork workflows.
                When provided with ``branch="main"``, the local main branch is
                reset to ``upstream/main`` and pushed to ``origin/main`` with
                ``--force-with-lease``.

        Returns:
            A dictionary with ``success``, ``path``, ``branch``, and ``message``
            keys describing the checkout result. ``success`` is false when a Git
            command fails.
        """

        authenticated_url = repo_url
        expected_repo_url = repo_url
        result: dict | None = None
        message = ""

        quoted_path = shlex.quote(local_path)
        quoted_git_dir = shlex.quote(f"{local_path}/.git")
        quoted_branch = shlex.quote(branch)
        quoted_repo_url = shlex.quote(authenticated_url)
        quoted_upstream_url = shlex.quote(upstream_url) if upstream_url else None

        check = await self._sandbox.run_shell(
            f"test -d {quoted_git_dir} && echo exists || echo new"
        )

        if "exists" in check.get("stdout", ""):
            remote_result = await self._sandbox.run_shell(
                f"git -C {quoted_path} config --get remote.origin.url"
            )
            existing_remote = remote_result.get("stdout", "").strip()
            existing_remote_canonical = existing_remote

            remote_missing = not remote_result.get("success", False) or not existing_remote
            remote_mismatch = (
                expected_repo_url is not None
                and existing_remote_canonical != expected_repo_url
            )

            if remote_missing or remote_mismatch:
                await self._sandbox.recreate()
                check = {"stdout": "new"}
            else:
                clean_result = await self._clean_existing_checkout(local_path)
                if not clean_result.get("success", False):
                    return {
                        "success": False,
                        "path": local_path,
                        "branch": branch,
                        "message": clean_result.get("stderr", "failed to clean checkout"),
                    }

                if upstream_url and branch == "main":
                    await self._sandbox.run_shell(
                        f"git -C {quoted_path} fetch --all && "
                        f"(git -C {quoted_path} remote add upstream {quoted_upstream_url} 2>/dev/null || "
                        f"git -C {quoted_path} remote set-url upstream {quoted_upstream_url})"
                    )
                    result = await self._sync_main_branch(local_path)
                    message = f"Synchronized 'main' with upstream at {local_path}"
                else:
                    result = await self._sandbox.run_shell(
                        f"git -C {quoted_path} fetch origin {quoted_branch} && "
                        f"git -C {quoted_path} checkout -B {quoted_branch} origin/{quoted_branch} && "
                        f"git -C {quoted_path} reset --hard origin/{quoted_branch}"
                    )
                    message = f"Reset branch '{branch}' to origin/{branch} at {local_path}"

        if "new" in check.get("stdout", ""):
            remove_result = await self._remove_non_git_checkout(local_path)
            if not remove_result.get("success", False):
                return {
                    "success": False,
                    "path": local_path,
                    "branch": branch,
                    "message": remove_result.get("stderr", "failed to remove stale checkout"),
                }
            result = await self._sandbox.run_shell(
                f"git clone --branch {quoted_branch} {quoted_repo_url} {quoted_path}"
            )
            if result.get("success", False) and upstream_url:
                await self._sandbox.run_shell(
                    f"(git -C {quoted_path} remote add upstream {quoted_upstream_url} 2>/dev/null || "
                    f"git -C {quoted_path} remote set-url upstream {quoted_upstream_url})"
                )
                if branch == "main":
                    result = await self._sync_main_branch(local_path)
                    message = f"Cloned '{repo_url}' and synchronized 'main' with upstream into {local_path}"
                else:
                    message = f"Cloned '{repo_url}' (branch: {branch}) into {local_path}"
            else:
                message = f"Cloned '{repo_url}' (branch: {branch}) into {local_path}"

        if result is None:
            return {
                "success": False,
                "path": local_path,
                "branch": branch,
                "message": "Failed to determine repository state for fetch.",
            }

        if not result.get("success", False):
            return {
                "success": False,
                "path": local_path,
                "branch": branch,
                "message": result.get("stderr", "git command failed"),
            }
        return {"success": True, "path": local_path, "branch": branch, "message": message}


    @track(step_type="tool")
    async def create_github_issue(
        self,
        token: str,
        repo: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> dict:
        """Create a GitHub issue."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"https://api.github.com/repos/{repo}/issues",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json={"title": title, "body": body, "labels": labels or []},
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "issue_number": data["number"],
                    "issue_url": data["html_url"],
                    "message": f"Issue #{data['number']} created: {data['html_url']}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "issue_number": None,
                    "issue_url": "",
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type="tool")
    async def pr_to_github(
        self,
        token: str,
        repo: str,
        branch: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        closes_issues: list[int] | None = None,
        local_path: str | None = None,
        draft: bool = False,
    ) -> dict:
        """Push a branch and open a GitHub pull request."""
        if closes_issues:
            body = body + "\n\n" + "\n".join(f"Closes #{n}" for n in closes_issues)

        # head may be in "owner:branch" format for the GitHub API; extract just the branch name for git push
        push_branch = head.split(":")[-1] if ":" in head else head
        push_cmd = (
            f"git -C {local_path} push origin {push_branch}"
            if local_path
            else f"git push origin {push_branch}"
        )
        result = await self._sandbox.run_shell(push_cmd)
        if result is None:
            return {
                "success": False,
                "path": local_path,
                "branch": branch,
                "message": "Failed to determine repository state for fetch.",
            }

        if not result.get("success", False):
            return {
                "success": False,
                "pr_url": "",
                "pr_number": None,
                "message": f"Failed to push branch '{head}': {result.get('stderr', '')}",
            }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"https://api.github.com/repos/{repo}/pulls",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json={"title": title, "body": body, "head": head, "base": base, "draft": draft},
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "pr_url": data["html_url"],
                    "pr_number": data["number"],
                    "message": f"Pull request #{data['number']} created: {data['html_url']}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "pr_url": "",
                    "pr_number": None,
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }

    # ==========================================================================
    # Issue and PR Comment/Review Interaction Methods
    # ==========================================================================

    @track(step_type="tool")
    async def list_open_pull_requests(
        self,
        token: str,
        repo: str,
        per_page: int = 30,
    ) -> dict:
        """List open pull requests in a repository."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/pulls",
                    headers=_github_headers(token),
                    params={"state": "open", "per_page": per_page},
                )
                response.raise_for_status()
                pulls = response.json()
                formatted = []
                for pull in pulls:
                    formatted.append({
                        "number": pull["number"],
                        "title": pull["title"],
                        "state": pull["state"],
                        "draft": pull.get("draft", False),
                        "html_url": pull["html_url"],
                        "created_at": pull["created_at"],
                        "updated_at": pull["updated_at"],
                        "user": pull.get("user", {}).get("login"),
                        "head_ref": pull.get("head", {}).get("ref"),
                        "head_sha": pull.get("head", {}).get("sha"),
                        "base_ref": pull.get("base", {}).get("ref"),
                    })
                return {
                    "success": True,
                    "repo": repo,
                    "pr_count": len(formatted),
                    "pull_requests": formatted,
                    "message": f"Found {len(formatted)} open PRs in {repo}",
                }
            except httpx.HTTPStatusError as e:
                return {
                    "success": False,
                    "pull_requests": [],
                    "message": f"GitHub API error {e.response.status_code}: {_github_error_detail(e.response)}",
                }

    @track(step_type="tool")
    async def get_pull_request(
        self,
        token: str,
        repo: str,
        pull_number: int,
    ) -> dict:
        """Fetch pull request metadata."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}",
                    headers=_github_headers(token),
                )
                response.raise_for_status()
                pull = response.json()
                return {
                    "success": True,
                    "pull_request": {
                        "number": pull["number"],
                        "title": pull["title"],
                        "body": pull.get("body") or "",
                        "state": pull["state"],
                        "draft": pull.get("draft", False),
                        "html_url": pull["html_url"],
                        "user": pull.get("user", {}).get("login"),
                        "head_ref": pull.get("head", {}).get("ref"),
                        "head_sha": pull.get("head", {}).get("sha"),
                        "head_repo": pull.get("head", {}).get("repo", {}).get("full_name")
                        if pull.get("head", {}).get("repo")
                        else None,
                        "base_ref": pull.get("base", {}).get("ref"),
                        "base_sha": pull.get("base", {}).get("sha"),
                        "mergeable": pull.get("mergeable"),
                        "mergeable_state": pull.get("mergeable_state"),
                        "commits": pull.get("commits"),
                        "additions": pull.get("additions"),
                        "deletions": pull.get("deletions"),
                        "changed_files": pull.get("changed_files"),
                    },
                    "message": f"Retrieved PR #{pull_number}",
                }
            except httpx.HTTPStatusError as e:
                return {
                    "success": False,
                    "pull_request": None,
                    "message": f"GitHub API error {e.response.status_code}: {_github_error_detail(e.response)}",
                }

    @track(step_type="tool")
    async def get_pr_files(
        self,
        token: str,
        repo: str,
        pull_number: int,
        per_page: int = 100,
    ) -> dict:
        """Fetch changed files for a pull request."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}/files",
                    headers=_github_headers(token),
                    params={"per_page": per_page},
                )
                response.raise_for_status()
                files = response.json()
                formatted = []
                for file in files:
                    formatted.append({
                        "filename": file["filename"],
                        "status": file["status"],
                        "additions": file.get("additions", 0),
                        "deletions": file.get("deletions", 0),
                        "changes": file.get("changes", 0),
                        "patch": file.get("patch"),
                        "raw_url": file.get("raw_url"),
                    })
                return {
                    "success": True,
                    "pull_number": pull_number,
                    "file_count": len(formatted),
                    "files": formatted,
                    "message": f"Retrieved {len(formatted)} changed files on PR #{pull_number}",
                }
            except httpx.HTTPStatusError as e:
                return {
                    "success": False,
                    "files": [],
                    "message": f"GitHub API error {e.response.status_code}: {_github_error_detail(e.response)}",
                }

    @track(step_type="tool")
    async def get_pr_check_summary(
        self,
        token: str,
        repo: str,
        ref: str,
    ) -> dict:
        """Fetch check runs and commit statuses for a PR head ref."""
        async with httpx.AsyncClient() as client:
            try:
                check_response = await client.get(
                    f"https://api.github.com/repos/{repo}/commits/{ref}/check-runs",
                    headers=_github_headers(token),
                    params={"per_page": 100},
                )
                check_response.raise_for_status()
                status_response = await client.get(
                    f"https://api.github.com/repos/{repo}/commits/{ref}/status",
                    headers=_github_headers(token),
                )
                status_response.raise_for_status()
                checks_payload = check_response.json()
                status_payload = status_response.json()
            except httpx.HTTPStatusError as e:
                return {
                    "success": False,
                    "available": False,
                    "all_successful": False,
                    "pending": [],
                    "failed": [],
                    "successful": [],
                    "message": f"GitHub API error {e.response.status_code}: {_github_error_detail(e.response)}",
                }

        pending: list[str] = []
        failed: list[str] = []
        successful: list[str] = []
        for check in checks_payload.get("check_runs", []):
            name = check.get("name") or "check"
            status = check.get("status")
            conclusion = check.get("conclusion")
            if status != "completed":
                pending.append(name)
            elif conclusion in {"success", "neutral", "skipped"}:
                successful.append(name)
            else:
                failed.append(name)

        for status in status_payload.get("statuses", []):
            context = status.get("context") or "status"
            state = status.get("state")
            if state == "success":
                successful.append(context)
            elif state in {"pending", "expected"}:
                pending.append(context)
            else:
                failed.append(context)

        available = bool(pending or failed or successful)
        return {
            "success": True,
            "available": available,
            "all_successful": available and not pending and not failed,
            "pending": pending,
            "failed": failed,
            "successful": successful,
            "message": f"Found {len(successful)} successful, {len(pending)} pending, {len(failed)} failed checks/statuses",
        }

    @track(step_type="tool")
    async def get_issue_comments(
        self,
        token: str,
        repo: str,
        issue_number: int,
        per_page: int = 30,
    ) -> dict:
        """Fetch all comments on a specific issue."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={"per_page": per_page},
                )
                response.raise_for_status()
                comments = response.json()
                formatted_comments = []
                for comment in comments:
                    formatted_comments.append({
                        "id": comment["id"],
                        "user": comment["user"]["login"],
                        "body": comment["body"],
                        "created_at": comment["created_at"],
                        "updated_at": comment["updated_at"],
                        "html_url": comment["html_url"],
                    })
                return {
                    "success": True,
                    "issue_number": issue_number,
                    "comment_count": len(formatted_comments),
                    "comments": formatted_comments,
                    "message": f"Retrieved {len(formatted_comments)} comments on issue #{issue_number}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "comments": [],
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type="tool")
    async def reply_to_issue(
        self,
        token: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> dict:
        """Add a comment to an issue."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json={"body": body},
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "comment_id": data["id"],
                    "comment_url": data["html_url"],
                    "message": f"Comment added to issue #{issue_number}: {data['html_url']}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "comment_id": None,
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type="tool")
    async def get_pr_reviews(
        self,
        token: str,
        repo: str,
        pull_number: int,
    ) -> dict:
        """Fetch all reviews on a pull request."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}/reviews",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                response.raise_for_status()
                reviews = response.json()
                formatted_reviews = []
                for review in reviews:
                    formatted_reviews.append({
                        "id": review["id"],
                        "user": review["user"]["login"],
                        "state": review["state"],
                        "body": review["body"],
                        "submitted_at": review.get("submitted_at"),
                        "html_url": review["html_url"],
                    })
                return {
                    "success": True,
                    "pull_number": pull_number,
                    "review_count": len(formatted_reviews),
                    "reviews": formatted_reviews,
                    "message": f"Retrieved {len(formatted_reviews)} reviews on PR #{pull_number}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "reviews": [],
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type="tool")
    async def get_pr_review_comments(
        self,
        token: str,
        repo: str,
        pull_number: int,
    ) -> dict:
        """Fetch inline review comments on a pull request."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}/comments",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                response.raise_for_status()
                comments = response.json()
                formatted_comments = []
                for comment in comments:
                    formatted_comments.append({
                        "id": comment["id"],
                        "user": comment["user"]["login"],
                        "body": comment["body"],
                        "path": comment["path"],
                        "line": comment.get("line"),
                        "original_line": comment.get("original_line"),
                        "commit_id": comment["commit_id"],
                        "created_at": comment["created_at"],
                        "html_url": comment["html_url"],
                    })
                return {
                    "success": True,
                    "pull_number": pull_number,
                    "comment_count": len(formatted_comments),
                    "comments": formatted_comments,
                    "message": f"Retrieved {len(formatted_comments)} review comments on PR #{pull_number}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "comments": [],
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type="tool")
    async def reply_to_pr_review_comment(
        self,
        token: str,
        repo: str,
        pull_number: int,
        comment_id: int,
        body: str,
    ) -> dict:
        """Reply to a specific inline review comment on a PR.
        
        Note: GitHub API creates a reply as a new comment in reply-to relation.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}/comments/{comment_id}/replies",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json={"body": body},
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "reply_id": data["id"],
                    "reply_url": data["html_url"],
                    "message": f"Reply added to review comment: {data['html_url']}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "reply_id": None,
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type="tool")
    async def get_pr_comments(
        self,
        token: str,
        repo: str,
        pull_number: int,
    ) -> dict:
        """Fetch general (non-review) comments on a pull request."""
        async with httpx.AsyncClient() as client:
            try:
                # PR comments are accessed via the issues endpoint
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/issues/{pull_number}/comments",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                response.raise_for_status()
                comments = response.json()
                formatted_comments = []
                for comment in comments:
                    formatted_comments.append({
                        "id": comment["id"],
                        "user": comment["user"]["login"],
                        "body": comment["body"],
                        "created_at": comment["created_at"],
                        "updated_at": comment["updated_at"],
                        "html_url": comment["html_url"],
                    })
                return {
                    "success": True,
                    "pull_number": pull_number,
                    "comment_count": len(formatted_comments),
                    "comments": formatted_comments,
                    "message": f"Retrieved {len(formatted_comments)} comments on PR #{pull_number}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "comments": [],
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type="tool")
    async def reply_to_pr(
        self,
        token: str,
        repo: str,
        pull_number: int,
        body: str,
    ) -> dict:
        """Add a general comment to a pull request."""
        # PR comments use the same endpoint as issue comments
        return await self.reply_to_issue(token, repo, pull_number, body)


    @track(step_type="tool")
    async def create_pr_review(
        self,
        token: str,
        repo: str,
        pull_number: int,
        event: str,
        body: str,
        commit_id: str | None = None,
        comments: list[dict] | None = None,
    ) -> dict:
        """Submit a formal GitHub pull request review."""
        payload: dict = {
            "event": event,
            "body": body,
        }
        if commit_id:
            payload["commit_id"] = commit_id
        normalized_comments: list[dict] = []
        for comment in comments or []:
            normalized = {
                key: value
                for key, value in comment.items()
                if value is not None and key in {"path", "body", "line", "side", "start_line", "start_side"}
            }
            if normalized:
                normalized_comments.append(normalized)
        if normalized_comments:
            payload["comments"] = normalized_comments

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}/reviews",
                    headers=_github_headers(token),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "review_id": data.get("id"),
                    "html_url": data.get("html_url"),
                    "state": data.get("state"),
                    "message": f"Review submitted on PR #{pull_number}: {data.get('html_url')}",
                }
            except httpx.HTTPStatusError as e:
                return {
                    "success": False,
                    "review_id": None,
                    "html_url": "",
                    "message": f"GitHub API error {e.response.status_code}: {_github_error_detail(e.response)}",
                }

    @track(step_type="tool")
    async def merge_pr(
        self,
        token: str,
        repo: str,
        pull_number: int,
        sha: str,
        merge_method: str = "squash",
        commit_title: str | None = None,
        commit_message: str | None = None,
    ) -> dict:
        """Merge a pull request with an expected head SHA."""
        payload: dict = {
            "sha": sha,
            "merge_method": merge_method,
        }
        if commit_title:
            payload["commit_title"] = commit_title
        if commit_message:
            payload["commit_message"] = commit_message

        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(
                    f"https://api.github.com/repos/{repo}/pulls/{pull_number}/merge",
                    headers=_github_headers(token),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "success": bool(data.get("merged", False)),
                    "sha": data.get("sha"),
                    "message": data.get("message") or f"Merged PR #{pull_number}",
                }
            except httpx.HTTPStatusError as e:
                return {
                    "success": False,
                    "sha": None,
                    "message": f"GitHub API error {e.response.status_code}: {_github_error_detail(e.response)}",
                }


    @track(step_type="tool")
    async def get_my_open_prs(
        self,
        token: str,
        repo: str,
        creator: str,
        per_page: int = 10,
    ) -> dict:
        """List open pull requests created by a specific user."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/pulls",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={
                        "state": "open",
                        "creator": creator,
                        "per_page": per_page,
                    },
                )
                response.raise_for_status()
                prs = response.json()
                formatted_prs = []
                for pr in prs:
                    formatted_prs.append({
                        "number": pr["number"],
                        "title": pr["title"],
                        "state": pr["state"],
                        "html_url": pr["html_url"],
                        "created_at": pr["created_at"],
                        "updated_at": pr["updated_at"],
                        "comments": pr["comments"],
                        "review_comments": pr["review_comments"],
                    })
                return {
                    "success": True,
                    "creator": creator,
                    "pr_count": len(formatted_prs),
                    "pull_requests": formatted_prs,
                    "message": f"Found {len(formatted_prs)} open PRs by {creator}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "pull_requests": [],
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type="tool")
    async def get_my_issues(
        self,
        token: str,
        repo: str,
        creator: str,
        state: str = "open",
        per_page: int = 10,
    ) -> dict:
        """List issues created by a specific user."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.github.com/repos/{repo}/issues",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={
                        "state": state,
                        "creator": creator,
                        "per_page": per_page,
                    },
                )
                response.raise_for_status()
                issues = response.json()
                # Filter out PRs (they appear as issues in the API)
                issues = [i for i in issues if "pull_request" not in i]
                formatted_issues = []
                for issue in issues:
                    formatted_issues.append({
                        "number": issue["number"],
                        "title": issue["title"],
                        "state": issue["state"],
                        "html_url": issue["html_url"],
                        "created_at": issue["created_at"],
                        "updated_at": issue["updated_at"],
                        "comments": issue["comments"],
                    })
                return {
                    "success": True,
                    "creator": creator,
                    "issue_count": len(formatted_issues),
                    "issues": formatted_issues,
                    "message": f"Found {len(formatted_issues)} issues by {creator}",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "issues": [],
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }


    @track(step_type="tool")
    async def get_notifications(
        self,
        token: str,
        all: bool = False,
        participating: bool = False,
        per_page: int = 30,
    ) -> dict:
        """Fetch GitHub notifications."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://api.github.com/notifications",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={
                        "all": str(all).lower(),
                        "participating": str(participating).lower(),
                        "per_page": per_page,
                    },
                )
                response.raise_for_status()
                notifications = response.json()
                formatted_notifications = []
                for notification in notifications:
                    subject = notification.get("subject", {})
                    repo = notification.get("repository", {})
                    formatted_notifications.append({
                        "id": notification["id"],
                        "reason": notification["reason"],
                        "unread": notification["unread"],
                        "updated_at": notification["updated_at"],
                        "subject_title": subject.get("title"),
                        "subject_type": subject.get("type"),
                        "subject_url": subject.get("url"),
                        "repository": repo.get("full_name"),
                    })
                return {
                    "success": True,
                    "notification_count": len(formatted_notifications),
                    "notifications": formatted_notifications,
                    "message": f"Retrieved {len(formatted_notifications)} notifications",
                }
            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("message", e.response.text)
                return {
                    "success": False,
                    "notifications": [],
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }

    @property
    def issues(self):
        """Return issue-related GitHub tools."""
        return {
            "create_github_issue": self.create_github_issue,
            "get_issue_comments": self.get_issue_comments,
            "reply_to_issue": self.reply_to_issue,
            "get_my_issues": self.get_my_issues,
        }
    
    @property
    def prs(self):
        """Return pull request-related GitHub tools."""
        return {
            "pr_to_github": self.pr_to_github,
            "list_open_pull_requests": self.list_open_pull_requests,
            "get_pull_request": self.get_pull_request,
            "get_pr_files": self.get_pr_files,
            "get_pr_check_summary": self.get_pr_check_summary,
            "get_pr_reviews": self.get_pr_reviews,
            "get_pr_review_comments": self.get_pr_review_comments,
            "reply_to_pr_review_comment": self.reply_to_pr_review_comment,
            "get_pr_comments": self.get_pr_comments,
            "reply_to_pr": self.reply_to_pr,
            "create_pr_review": self.create_pr_review,
            "get_my_open_prs": self.get_my_open_prs,
        }


    @property
    def admin_prs(self):
        """Return administrator-only pull request tools."""
        return {
            "merge_pr": self.merge_pr,
        }


    @property
    def notifications(self):
        """Return notification-related GitHub tools."""
        return {
            "get_notifications": self.get_notifications,
        }


    @property
    def admin_tools(self):
        """Return administrator-only GitHub tools."""
        return {
            **self.admin_prs,
        }


    @property
    def all_tools(self):
        """Return all tools exposed by this toolkit."""
        issues = self.issues
        prs = self.prs
        notifications = self.notifications
        return {
            **issues,
            **prs,
            **notifications,
        }
