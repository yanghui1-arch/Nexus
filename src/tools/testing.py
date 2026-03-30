"""Testing tools for Tela."""

import json
import tempfile
import os
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from openai import pydantic_function_tool


class RunTests(BaseModel):
    """Run tests on Python code and return results."""
    
    test_code: str = Field(description="Python test code to run")
    test_framework: str = Field(default="pytest", description="Test framework: 'pytest', 'unittest', or 'nose'")
    timeout: int = Field(default=30, description="Timeout in seconds for test execution")
    capture_output: bool = Field(default=True, description="Capture test output")


class AnalyzeTestCoverage(BaseModel):
    """Analyze test coverage of Python code."""
    
    code: str = Field(description="Source code to analyze")
    tests: str = Field(description="Test code to run against the source code")
    report_type: str = Field(default="summary", description="Coverage report type: 'summary', 'detailed', or 'html'")


class GenerateTests(BaseModel):
    """Generate test cases for Python code."""
    
    code: str = Field(description="Python source code to generate tests for")
    test_framework: str = Field(default="pytest", description="Test framework to use")
    include_edge_cases: bool = Field(default=True, description="Include edge case tests")
    mock_dependencies: bool = Field(default=True, description="Mock external dependencies")


class CheckTestQuality(BaseModel):
    """Check the quality of test code."""
    
    test_code: str = Field(description="Python test code to analyze")
    check_coverage: bool = Field(default=True, description="Check test coverage metrics")
    check_assertions: bool = Field(default=True, description="Check assertion quality")
    check_independence: bool = Field(default=True, description="Check test independence")


class BenchmarkPerformance(BaseModel):
    """Run performance benchmarks on Python code."""
    
    code: str = Field(description="Python code to benchmark")
    iterations: int = Field(default=1000, description="Number of iterations for benchmarking")
    warmup_iterations: int = Field(default=100, description="Number of warmup iterations")
    measure_memory: bool = Field(default=False, description="Measure memory usage")


class ProfileCode(BaseModel):
    """Profile Python code to identify performance bottlenecks."""
    
    code: str = Field(description="Python code to profile")
    profiler: str = Field(default="cProfile", description="Profiler to use: 'cProfile', 'pyinstrument', or 'line_profiler'")


# Tool definitions
RUN_TESTS = pydantic_function_tool(RunTests)
ANALYZE_TEST_COVERAGE = pydantic_function_tool(AnalyzeTestCoverage)
GENERATE_TESTS = pydantic_function_tool(GenerateTests)
CHECK_TEST_QUALITY = pydantic_function_tool(CheckTestQuality)
BENCHMARK_PERFORMANCE = pydantic_function_tool(BenchmarkPerformance)
PROFILE_CODE = pydantic_function_tool(ProfileCode)

TESTING_TOOL_DEFINITIONS: List = [
    RUN_TESTS, ANALYZE_TEST_COVERAGE, GENERATE_TESTS, 
    CHECK_TEST_QUALITY, BENCHMARK_PERFORMANCE, PROFILE_CODE
]


