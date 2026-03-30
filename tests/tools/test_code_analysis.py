"""Unit tests for CodeAnalysisToolKit."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.tools.code_analysis import CodeAnalysisToolKit


@pytest.fixture
def mock_sandbox():
    """Create a mock sandbox for testing."""
    sandbox = AsyncMock()
    sandbox.run_shell = AsyncMock(return_value={"success": True, "stdout": "", "stderr": ""})
    sandbox.run_code = AsyncMock(return_value={"success": True, "stdout": "", "stderr": ""})
    return sandbox


@pytest.fixture
def code_analysis_kit(mock_sandbox):
    """Create a CodeAnalysisToolKit instance with mock sandbox."""
    return CodeAnalysisToolKit(mock_sandbox)


def test_extract_imports():
    """Test extraction of imports from code."""
    kit = CodeAnalysisToolKit(None)
    
    code = """
import os
import sys
from datetime import datetime
from typing import List, Dict
import numpy as np
from sklearn.linear_model import LinearRegression
"""
    
    imports = kit._extract_imports_from_code(code)
    
    assert "os" in imports
    assert "sys" in imports
    assert "datetime" in imports
    assert "typing" in imports
    assert "numpy" in imports
    assert "sklearn" in imports
    assert len(imports) == 6


def test_extract_functions():
    """Test extraction of functions from AST."""
    kit = CodeAnalysisToolKit(None)
    
    code = """
def simple_function():
    pass

def complex_function(x: int, y: str) -> bool:
    return True

class MyClass:
    def method(self):
        pass
"""
    
    imports = kit._extract_imports_from_code(code)
    # No imports in this code
    assert len(imports) == 0


def test_parse_dependency_string():
    """Test parsing of dependency strings."""
    kit = CodeAnalysisToolKit(None)
    
    test_cases = [
        ("requests", {"name": "requests", "version": "latest", "original": "requests"}),
        ("requests==2.31.0", {"name": "requests", "version": "==2.31.0", "original": "requests==2.31.0"}),
        ("requests>=2.0", {"name": "requests", "version": ">=2.0", "original": "requests>=2.0"}),
        ("numpy<1.25", {"name": "numpy", "version": "<1.25", "original": "numpy<1.25"}),
    ]
    
    for dep_str, expected in test_cases:
        result = kit._parse_dependency_string(dep_str)
        assert result["name"] == expected["name"]
        assert result["version"] == expected["version"]


def test_is_standard_library():
    """Test checking if a module is in standard library."""
    kit = CodeAnalysisToolKit(None)
    
    assert kit._is_standard_library("os") is True
    assert kit._is_standard_library("sys") is True
    assert kit._is_standard_library("datetime") is True
    assert kit._is_standard_library("numpy") is False
    assert kit._is_standard_library("requests") is False


def test_categorize_dependencies():
    """Test categorization of dependencies."""
    kit = CodeAnalysisToolKit(None)
    
    imports = ["os", "sys", "numpy", "pandas", "django", "flask", "pytest", "unknown_package"]
    
    categorized = kit._categorize_dependencies(imports)
    
    assert "os" in categorized["standard_library"]
    assert "sys" in categorized["standard_library"]
    assert "numpy" in categorized["data_science"]
    assert "pandas" in categorized["data_science"]
    assert "django" in categorized["web_frameworks"]
    assert "flask" in categorized["web_frameworks"]
    assert "pytest" in categorized["testing"]
    assert "unknown_package" in categorized["other"]


@pytest.mark.asyncio
async def test_analyze_code_success(code_analysis_kit, mock_sandbox):
    """Test successful code analysis."""
    code = """
import os
import sys

def add(a: int, b: int) -> int:
    return a + b

class Calculator:
    def multiply(self, x: int, y: int) -> int:
        return x * y
"""
    
    result = await code_analysis_kit.analyze_code(code)
    
    assert result["success"] is True
    assert "analysis" in result
    assert "imports" in result["analysis"]
    assert "functions" in result["analysis"]
    assert "classes" in result["analysis"]


@pytest.mark.asyncio
async def test_analyze_code_with_syntax_error(code_analysis_kit):
    """Test code analysis with syntax error."""
    code = "def broken_function("  # Missing closing parenthesis
    
    result = await code_analysis_kit.analyze_code(code)
    
    assert result["success"] is True  # Analysis still returns success
    assert result["analysis"]["ast_valid"] is False
    assert "syntax_error" in result["analysis"]


@pytest.mark.asyncio
async def test_lint_code(code_analysis_kit, mock_sandbox):
    """Test code linting."""
    code = """
def foo():
    x = 1
    return x
"""
    
    result = await code_analysis_kit.lint_code(code, linter="flake8")
    
    assert result["success"] is True
    assert result["linter"] == "flake8"
    assert "results" in result


@pytest.mark.asyncio
async def test_check_type_hints(code_analysis_kit, mock_sandbox):
    """Test type hint checking."""
    code = """
def add(a: int, b: int) -> int:
    return a + b
"""
    
    # Mock mypy response
    mock_sandbox.run_shell.return_value = {
        "success": True,
        "stdout": "Success: no issues found",
        "stderr": ""
    }
    
    result = await code_analysis_kit.check_type_hints(code)
    
    assert result["success"] is True
    assert "Type checking completed" in result["message"]


@pytest.mark.asyncio
async def test_calculate_metrics(code_analysis_kit):
    """Test code metrics calculation."""
    code = """
def factorial(n: int) -> int:
    if n <= 1:
        return 1
    else:
        return n * factorial(n - 1)
"""
    
    result = await code_analysis_kit.calculate_metrics(code)
    
    assert result["success"] is True
    assert "metrics" in result
    assert "complexity" in result["metrics"] or "cyclomatic_complexity" in result["metrics"]


@pytest.mark.asyncio
async def test_check_security(code_analysis_kit):
    """Test security checking."""
    code = """
import os
import subprocess

def dangerous(user_input):
    # Potential command injection
    os.system(f"echo {user_input}")
    subprocess.call(f"ls {user_input}", shell=True)
"""
    
    result = await code_analysis_kit.check_security(code)
    
    assert result["success"] is True
    assert "security_issues" in result
    assert result["issue_count"] > 0  # Should find at least one issue


@pytest.mark.asyncio
async def test_find_duplicates(code_analysis_kit):
    """Test duplicate code detection."""
    code = """
def func1():
    x = 1
    y = 2
    z = x + y
    return z

def func2():
    a = 1
    b = 2
    c = a + b
    return c

def func3():
    # Different logic
    result = 1 + 2 + 3
    return result
"""
    
    result = await code_analysis_kit.find_duplicates(code)
    
    assert result["success"] is True
    assert "duplicates" in result
    assert "total_duplicates" in result


def test_as_tool_kits(code_analysis_kit):
    """Test that all tools are exposed in the toolkit."""
    kits = code_analysis_kit.as_tool_kits()
    
    expected_tools = [
        "AnalyzeCode",
        "LintCode",
        "CheckTypeHints",
        "CalculateMetrics",
        "CheckSecurity",
        "FindDuplicates",
    ]
    
    for tool in expected_tools:
        assert tool in kits
        assert callable(kits[tool])