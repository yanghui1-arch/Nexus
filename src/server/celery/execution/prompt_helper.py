from __future__ import annotations

from src.server.postgres.models import (
    GithubPullRequestFeedbackKind,
    GithubPullRequestFeedbackRecord,
    TaskRecord,
    TaskWorkItemRecord,
)


def build_work_item_prompt(
    work_item: TaskWorkItemRecord,
    *,
    is_final_work_item: bool = False,
) -> str:
    """Build the agent prompt for one Nexus work item.

    Args:
        work_item: Work item the agent should implement.
        is_final_work_item: Whether this is the final executable item and the
            agent should create or update the external pull request.

    Returns:
        Prompt text to send to the coding agent.
    """
    external_pr_instruction = (
        "This is the final executable work item. After committing the scoped changes, "
        "create or update exactly one real GitHub pull request for the accumulated "
        "task changes, then call finish_current_task_work_item. "
    ) if is_final_work_item else (
        "Do not create a github pull request for this work item. "
    )

    return (
        f"Implement only this work item {work_item.title}. Commit this work item's scoped changes before finishing; "
        "Nexus records this work item's review scope from base_commit..head_commit. "
        f"{external_pr_instruction}"
        "When the scoped implementation is complete, call finish_current_task_work_item"
    )


def build_github_feedback_prompt(
    task: TaskRecord,
    feedback_items: list[GithubPullRequestFeedbackRecord],
) -> str:
    """Build a resume prompt for pending GitHub feedback.

    Args:
        task: Task that owns the pull request feedback.
        feedback_items: Claimed feedback records to process in one agent turn.

    Returns:
        Prompt text instructing the agent to update the existing PR and reply
        to each feedback item.
    """
    pull_number = feedback_items[0].pull_request_number
    lines = [
        "Continue the current task.",
        f"There is new GitHub feedback on the existing pull request #{pull_number} in {task.repo}.",
        "This is not a new task and you must not open a new pull request.",
        "If code changes are needed, update the existing branch/PR and then reply on GitHub.",
        "If a `pr_merge_conflict` item is present, resolve the merge conflicts locally and push the existing PR branch again.",
        "Use `reply_to_pr` for `pr_comment`, `pr_review`, and `pr_merge_conflict` items.",
        "Use `reply_to_pr_review_comment` for `pr_review_comment` items with the exact `comment_id` shown below.",
        "Handle every feedback item exactly once.",
        "",
        "Feedback items:",
    ]

    for index, item in enumerate(feedback_items, start=1):
        reply_tool = (
            f"reply_to_pr_review_comment(pull_number={pull_number}, comment_id={item.external_id})"
            if item.kind == GithubPullRequestFeedbackKind.pr_review_comment
            else f"reply_to_pr(pull_number={pull_number})"
        )
        summary_parts = [
            f"{index}. kind={item.kind.value}",
            f"github_id={item.external_id}",
            f"reply_with={reply_tool}",
            f"author={item.author or 'unknown'}",
        ]
        if item.review_state:
            summary_parts.append(f"review_state={item.review_state}")
        if item.file_path:
            summary_parts.append(f"file={item.file_path}")
        if item.line is not None:
            summary_parts.append(f"line={item.line}")
        if item.html_url:
            summary_parts.append(f"url={item.html_url}")
        lines.append("; ".join(summary_parts))
        if item.body:
            lines.append(format_github_feedback_message(item))
        lines.append("")

    return "\n".join(lines).rstrip()


def format_github_feedback_message(item: GithubPullRequestFeedbackRecord) -> str:
    """Format one GitHub feedback body for the agent prompt.

    Args:
        item: Feedback record from a pull request comment or review.

    Returns:
        Feedback body wrapped with a short system reminder describing its
        GitHub source.
    """
    reminder_parts = [
        "The following feedback was sent from GitHub",
        f"by `{item.author}`" if item.author else "by an unknown GitHub user",
        f"as `{item.kind.value}`",
    ]
    if item.review_state:
        reminder_parts.append(f"with review state `{item.review_state}`")
    reminder = " ".join(reminder_parts) + "."
    return f"<agent-system-reminder>{reminder}</agent-system-reminder>{item.body}"
