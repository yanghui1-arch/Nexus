"""
GitHub Collaboration Demo for Tela

This example demonstrates how Tela can interact with GitHub reviews and comments
to collaborate effectively with team members.

Usage:
    export NEXUS_API_KEY=your_api_key
    export NEXUS_GITHUB_REPO=owner/repo
    export NEXUS_GITHUB_TOKEN=your_github_token
    python examples/github_collaboration_demo.py
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.code.github_tools import GithubToolKit
from src.sandbox import Sandbox, PYTHON_312


async def demo_github_collaboration():
    """Demonstrate GitHub review and comment interaction capabilities."""
    
    # Get configuration from environment
    token = os.environ.get("NEXUS_GITHUB_TOKEN")
    repo = os.environ.get("NEXUS_GITHUB_REPO", "owner/repo")
    
    if not token:
        print("Error: NEXUS_GITHUB_TOKEN environment variable is required")
        print("Please set your GitHub personal access token")
        sys.exit(1)
    
    print("=" * 70)
    print("GitHub Collaboration Demo for Tela")
    print("=" * 70)
    print(f"\nRepository: {repo}")
    print()
    
    # Create a sandbox and GitHub tool kit
    async with Sandbox(PYTHON_312) as sandbox:
        github_kit = GithubToolKit(sandbox)
        
        # Demo 1: Get Notifications
        print("-" * 70)
        print("1. Getting GitHub Notifications")
        print("-" * 70)
        result = await github_kit.get_notifications(token=token, all=False)
        if result["success"]:
            print(f"Found {result['notification_count']} unread notifications")
            for notif in result["notifications"][:3]:  # Show first 3
                print(f"  - [{notif['reason']}] {notif['subject_title']}")
                print(f"    Repository: {notif['repository']}")
                print(f"    Type: {notif['subject_type']}")
                print()
        else:
            print(f"Error: {result['message']}")
        
        # Demo 2: Get My Open PRs
        print("-" * 70)
        print("2. Getting My Open Pull Requests")
        print("-" * 70)
        # Replace with your actual GitHub username
        username = repo.split("/")[0]  # Using repo owner as example
        result = await github_kit.get_my_open_prs(
            token=token,
            repo=repo,
            creator=username,
            per_page=5
        )
        if result["success"]:
            print(f"Found {result['pr_count']} open PRs by {username}")
            for pr in result["pull_requests"]:
                print(f"  - #{pr['number']}: {pr['title']}")
                print(f"    URL: {pr['html_url']}")
                print(f"    Comments: {pr['comments']}, Review Comments: {pr['review_comments']}")
                print()
        else:
            print(f"Error: {result['message']}")
        
        # Demo 3: Get My Issues
        print("-" * 70)
        print("3. Getting My Issues")
        print("-" * 70)
        result = await github_kit.get_my_issues(
            token=token,
            repo=repo,
            creator=username,
            state="open",
            per_page=5
        )
        if result["success"]:
            print(f"Found {result['issue_count']} open issues by {username}")
            for issue in result["issues"]:
                print(f"  - #{issue['number']}: {issue['title']}")
                print(f"    URL: {issue['html_url']}")
                print(f"    Comments: {issue['comments']}")
                print()
        else:
            print(f"Error: {result['message']}")
        
        # Demo 4: Example workflow for checking PR reviews
        print("-" * 70)
        print("4. Example: Checking PR Reviews and Comments")
        print("-" * 70)
        print("""
To check reviews and comments on a specific PR:

    # Get PR reviews (APPROVED, CHANGES_REQUESTED, COMMENTED)
    reviews = await github_kit.get_pr_reviews(
        token=token,
        repo="owner/repo",
        pull_number=42
    )
    
    # Get inline review comments (line-specific feedback)
    review_comments = await github_kit.get_pr_review_comments(
        token=token,
        repo="owner/repo", 
        pull_number=42
    )
    
    # Get general PR discussion comments
    pr_comments = await github_kit.get_pr_comments(
        token=token,
        repo="owner/repo",
        pull_number=42
    )

Example response structure:
    {
        "success": True,
        "review_count": 2,
        "reviews": [
            {
                "id": 123,
                "user": "reviewer1",
                "state": "CHANGES_REQUESTED",
                "body": "Please fix the indentation",
                ...
            },
            {
                "id": 124,
                "user": "reviewer2",
                "state": "APPROVED",
                "body": "LGTM!",
                ...
            }
        ]
    }
        """)
        
        # Demo 5: Example workflow for responding to feedback
        print("-" * 70)
        print("5. Example: Responding to Reviews and Comments")
        print("-" * 70)
        print("""
To respond to feedback:

    # Reply to an inline review comment
    await github_kit.reply_to_pr_review_comment(
        token=token,
        repo="owner/repo",
        pull_number=42,
        comment_id=12345,
        body="Good point! I'll fix this in the next commit."
    )
    
    # Add a general comment to a PR
    await github_kit.reply_to_pr(
        token=token,
        repo="owner/repo",
        pull_number=42,
        body="Thank you for the review! All comments have been addressed."
    )
    
    # Reply to an issue comment
    await github_kit.reply_to_issue(
        token=token,
        repo="owner/repo",
        issue_number=10,
        body="This issue has been resolved in PR #42."
    )
        """)
        
        # Demo 6: Example workflow for issue comment interaction
        print("-" * 70)
        print("6. Example: Issue Comment Workflow")
        print("-" * 70)
        print("""
To check and respond to issue comments:

    # Get all comments on an issue
    comments = await github_kit.get_issue_comments(
        token=token,
        repo="owner/repo",
        issue_number=10
    )
    
    # Respond to the issue
    await github_kit.reply_to_issue(
        token=token,
        repo="owner/repo",
        issue_number=10,
        body="Thanks for the feedback! I'll look into this."
    )
        """)
    
    print("=" * 70)
    print("Demo completed!")
    print("=" * 70)
    print("""
Summary of New GitHub Collaboration Features:

1. Get Notifications         - Check for new activity on your PRs/issues
2. Get My Open PRs           - List your open PRs to track feedback
3. Get My Issues             - List your issues to check discussions
4. Get PR Reviews            - Read review approvals and feedback
5. Get PR Review Comments    - Read inline code review comments
6. Reply to PR Review        - Respond to inline review comments
7. Get PR Comments           - Read general PR discussion
8. Reply to PR               - Add comments to PR discussions
9. Get Issue Comments        - Read issue comments
10. Reply to Issue           - Respond to issue discussions

These tools enable Tela to:
- Monitor feedback from team members
- Respond to code reviews and discussions
- Participate actively in collaborative development
- Maintain context across sessions by checking notifications

For more details, see the tool definitions in:
    src/tools/code/github_tools.py
    """)


if __name__ == "__main__":
    asyncio.run(demo_github_collaboration())