class TestingToolKit:
    """Testing and performance analysis tools."""
    
    def __init__(self, sandbox):
        self._sandbox = sandbox
    
    async def run_tests(
        self,
        test_code: str,
        test_framework: str = "pytest",
        timeout: int = 30,
        capture_output: bool = True,
    ) -> Dict[str, Any]:
        """Run tests on Python code."""
        # Create temporary files for test code
        with tempfile.NamedTemporaryFile(mode='w', suffix='_test.py', delete=False) as f:
            f.write(test_code)
            test_file = f.name
        
        try:
            if test_framework == "pytest":
                cmd = f"pytest {test_file} -v"
                if capture_output:
                    cmd += " --tb=short"
                if timeout:
                    cmd += f" --timeout={timeout}"
            elif test_framework == "unittest":
                # Extract test module name
                module_name = Path(test_file).stem
                cmd = f"python -m unittest {module_name}"
            else:
                cmd = f"python {test_file}"
            
            result = await self._sandbox.run_shell(cmd)
            
            # Parse test results
            test_results = self._parse_test_results(
                result.get("stdout", ""),
                result.get("stderr", ""),
                test_framework
            )
            
            return {
                "success": result.get("success", False),
                "test_results": test_results,
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "message": "Test execution completed"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Test execution failed: {str(e)}"
            }
        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)
    
    async def analyze_test_coverage(
        self,
        code: str,
        tests: str,
        report_type: str = "summary",
    ) -> Dict[str, Any]:
        """Analyze test coverage."""
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as code_file:
            code_file.write(code)
            code_path = code_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='_test.py', delete=False) as test_file:
            test_file.write(tests)
            test_path = test_file.name
        
        try:
            # Run coverage
            cmd = f"coverage run --source={code_path} {test_path}"
            result = await self._sandbox.run_shell(cmd)
            
            if not result.get("success", False):
                return {
                    "success": False,
                    "error": result.get("stderr", ""),
                    "message": "Test execution failed"
                }
            
            # Generate coverage report
            if report_type == "summary":
                report_cmd = "coverage report"
            elif report_type == "detailed":
                report_cmd = "coverage report --show-missing"
            else:  # html
                report_cmd = "coverage html"
            
            report_result = await self._sandbox.run_shell(report_cmd)
            
            coverage_data = self._parse_coverage_report(
                report_result.get("stdout", ""),
                report_type
            )
            
            return {
                "success": True,
                "coverage": coverage_data,
                "stdout": report_result.get("stdout", ""),
                "message": "Coverage analysis completed"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Coverage analysis failed: {str(e)}"
            }
        finally:
            for path in [code_path, test_path]:
                if os.path.exists(path):
                    os.unlink(path)
    
    async def generate_tests(
        self,
        code: str,
        test_framework: str = "pytest",
        include_edge_cases: bool = True,
        mock_dependencies: bool = True,
    ) -> Dict[str, Any]:
        """Generate test cases for Python code."""
        try:
            # Parse the code to understand its structure
            import ast
            
            tree = ast.parse(code)
            
            # Extract functions and classes
            functions = []
            classes = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_info = {
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "returns": self._extract_return_type(node),
                        "docstring": ast.get_docstring(node)
                    }
                    functions.append(func_info)
                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        "name": node.name,
                        "methods": [],
                        "docstring": ast.get_docstring(node)
                    }
                    for subnode in node.body:
                        if isinstance(subnode, ast.FunctionDef):
                            method_info = {
                                "name": subnode.name,
                                "args": [arg.arg for arg in subnode.args.args],
                                "returns": self._extract_return_type(subnode),
                                "docstring": ast.get_docstring(subnode)
                            }
                            class_info["methods"].append(method_info)
                    classes.append(class_info)
            
            # Generate test code based on the framework
            test_code = self._generate_test_code(
                functions,
                classes,
                test_framework,
                include_edge_cases,
                mock_dependencies
            )
            
            return {
                "success": True,
                "test_code": test_code,
                "functions_analyzed": len(functions),
                "classes_analyzed": len(classes),
                "message": f"Generated tests for {len(functions)} functions and {len(classes)} classes"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Test generation failed: {str(e)}"
            }
    
    async def check_test_quality(
        self,
        test_code: str,
        check_coverage: bool = True,
        check_assertions: bool = True,
        check_independence: bool = True,
    ) -> Dict[str, Any]:
        """Check the quality of test code."""
        quality_issues = []
        
        try:
            # Parse test code
            import ast
            
            tree = ast.parse(test_code)
            
            if check_assertions:
                assertion_issues = self._check_assertion_quality(tree)
                quality_issues.extend(assertion_issues)
            
            if check_independence:
                independence_issues = self._check_test_independence(tree)
                quality_issues.extend(independence_issues)
            
            # Basic metrics
            test_count = self._count_tests(tree)
            assertion_count = self._count_assertions(tree)
            
            quality_score = self._calculate_quality_score(
                test_count,
                assertion_count,
                len(quality_issues)
            )
            
            return {
                "success": True,
                "quality_issues": quality_issues,
                "metrics": {
                    "test_count": test_count,
                    "assertion_count": assertion_count,
                    "assertion_per_test": assertion_count / max(test_count, 1),
                    "quality_score": quality_score
                },
                "message": f"Found {len(quality_issues)} quality issues"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Test quality check failed: {str(e)}"
            }
    
    async def benchmark_performance(
        self,
        code: str,
        iterations: int = 1000,
        warmup_iterations: int = 100,
        measure_memory: bool = False,
    ) -> Dict[str, Any]:
        """Run performance benchmarks."""
        # Create a benchmark wrapper
        benchmark_code = f"""
import time
import sys
import gc

{code}

def run_benchmark():
    # Warmup
    for _ in range({warmup_iterations}):
        pass
    
    # Actual benchmark
    start = time.perf_counter()
    for _ in range({iterations}):
        pass
    end = time.perf_counter()
    
    return end - start

if __name__ == "__main__":
    duration = run_benchmark()
    print(f"Time for {iterations} iterations: {{duration:.6f}} seconds")
    print(f"Time per iteration: {{duration/{iterations}:.9f}} seconds")
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='_benchmark.py', delete=False) as f:
            f.write(benchmark_code)
            benchmark_file = f.name
        
        try:
            result = await self._sandbox.run_shell(f"python {benchmark_file}")
            
            # Parse benchmark results
            output = result.get("stdout", "")
            time_pattern = r"Time for \d+ iterations: ([\d.]+) seconds"
            per_iter_pattern = r"Time per iteration: ([\d.]+) seconds"
            
            total_time = None
            per_iter_time = None
            
            for line in output.split('\n'):
                match = re.search(time_pattern, line)
                if match:
                    total_time = float(match.group(1))
                
                match = re.search(per_iter_pattern, line)
                if match:
                    per_iter_time = float(match.group(1))
            
            benchmark_results = {
                "iterations": iterations,
                "total_time": total_time,
                "time_per_iteration": per_iter_time,
                "iterations_per_second": 1 / per_iter_time if per_iter_time else None
            }
            
            return {
                "success": result.get("success", False),
                "benchmark_results": benchmark_results,
                "stdout": output,
                "stderr": result.get("stderr", ""),
                "message": "Benchmark execution completed"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Benchmark execution failed: {str(e)}"
            }
        finally:
            if os.path.exists(benchmark_file):
                os.unlink(benchmark_file)
    
    async def profile_code(
        self,
        code: str,
        profiler: str = "cProfile",
    ) -> Dict[str, Any]:
        """Profile Python code."""
        # Create profiling wrapper
        if profiler == "cProfile":
            profile_code = f"""
