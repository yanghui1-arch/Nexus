"""
Sophie Demo — Showcase Sophie's React & Web Design capabilities

This example demonstrates Sophie's abilities:
- React development with modern best practices
- Anthropic-style design principles
- Full GitHub workflow integration
- Web research capabilities
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


async def demo_sophie():
    """Demonstrate Sophie's React and design capabilities."""
    from src.agents.sophie import Sophie

    base_url = os.getenv("NEXUS_BASE_URL", "https://api.openai.com/v1")
    api_key = os.getenv("NEXUS_API_KEY")
    model = os.getenv("NEXUS_MODEL", "gpt-4o")
    max_context = int(os.getenv("NEXUS_MAX_CONTEXT", "128000"))
    github_repo = os.getenv("NEXUS_GITHUB_REPO")
    github_token = os.getenv("NEXUS_GITHUB_TOKEN")

    async with Sophie.create(
        base_url=base_url,
        api_key=api_key,
        model=model,
        max_context=max_context,
        github_repo=github_repo,
        github_token=github_token,
    ) as sophie:
        # Example 1: Create a beautiful React component
        print("=" * 60)
        print("Demo 1: Creating a beautiful React button component")
        print("=" * 60)
        result = await sophie.work(
            question="""Create a beautiful, accessible React button component with:
            - Anthropic-style design (clean, thoughtful, human-centered)
            - Multiple variants (primary, secondary, ghost, danger)
            - Loading and disabled states
            - Smooth micro-interactions
            - Full TypeScript support
            - Accessibility features (ARIA labels, keyboard navigation)
            - Save to /workspace/demo/Button.tsx
            """,
            current_session_ctx=[],
            history_session_ctx=[],
        )
        print(f"Response: {result.response}")
        if result.sop:
            print(f"\nSOP: {result.sop}")

        # Example 2: Research design trends
        print("\n" + "=" * 60)
        print("Demo 2: Researching modern React animation libraries")
        print("=" * 60)
        result = await sophie.work(
            question="""Research the best React animation libraries in 2024.
            Compare Framer Motion, React Spring, and GSAP.
            Provide recommendations based on:
            - Performance
            - Ease of use
            - TypeScript support
            - Community adoption
            """,
            current_session_ctx=[],
            history_session_ctx=[],
        )
        print(f"Response: {result.response}")

        # Example 3: GitHub workflow
        if github_repo and github_token:
            print("\n" + "=" * 60)
            print("Demo 3: Checking GitHub activity")
            print("=" * 60)
            result = await sophie.work(
                question=f"""Check my open pull requests and recent issues in {github_repo}.
                Summarize the status of each PR and identify any that need attention.
                """,
                current_session_ctx=[],
                history_session_ctx=[],
            )
            print(f"Response: {result.response}")


if __name__ == "__main__":
    asyncio.run(demo_sophie())
