"""Unit tests for TestingToolKit."""

import ast
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.tools.testing import TestingToolKit


@pytest.fixture
def mock_sandbox():
    """Create a mock sandbox for testing."""
    sandbox = AsyncMock()
    sandbox.run_shell = AsyncMock(return_value={"success": True, "stdout": "", "stderr": ""})
    return sandbox


@pytest.fixture
def testing_kit(mock_sandbox):
    """Create a TestingToolKit instance with mock sandbox."""
    return TestingToolKit(mock_sandbox)


def test_parse_test_results_pytest():
    """Test parsing pytest results."""
    kit = TestingToolKit(None)
    
    stdout = """
================================ test session starts ================================
platform linux -- Python 3.12.0, pytest-7.4.0, pluggy-1.2.0
rootdir: /workspace
collected 3 items

test_sample.py::test_add PASSED                                                 [ 33%]
test_sample.py::test_subtract FAILED                                           [ 66%]
test_sample.py::test_multiply SKIPPED                                          [100%]

===================================== FAILURES ======================================
test_sample.py::test_subtract FAILED

AssertionError: assert 1 - 2 == -2

================================= short test summary ================================
FAILED test_sample.py::test_subtract - AssertionError: assert 1 - 2 == -2
3 passed, 1 failed, 2 skipped in 0.12s
"""
    
    results = kit._parse_test_results(stdout, "", "pytest")
    
    assert results["passed"] == 3
    assert results["failed"] == 1
    assert results["skipped"] == 2
    assert results["total"] == 6


def test_count_tests():
    """Test counting test functions."""
    kit = TestingToolKit(None)
    
    code = """
def test_addition():
    assert 1 + 1 == 2

def test_subtraction():
    assert 2 - 1 == 1

class TestCalculator:
    def test_multiplication(self):
        assert 2 * 2 == 4
    
    def test_division(self):
        assert 4 / 2 == 2
        
def not_a_test():
    return 42
"""
    
    test_count = kit._count_tests(ast.parse(code))
    assert test_count == 4  # 2 standalone tests + 2 class methods


def test_count_assertions():
    """Test counting assertion statements."""
    kit = TestingToolKit(None)
    
    code = """
def test_example():
    assert True
    assert 1 == 1
    assert "hello" == "hello"
    
class TestExample:
    def test_method(self):
        self.assertEqual(1, 1)
        self.assertTrue(True)
"""
    
    assertion_count = kit._count_assertions(ast.parse(code))
    assert assertion_count == 5  # 3 assert statements + 2 unittest assertions


@pytest.mark.asyncio
async def test_run_tests_pytest(testing_kit, mock_sandbox):
    """Test running tests with pytest."""
    test_code = """
import pytest

def test_addition():
    assert 1 + 1 == 2

def test_subtraction():
    assert 2 - 1 == 1
"""
    
    # Mock pytest output
    mock_sandbox.run_shell.return_value = {
        "success": True,
        "stdout": "2 passed in 0.01s",
        "stderr": ""
    }
    
    result = await testing_kit.run_tests(test_code, test_framework="pytest")
    
    assert result["success"] is True
    assert "test_results" in result
    assert result["test_framework"] == "pytest"


@pytest.mark.asyncio
async def test_analyze_test_coverage(testing_kit, mock_sandbox):
    """Test test coverage analysis."""
    code = """
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
"""
    
    tests = """
from mymodule import add, subtract

def test_add():
    assert add(1, 2) == 3

def test_subtract():
    assert subtract(5, 3) == 2
"""
    
    # Mock coverage results
    mock_sandbox.run_shell.side_effect = [
        {"success": True, "stdout": "", "stderr": ""},  # coverage run
        {"success": True, "stdout": "TOTAL 100%", "stderr": ""}  # coverage report
    ]
    
    result = await testing_kit.analyze_test_coverage(code, tests, report_type="summary")
    
    assert result["success"] is True
    assert "coverage" in result
    assert result["report_type"] == "summary"


@pytest.mark.asyncio
async def test_generate_tests(testing_kit):
    """Test test generation."""
    code = """
def add(a: int, b: int) -> int:
    return a + b

def greet(name: str) -> str:
    return f"Hello, {name}!"

class Calculator:
    def multiply(self, x: int, y: int) -> int:
        return x * y
"""
    
    result = await testing_kit.generate_tests(code, test_framework="pytest")
    
    assert result["success"] is True
    assert "test_code" in result
    assert result["functions_analyzed"] == 2
    assert result["classes_analyzed"] == 1
    assert "TODO" in result["test_code"]  # Placeholder tests


@pytest.mark.asyncio
async def test_check_test_quality(testing_kit):
    """Test test quality checking."""
    test_code = """
def test_addition():
    assert 1 + 1 == 2

def test_subtraction():
    assert 2 - 1 == 1

def test_with_message():
    assert 1 == 1, "One should equal one"
"""
    
    result = await testing_kit.check_test_quality(test_code)
    
    assert result["success"] is True
    assert "quality_issues" in result
    assert "metrics" in result
    assert "test_count" in result["metrics"]
    assert "assertion_count" in result["metrics"]


@pytest.mark.asyncio
async def test_benchmark_performance(testing_kit, mock_sandbox):
    """Test performance benchmarking."""
    code = """
def calculate_sum(n):
    total = 0
    for i in range(n):
        total += i
    return total
"""
    
    # Mock benchmark output
    mock_sandbox.run_shell.return_value = {
        "success": True,
        "stdout": "Time for 1000 iterations: 0.123456 seconds\nTime per iteration: 0.000123 seconds",
        "stderr": ""
    }
    
    result = await testing_kit.benchmark_performance(code, iterations=1000)
    
    assert result["success"] is True
    assert "benchmark_results" in result
    assert result["benchmark_results"]["iterations"] == 1000


@pytest.mark.asyncio
async def test_profile_code(testing_kit, mock_sandbox):
    """Test code profiling."""
    code = """
def slow_function():
    total = 0
    for i in range(10000):
        total += i
    return total
"""
    
    # Mock profiling output
    mock_sandbox.run_shell.return_value = {
        "success": True,
        "stdout": "Profiling results...\nFunction calls: 10000",
        "stderr": ""
    }
    
    result = await testing_kit.profile_code(code, profiler="cProfile")
    
    assert result["success"] is True
    assert result["profiler"] == "cProfile"
    assert "output" in result


def test_as_tool_kits(testing_kit):
    """Test that all tools are exposed in the toolkit."""
    kits = testing_kit.as_tool_kits()
    
    expected_tools = [
        "RunTests",
        "AnalyzeTestCoverage",
        "GenerateTests",
        "CheckTestQuality",
        "BenchmarkPerformance",
        "ProfileCode",
    ]
    
    for tool in expected_tools:
        assert tool in kits
        assert callable(kits[tool])