# Nexus: Enhanced Tela Agent

Coding automatically as a team in an enterprise level with enhanced AI agent capabilities.

## What's New: Enhanced Tela Agent

Tela, the Python coding agent in Nexus, has been significantly enhanced with:
1. **GitHub Review and Comment Interaction** - Collaborate effectively with team members
2. **Code Analysis Tools** - Comprehensive code quality analysis
3. **Testing Tools** - Execute tests and analyze coverage
4. **Dependency Management Tools** - Manage project dependencies

These enhancements make Tela a more powerful, self-sufficient, and collaborative agent for software development tasks.

## New Enhanced Capabilities

### 1. **GitHub Review and Comment Interaction**
- **GetIssueComments**: Fetch all comments on a GitHub issue
- **ReplyToIssue**: Add a comment to respond to issue discussions
- **GetPRReviews**: Fetch reviews on a pull request (APPROVED, CHANGES_REQUESTED, COMMENTED)
- **GetPRReviewComments**: Fetch inline code review comments on a PR
- **ReplyToPRReviewComment**: Reply to specific inline review comments
- **GetPRComments**: Fetch general discussion comments on a PR
- **ReplyToPR**: Add general comments to PR discussions
- **GetMyOpenPRs**: List your open PRs to track feedback
- **GetMyIssues**: List your issues to check for new comments
- **GetNotifications**: Get GitHub notifications for activity on your contributions

These tools enable Tela to actively participate in code reviews, respond to feedback, and collaborate effectively with team members.

### 2. **Code Analysis Tools**
- **AnalyzeCode**: Comprehensive code quality analysis including complexity, style, and imports
- **LintCode**: Run linters (flake8, pylint, ruff) on Python code
- **CheckTypeHints**: Type checking with mypy
- **CalculateMetrics**: Code metrics calculation (cyclomatic complexity, LOC, Halstead metrics)
- **CheckSecurity**: Security vulnerability detection (SQL injection, command injection, hardcoded secrets)
- **FindDuplicates**: Duplicate code detection

### 3. **Testing Tools**
- **RunTests**: Execute tests with pytest, unittest, or nose
- **AnalyzeTestCoverage**: Test coverage analysis and reporting
- **GenerateTests**: Automatic test case generation
- **CheckTestQuality**: Test code quality assessment
- **BenchmarkPerformance**: Performance benchmarking
- **ProfileCode**: Code profiling with cProfile or other profilers

### 4. **Dependency Management Tools**
- **AnalyzeDependencies**: Dependency analysis from code and requirements files
- **CheckDependencyUpdates**: Check for available dependency updates
- **GenerateRequirements**: Generate requirements.txt from code analysis
- **CheckDependencyConflicts**: Dependency conflict detection
- **AnalyzeImportUsage**: Import usage analysis and alternative suggestions
- **ManageVirtualEnvironment**: Virtual environment management

### 5. **Enhanced Existing Tools**
- **GitHub Operations**: Improved with token injection for authenticated operations
- **Sandbox Operations**: All existing tools remain available
- **Web Operations**: Web fetching and searching capabilities

## Getting Started

### Installation
```bash
# Clone the repository
git clone https://github.com/Nexus-Tela/Nexus.git
cd Nexus

# Install dependencies
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
```

### Environment Setup
Create a `.env` file with:
```bash
NEXUS_API_KEY=your_openai_api_key
NEXUS_BASE_URL=https://api.openai.com/v1  # Optional
NEXUS_MODEL=gpt-4o  # Optional
NEXUS_MAX_CONTEXT=128000  # Optional
NEXUS_MAX_ATTEMPTS=30  # Optional
NEXUS_GITHUB_REPO=owner/repo  # For GitHub operations
NEXUS_GITHUB_TOKEN=your_github_token  # For GitHub operations
```

### Basic Usage
```bash
# Run Tela with a task
python main.py "Your task here"

# Run the GitHub collaboration demo
python examples/github_collaboration_demo.py

# Run the enhanced demo
python examples/enhanced_tela_demo.py
```

### Advanced Usage
```python
from src.agents.tela import Tela

async with Tela.create(
    base_url="https://api.openai.com/v1",
    api_key="your_api_key",
    model="gpt-4o",
    max_context=128000,
    github_repo="owner/repo",
    github_token="your_token"
) as tela:
    result = await tela.work("Your task here")
```

