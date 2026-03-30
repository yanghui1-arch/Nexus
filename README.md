# Nexus: Enhanced Tela Agent

Coding automatically as a team in an enterprise level with enhanced AI agent capabilities.

## What's New: Enhanced Tela Agent

Tela, the Python coding agent in Nexus, has been significantly enhanced with new capabilities for code analysis, testing, and dependency management. These enhancements make Tela a more powerful and self-sufficient agent for software development tasks.

## New Enhanced Capabilities

### 1. **Code Analysis Tools**
- **AnalyzeCode**: Comprehensive code quality analysis including complexity, style, and imports
- **LintCode**: Run linters (flake8, pylint, ruff) on Python code
- **CheckTypeHints**: Type checking with mypy
- **CalculateMetrics**: Code metrics calculation (cyclomatic complexity, LOC, Halstead metrics)
- **CheckSecurity**: Security vulnerability detection (SQL injection, command injection, hardcoded secrets)
- **FindDuplicates**: Duplicate code detection

### 2. **Testing Tools**
- **RunTests**: Execute tests with pytest, unittest, or nose
- **AnalyzeTestCoverage**: Test coverage analysis and reporting
- **GenerateTests**: Automatic test case generation
- **CheckTestQuality**: Test code quality assessment
- **BenchmarkPerformance**: Performance benchmarking
- **ProfileCode**: Code profiling with cProfile or other profilers

### 3. **Dependency Management Tools**
- **AnalyzeDependencies**: Dependency analysis from code and requirements files
- **CheckDependencyUpdates**: Check for available dependency updates
- **GenerateRequirements**: Generate requirements.txt from code analysis
- **CheckDependencyConflicts**: Dependency conflict detection
- **AnalyzeImportUsage**: Import usage analysis and alternative suggestions
- **ManageVirtualEnvironment**: Virtual environment management

### 4. **Enhanced Existing Tools**
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
python main.py "Analyze this Python code for quality issues"

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

## Examples

See `examples/enhanced_tela_demo.py` for comprehensive demonstrations of all new capabilities.

## Project Structure
```
nexus/
├── src/agents/tela/              # Tela agent implementation
│   ├── agent.py                  # Enhanced Tela agent with new tools
│   └── system_prompt.py          # Updated system prompt
├── src/tools/                    # Enhanced tool implementations
│   ├── code_analysis.py          # Code analysis tools
│   ├── testing.py                # Testing tools
│   ├── dependencies.py           # Dependency management tools
│   ├── sandbox.py                # Sandbox operations
│   ├── web_search.py             # Web operations
│   └── code/github_tools.py      # GitHub operations
├── tests/tools/                  # Tests for new tools
│   ├── test_code_analysis.py
│   └── test_testing.py
├── examples/                     # Usage examples
│   └── enhanced_tela_demo.py
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
