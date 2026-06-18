from src.tools.code.github.client import GithubTools
from src.tools.code.github.issue import (
    CREATE_GITHUB_ISSUE,
    GET_ISSUE_COMMENTS,
    REPLY_TO_ISSUE,
    GET_MY_ISSUES,
)
from src.tools.code.github.pr import (
    PR_TO_GITHUB,
    GET_PULL_REQUEST,
    LIST_OPEN_PULL_REQUESTS,
    GET_PR_FILES,
    GET_PR_CHECK_SUMMARY,
    GET_PR_REVIEWS,
    GET_PR_REVIEW_COMMENTS,
    REPLY_TO_PR_REVIEW_COMMENT,
    GET_PR_COMMENTS,
    REPLY_TO_PR,
    CREATE_PR_REVIEW,
    MERGE_PR,
    GET_MY_OPEN_PRS,
)
from src.tools.code.github.notification import GET_NOTIFICATIONS

__all__ = [
    "issues",
    "prs",
    "notifications",
    "GithubTools",
]

issues = [CREATE_GITHUB_ISSUE, GET_ISSUE_COMMENTS, REPLY_TO_ISSUE, GET_MY_ISSUES]
prs = [
    PR_TO_GITHUB,
    LIST_OPEN_PULL_REQUESTS,
    GET_PULL_REQUEST,
    GET_PR_FILES,
    GET_PR_CHECK_SUMMARY,
    GET_PR_REVIEWS,
    GET_PR_REVIEW_COMMENTS,
    REPLY_TO_PR_REVIEW_COMMENT,
    GET_PR_COMMENTS,
    REPLY_TO_PR,
    CREATE_PR_REVIEW,
    MERGE_PR,
    GET_MY_OPEN_PRS,
]
notifications = [GET_NOTIFICATIONS]