## Enhanced Workflow

Tela now follows an enhanced workflow for software development tasks:

1. **Code Analysis Phase**: Analyze code quality, security, and complexity
2. **Testing Phase**: Generate, run, and analyze tests
3. **Dependency Management Phase**: Analyze and manage project dependencies
4. **Implementation Phase**: Write clean, well-tested code
5. **Quality Assurance Phase**: Verify code quality and security
6. **Documentation Phase**: Generate documentation and reports
7. **Collaboration Phase**: Respond to reviews and participate in discussions

## GitHub Collaboration Workflow

Tela can now actively collaborate with team members through GitHub:

### Starting a Session (Checking for Updates)
```python
# Check for new notifications
notifications = await github_kit.get_notifications(token=token)

# Check your open PRs for new comments
my_prs = await github_kit.get_my_open_prs(
    token=token, repo="owner/repo", creator="your-username"
)

# For each PR with new activity, read the comments
for pr in my_prs["pull_requests"]:
    if pr["review_comments"] > 0:
        reviews = await github_kit.get_pr_reviews(token, repo, pr["number"])
        review_comments = await github_kit.get_pr_review_comments(token, repo, pr["number"])
    if pr["comments"] > 0:
        comments = await github_kit.get_pr_comments(token, repo, pr["number"])
```

### Responding to Code Reviews
```python
# Reply to inline review comments
await github_kit.reply_to_pr_review_comment(
    token=token,
    repo="owner/repo",
    pull_number=42,
    comment_id=12345,
    body="Thanks for the feedback! I've updated the code accordingly."
)

# Add a general response to the PR
await github_kit.reply_to_pr(
    token=token,
    repo="owner/repo",
    pull_number=42,
    body="All review comments have been addressed. Ready for another review!"
)
```

### Participating in Issue Discussions
```python
# Read issue comments
comments = await github_kit.get_issue_comments(token, repo, issue_number=10)

# Respond to the discussion
await github_kit.reply_to_issue(
    token=token,
    repo="owner/repo",
    issue_number=10,
    body="This has been implemented in PR #42. Please review!"
)
```

See `examples/github_collaboration_demo.py` for a complete demonstration.

## Examples

- See `examples/github_collaboration_demo.py` for GitHub collaboration features
- See `examples/enhanced_tela_demo.py` for code analysis, testing, and dependency management features

## Project Structure
```
nexus/
├── src/agents/tela/              # Tela agent implementation
│   ├── agent.py                  # Enhanced Tela agent with all tools
│   └── system_prompt.py          # System prompt
├── src/tools/                    # Enhanced tool implementations
│   ├── code_analysis.py          # Code analysis tools
│   ├── testing.py                # Testing tools
│   ├── dependencies.py           # Dependency management tools
│   ├── sandbox.py                # Sandbox operations
│   ├── web_search.py             # Web operations
│   └── code/github_tools.py      # GitHub operations (including review/comment interaction)
├── tests/tools/                  # Tests for tools
│   ├── test_github_tools.py      # Tests for GitHub tools
│   ├── test_code_analysis.py     # Tests for code analysis tools
│   └── test_testing.py           # Tests for testing tools
├── examples/                     # Usage examples
│   ├── github_collaboration_demo.py  # Demo of GitHub collaboration features
│   └── enhanced_tela_demo.py     # Demo of analysis/testing features
└── main.py                       # Entry point
```

## Running Tests
```bash
# Run all tests
python -m pytest tests/

# Run specific test suites
python -m pytest tests/agents/tela/
python -m pytest tests/tools/
```

## Development

### Adding New Tools
1. Create a new tool module in `src/tools/`
2. Define tool schemas using Pydantic
3. Implement the tool kit class
4. Add tool definitions to `_ALL_TOOL_DEFINITIONS` in `src/agents/tela/agent.py`
5. Register the tool kit in Tela's `__aenter__` method
6. Write comprehensive tests

### Contributing
1. Fork the repository
2. Create a feature branch
3. Add your enhancements
4. Write tests for new functionality
5. Submit a pull request

## License
This project is licensed under the terms included in the LICENSE file.

## Acknowledgments
- OpenAI for the GPT models and API
- The MCP (Model Context Protocol) ecosystem
- All contributors to the Nexus project
