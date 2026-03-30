"""
Sophie: React Agent Demo

This example demonstrates Sophie's capabilities as a React developer
and web designer with Anthropic-style design expertise.

Usage:
    export NEXUS_API_KEY=your_api_key
    export NEXUS_GITHUB_REPO=owner/repo
    export NEXUS_GITHUB_TOKEN=your_github_token
    python examples/sophie_react_demo.py
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.sophie import Sophie
from src.tools.code.github_tools import GithubToolKit
from src.sandbox import Sandbox, PYTHON_312


async def demo_sophie_react():
    """Demonstrate Sophie's React and design capabilities."""
    
    # Get configuration from environment
    token = os.environ.get("NEXUS_GITHUB_TOKEN")
    repo = os.environ.get("NEXUS_GITHUB_REPO", "owner/repo")
    api_key = os.environ.get("NEXUS_API_KEY")
    base_url = os.environ.get("NEXUS_BASE_URL", "https://api.openai.com/v1")
    
    print("=" * 70)
    print("Sophie: React Agent with Anthropic-Style Design Expertise")
    print("=" * 70)
    print()
    print("Design Philosophy:")
    print("  • Clarity - Interfaces should be self-evident")
    print("  • Craft - Attention to detail in every element")
    print("  • Trust - Transparent and predictable interactions")
    print("  • Thoughtfulness - Every element has purpose")
    print("  • Human-centered - Design for real people")
    print()
    print(f"Repository: {repo}")
    print()
    
    # Demo 1: Sophie Agent Setup
    print("-" * 70)
    print("1. Sophie Agent Setup")
    print("-" * 70)
    
    if not api_key:
        print("Note: NEXUS_API_KEY not set. Showing configuration example:")
        print("""
    sophie = Sophie.create(
        base_url="https://api.openai.com/v1",
        api_key="your-api-key",
        model="gpt-4",
        max_context=8192,
        github_repo="owner/repo",
        github_token="your-github-token",
    )
    
    async with sophie as agent:
        # Sophie is ready to work
        result = await agent.work(question="Create a React component...", ...)
        """)
    else:
        sophie = Sophie.create(
            base_url=base_url,
            api_key=api_key,
            model="gpt-4",
            max_context=8192,
            github_repo=repo,
            github_token=token,
        )
        
        async with sophie as agent:
            print(f"✓ Sophie agent initialized")
            print(f"  - Name: {agent.name}")
            print(f"  - GitHub Nickname: {agent.SOPHIE_GITHUB_NICKNAME}")
            print(f"  - Max Attempts: {agent.max_attempts}")
            print()
            
            # Demo 2: Tool Access
            print("-" * 70)
            print("2. Sophie's Tools")
            print("-" * 70)
            
            tools = list(agent.tool_kits.keys())
            print(f"Sophie has access to {len(tools)} tools:")
            print()
            
            # Sandbox tools
            sandbox_tools = [t for t in tools if t in [
                "RunCode", "RunCommand", "WriteFile", "ReadFile", 
                "AppendFile", "EditFile", "ListFiles"
            ]]
            print(f"  Sandbox Tools ({len(sandbox_tools)}):")
            for tool in sandbox_tools:
                print(f"    • {tool}")
            print()
            
            # GitHub tools
            github_tools = [t for t in tools if t in [
                "FetchFromGithub", "CreateGithubIssue", "PrToGithub",
                "GetIssueComments", "ReplyToIssue", "GetPRReviews",
                "GetPRReviewComments", "ReplyToPRReviewComment",
                "GetPRComments", "ReplyToPR", "GetMyOpenPRs",
                "GetMyIssues", "GetNotifications"
            ]]
            print(f"  GitHub Tools ({len(github_tools)}):")
            for tool in github_tools:
                print(f"    • {tool}")
            print()
            
            # Web tools
            web_tools = [t for t in tools if t in ["WebFetch", "WebSearch"]]
            print(f"  Web Tools ({len(web_tools)}):")
            for tool in web_tools:
                print(f"    • {tool}")
            print()
    
    # Demo 3: Example React Workflow
    print("-" * 70)
    print("3. Example: React Component Development Workflow")
    print("-" * 70)
    print("""
Sophie follows a thoughtful workflow for React development:

    # 1. Research current best practices
    await agent.tool_kits["WebSearch"](query="React 18 best practices 2024")
    
    # 2. Design the component API
    # Sophie thinks about:
    #   - What props does the component need?
    #   - How will developers use this component?
    #   - What are the accessibility requirements?
    
    # 3. Implement with accessibility in mind
    await agent.tool_kits["WriteFile"](
        path="/workspace/src/components/Button.tsx",
        content="""
import React from 'react';

interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'ghost';
  disabled?: boolean;
  'aria-label'?: string;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  onClick,
  variant = 'primary',
  disabled = false,
  'aria-label': ariaLabel,
}) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      className={`btn btn--${variant} ${disabled ? 'btn--disabled' : ''}`}
    >
      {children}
    </button>
  );
};
"""
    )
    
    # 4. Test the component
    await agent.tool_kits["RunCommand"](cmd="npm test Button.test.tsx")
    
    # 5. Refine based on Anthropic design principles
    #   - Check spacing and typography
    #   - Verify keyboard navigation
    #   - Test with screen readers
    """)
    
    # Demo 4: Example GitHub Collaboration
    print("-" * 70)
    print("4. Example: GitHub Collaboration Workflow")
    print("-" * 70)
    print("""
Sophie can collaborate on React projects using GitHub:

    # Create an issue for a new feature
    await agent.tool_kits["CreateGithubIssue"](
        token=token,
        repo="owner/repo",
        title="feat: Add accessible Modal component",
        body="""## Description
        
Create a Modal component following Anthropic design principles:
- Clear focus management
- ESC key to close
- Click outside to close
- Smooth animations
- ARIA attributes for screen readers

## Acceptance Criteria
- [ ] Component accepts title, children, and onClose props
- [ ] Traps focus when open
- [ ] Returns focus to trigger on close
- [ ] Animations respect prefers-reduced-motion
""",
        labels=["enhancement", "accessibility"]
    )
    
    # Clone repository and make changes
    await agent.tool_kits["FetchFromGithub"](
        repo_url="https://github.com/owner/repo",
        local_path="/workspace/project",
        branch="main"
    )
    
    # Write the component
    await agent.tool_kits["WriteFile"](...)
    
    # Create a pull request
    await agent.tool_kits["PrToGithub"](
        token=token,
        repo="owner/repo",
        title="feat: Add accessible Modal component",
        body="Implements the Modal component as described in #<issue_number>.",
        head="feature/add-modal",
        base="main",
        closes_issues=[<issue_number>]
    )
    
    # Respond to review feedback
    await agent.tool_kits["GetPRReviewComments"](
        token=token,
        repo="owner/repo",
        pull_number=42
    )
    
    await agent.tool_kits["ReplyToPRReviewComment"](
        token=token,
        repo="owner/repo",
        pull_number=42,
        comment_id=12345,
        body="Good catch! I'll update the focus trap logic to handle this edge case."
    )
    """)
    
    # Demo 5: Design System Example
    print("-" * 70)
    print("5. Example: Creating a Design System")
    print("-" * 70)
    print("""
Sophie can create comprehensive design systems:

    # Design tokens
    await agent.tool_kits["WriteFile"](
        path="/workspace/src/tokens/colors.ts",
        content="""
// Anthropic-inspired color palette
export const colors = {
  // Primary
  primary: {
    50: '#f0f9ff',
    100: '#e0f2fe',
    500: '#0ea5e9',
    600: '#0284c7',
    700: '#0369a1',
    900: '#0c4a6e',
  },
  // Neutral
  gray: {
    50: '#f9fafb',
    100: '#f3f4f6',
    200: '#e5e7eb',
    300: '#d1d5db',
    400: '#9ca3af',
    500: '#6b7280',
    600: '#4b5563',
    700: '#374151',
    800: '#1f2937',
    900: '#111827',
  },
  // Semantic
  success: '#10b981',
  warning: '#f59e0b',
  error: '#ef4444',
  info: '#3b82f6',
} as const;
"""
    )
    
    # Component library
    await agent.tool_kits["WriteFile"](
        path="/workspace/src/components/index.ts",
        content="""
// Component library exports
export { Button } from './Button';
export { Card } from './Card';
export { Input } from './Input';
export { Modal } from './Modal';
export { Select } from './Select';
export { Tooltip } from './Tooltip';

// Hooks
export { useFocusTrap } from './hooks/useFocusTrap';
export { useOutsideClick } from './hooks/useOutsideClick';
export { useReducedMotion } from './hooks/useReducedMotion';
"""
    )
    """)
    
    print("=" * 70)
    print("Demo completed!")
    print("=" * 70)
    print("""
Summary of Sophie's Capabilities:

1. React Development
   • Modern React (18+) with TypeScript
   • Hooks, Context, and state management
   • Server Components and App Router
   • Performance optimization

2. Web Design
   • Anthropic-inspired design principles
   • Design systems and component libraries
   • Accessibility-first development
   • Responsive design

3. Tools Available
   • Sandbox operations (code execution, file management)
   • Complete GitHub workflow (issues, PRs, reviews)
   • Web search and fetch for research
   • Comment and notification management

4. Design Philosophy
   • Clarity: Self-evident interfaces
   • Craft: Attention to detail
   • Trust: Transparent interactions
   • Thoughtfulness: Purposeful elements
   • Human-centered: Real user needs

Sophie is ready to build beautiful, accessible React applications!
""")


if __name__ == "__main__":
    asyncio.run(demo_sophie_react())
