from __future__ import annotations

import httpx

from mwin import track

from src.sandbox import Sandbox

class GithubTools:
    """GitHub/git operations bound to a sandbox container."""

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    @track(step_type="tool")
    async def fetch_from_github(
        self,
        repo_url: str,
        local_path: str,
        branch: str = "main",
        token: str | None = None,
        upstream_url: str | None = None,
    ) -> dict:
        """Fetch from github.
        repo_url should always be authenticated_url if github_token is provided.
        """

        authenticated_url = repo_url
        expected_repo_url = repo_url
        result: dict | None = None
        message = ""

        check = await self._sandbox.run_shell(
            f"test -d '{local_path}/.git' && echo exists || echo new"
        )

        if "exists" in check.get("stdout", ""):
            remote_result = await self._sandbox.run_shell(
                f"git -C '{local_path}' config --get remote.origin.url"
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
                result = await self._sandbox.run_shell(
                    f"git -C '{local_path}' fetch --all && "
                    f"git -C '{local_path}' checkout {branch} && "
                    f"git -C '{local_path}' pull origin {branch}"
                )
                message = f"Pulled latest on branch '{branch}' at {local_path}"

        if "new" in check.get("stdout", ""):
            result = await self._sandbox.run_shell(
                f"git clone --branch {branch} '{authenticated_url}' '{local_path}'"
            )
            if result.get("success", False) and upstream_url:
                await self._sandbox.run_shell(
                    f"git -C '{local_path}' remote add upstream '{upstream_url}' 2>/dev/null || "
                    f"git -C '{local_path}' remote set-url upstream '{upstream_url}'"
                )
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

    @track(step_type="tool")
    async def create_sub_issue(
        self,
        token: str,
        repo: str,
        issue_number: int,
        sub_issue_number: int,
        replace_parent: bool = False,
    ) -> dict:
        """Create a sub-issue relationship between two issues.

        Resolve sub_issue_number to GitHub's internal issue id first, then
        create the sub-issue relationship.
        """
        async with httpx.AsyncClient() as client:
            try:
                issue_response = await client.get(
                    f"https://api.github.com/repos/{repo}/issues/{sub_issue_number}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                issue_response.raise_for_status()
                issue_data = issue_response.json()
                sub_issue_id = issue_data.get("id")
                if sub_issue_id is None:
                    return {
                        "success": False,
                        "sub_issue_number": None,
                        "sub_issue_url": "",
                        "parent_issue_number": issue_number,
                        "message": f"Could not resolve internal issue id for issue #{sub_issue_number}",
                    }
                if issue_data.get("pull_request"):
                    return {
                        "success": False,
                        "sub_issue_number": None,
                        "sub_issue_url": "",
                        "parent_issue_number": issue_number,
                        "message": f"Issue #{sub_issue_number} is a pull request, not a real issue.",
                    }

                response = await client.post(
                    f"https://api.github.com/repos/{repo}/issues/{issue_number}/sub_issues",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json={
                        "sub_issue_id": sub_issue_id,
                        "replace_parent": replace_parent,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "success": True,
                    "sub_issue_number": data.get("number"),
                    "sub_issue_url": data.get("html_url", ""),
                    "parent_issue_number": issue_number,
                    "message": f"Sub-issue #{data.get('number')} added to issue #{issue_number}: {data.get('html_url', '')}",
                }
            except httpx.HTTPStatusError as e:
                try:
                    error_detail = e.response.json().get("message", e.response.text)
                except Exception:
                    error_detail = e.response.text
                return {
                    "success": False,
                    "sub_issue_number": None,
                    "sub_issue_url": "",
                    "parent_issue_number": issue_number,
                    "message": f"GitHub API error {e.response.status_code}: {error_detail}",
                }
    

    @property
    def issues(self):
        return {
            "get_issue_comments": self.get_issue_comments,
            "reply_to_issue": self.reply_to_issue,
            "get_my_issues": self.get_my_issues,
            "create_sub_issue": self.create_sub_issue,
        }
    
    @property
    def prs(self):
        return {
            "pr_to_github": self.pr_to_github,
            "get_pr_reviews": self.get_pr_reviews,
            "get_pr_review_comments": self.get_pr_review_comments,
            "reply_to_pr_review_comment": self.reply_to_pr_review_comment,
            "get_pr_comments": self.get_pr_comments,
            "reply_to_pr": self.reply_to_pr,
            "get_my_open_prs": self.get_my_open_prs,
        }


    @property
    def notifications(self):
        return {
            "get_notifications": self.get_notifications,
        }

    
    @property
    def all_tools(self):
        issues = self.issues
        prs = self.prs
        notifications = self.notifications
        return {
            **issues,
            **prs,
            **notifications,
        }