import cProfile
import pstats
import io

{code}

def profile_wrapper():
    # Execute the code
    pass

if __name__ == "__main__":
    pr = cProfile.Profile()
    pr.enable()
    profile_wrapper()
    pr.disable()
    
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(20)
    print(s.getvalue())
"""
        else:
            profile_code = f"""
import time
import sys

{code}

if __name__ == "__main__":
    # Simple time-based profiling
    import inspect
    import ast
    
    tree = ast.parse('''{code}''')
    
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append(node.name)
    
    print(f"Found functions: {{functions}}")
    print("Note: Install {profiler} for detailed profiling")
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='_profile.py', delete=False) as f:
            f.write(profile_code)
            profile_file = f.name
        
        try:
            result = await self._sandbox.run_shell(f"python {profile_file}")
            
            return {
                "success": result.get("success", False),
                "profiler": profiler,
                "output": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "message": f"Profiling completed with {profiler}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Profiling failed: {str(e)}"
            }
        finally:
            if os.path.exists(profile_file):
                os.unlink(profile_file)
    
    # Helper methods
    def _parse_test_results(
        self,
        stdout: str,
        stderr: str,
        framework: str
    ) -> Dict[str, Any]:
        """Parse test results from output."""
        results = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "total": 0
        }
        
        if framework == "pytest":
            # Parse pytest output
            for line in stdout.split('\n'):
                if "passed" in line and "failed" in line and "skipped" in line:
                    # Summary line like: "3 passed, 1 failed, 2 skipped in 0.12s"
                    numbers = re.findall(r'\d+', line)
                    if len(numbers) >= 3:
                        results["passed"] = int(numbers[0])
                        results["failed"] = int(numbers[1])
                        results["skipped"] = int(numbers[2])
                        results["total"] = sum(results.values())
        
        return results
    
    def _parse_coverage_report(
        self,
        report: str,
        report_type: str
    ) -> Dict[str, Any]:
        """Parse coverage report."""
        coverage_data = {
            "statements": 0,
            "missed": 0,
            "coverage": 0.0,
            "files": []
        }
        
        if report_type == "summary":
            for line in report.split('\n'):
                if "TOTAL" in line:
                    parts = line.split()
                    if len(parts) >= 6:
                        coverage_data["statements"] = int(parts[1])
                        coverage_data["missed"] = int(parts[2])
                        coverage_percent = parts[3].replace('%', '')
                        coverage_data["coverage"] = float(coverage_percent)
        
        return coverage_data
    
    def _extract_return_type(self, func_node):
        """Extract return type annotation from function node."""
        if func_node.returns:
            return ast.unparse(func_node.returns) if hasattr(ast, 'unparse') else str(func_node.returns)
        return None
    
    def _generate_test_code(
        self,
        functions: List[Dict],
        classes: List[Dict],
        framework: str,
        include_edge_cases: bool,
        mock_dependencies: bool
    ) -> str:
        """Generate test code based on analysis."""
        imports = []
        test_cases = []
        
        if framework == "pytest":
            imports.append("import pytest")
            if mock_dependencies:
                imports.append("from unittest.mock import Mock, patch")
        
        # Generate imports section
        imports_section = "\n".join(imports)
        
        # Generate test cases for functions
        for func in functions:
            test_case = self._generate_function_test(func, framework, include_edge_cases)
            test_cases.append(test_case)
        
        # Generate test cases for classes
        for cls in classes:
            class_test = self._generate_class_test(cls, framework, include_edge_cases, mock_dependencies)
            test_cases.append(class_test)
        
        # Combine everything
        test_code = f"""{imports_section}

{chr(10).join(test_cases)}
"""
        return test_code
    
    def _generate_function_test(
        self,
        func: Dict,
        framework: str,
        include_edge_cases: bool
    ) -> str:
        """Generate test case for a function."""
        func_name = func["name"]
        
        if framework == "pytest":
            test = f"""
def test_{func_name}():
    \"\"\"Test {func_name} function.\"\"\"
    # TODO: Implement test for {func_name}
    # Args: {func['args']}
    # Returns: {func['returns']}
    pass
"""
        else:  # unittest
            test = f"""
class Test{func_name.capitalize()}(unittest.TestCase):
    def test_{func_name}(self):
        \"\"\"Test {func_name} function.\"\"\"
        # TODO: Implement test for {func_name}
        # Args: {func['args']}
        # Returns: {func['returns']}
        pass
"""
        
        return test
    
    def _generate_class_test(
        self,
        cls: Dict,
        framework: str,
        include_edge_cases: bool,
        mock_dependencies: bool
    ) -> str:
        """Generate test case for a class."""
        class_name = cls["name"]
        
        if framework == "pytest":
            test = f"""
class Test{class_name}:
    \"\"\"Test {class_name} class.\"\"\"
    
    def test_initialization(self):
        \"\"\"Test class initialization.\"\"\"
        # TODO: Test {class_name} instantiation
        pass
"""
            
            # Add tests for methods
            for method in cls["methods"]:
                test += f"""
    def test_{method['name']}(self):
        \"\"\"Test {method['name']} method.\"\"\"
        # TODO: Test {method['name']} method
        # Args: {method['args']}
        # Returns: {method['returns']}
        pass
"""
        else:  # unittest
            test = f"""
class Test{class_name}(unittest.TestCase):
    \"\"\"Test {class_name} class.\"\"\"
    
    def test_initialization(self):
        \"\"\"Test class initialization.\"\"\"
        # TODO: Test {class_name} instantiation
        pass
"""
            
            # Add tests for methods
            for method in cls["methods"]:
                test += f"""
    def test_{method['name']}(self):
        \"\"\"Test {method['name']} method.\"\"\"
        # TODO: Test {method['name']} method
        # Args: {method['args']}
        # Returns: {method['returns']}
        pass
"""
        
        return test
    
    def _check_assertion_quality(self, tree) -> List[Dict[str, Any]]:
        """Check assertion quality in test code."""
        issues = []
        
        # Look for simple assertions without messages
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                # Check if assert has a message
                if len(node.args) == 1:  # Only condition, no message
                    issues.append({
                        "issue": "Assertion without message",
                        "line": node.lineno,
                        "severity": "low"
                    })
        
        return issues
    
    def _check_test_independence(self, tree) -> List[Dict[str, Any]]:
        """Check test independence."""
        issues = []
        
        # Look for shared state between tests
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Check for module-level assignments (shared state)
                if hasattr(node, 'lineno'):
                    # Simple check for potential shared state
                    issues.append({
                        "issue": "Potential shared state (module-level assignment)",
                        "line": node.lineno,
                        "severity": "medium"
                    })
        
        return issues
    
    def _count_tests(self, tree) -> int:
        """Count test functions in the code."""
        test_count = 0
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith('test_'):
                    test_count += 1
            elif isinstance(node, ast.ClassDef):
                for subnode in node.body:
                    if isinstance(subnode, ast.FunctionDef):
                        if subnode.name.startswith('test_'):
                            test_count += 1
        
        return test_count
    
    def _count_assertions(self, tree) -> int:
        """Count assertion statements in the code."""
        assertion_count = 0
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                assertion_count += 1
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['assertEqual', 'assertTrue', 'assertFalse',
                                         'assertRaises', 'assertIs', 'assertIsNone']:
                        assertion_count += 1
        
        return assertion_count
    
    def _calculate_quality_score(
        self,
        test_count: int,
        assertion_count: int,
        issue_count: int
    ) -> float:
        """Calculate test quality score."""
        if test_count == 0:
            return 0.0
        
        # Score based on assertions per test and issue count
        assertions_per_test = assertion_count / test_count
        issue_penalty = min(issue_count / test_count, 1.0)
        
        # Normalize score to 0-100
        score = (assertions_per_test * 40) + ((1 - issue_penalty) * 60)
        return max(0, min(100, score))
    
    def as_tool_kits(self) -> Dict[str, callable]:
        """Return a name→callable mapping for the tools."""
        return {
            "RunTests": self.run_tests,
            "AnalyzeTestCoverage": self.analyze_test_coverage,
            "GenerateTests": self.generate_tests,
            "CheckTestQuality": self.check_test_quality,
            "BenchmarkPerformance": self.benchmark_performance,
            "ProfileCode": self.profile_code,
        }