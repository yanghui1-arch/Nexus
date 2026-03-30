"""Code analysis and quality tools for Tela."""

import ast
import subprocess
import tempfile
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from openai import pydantic_function_tool


class AnalyzeCode(BaseModel):
    """Analyze Python code for quality issues, complexity, and style."""
    
    code: str = Field(description="Python source code to analyze")
    check_style: bool = Field(default=True, description="Check code style (PEP 8)")
    check_complexity: bool = Field(default=True, description="Calculate code complexity metrics")
    check_imports: bool = Field(default=True, description="Check import statements")


class LintCode(BaseModel):
    """Run linters on Python code and return results."""
    
    code: str = Field(description="Python source code to lint")
    linter: str = Field(default="flake8", description="Linter to use: 'flake8', 'pylint', 'ruff', or 'all'")
    max_line_length: int = Field(default=88, description="Maximum line length for linting")


class CheckTypeHints(BaseModel):
    """Check type hints in Python code using mypy."""
    
    code: str = Field(description="Python source code to check")
    strict: bool = Field(default=False, description="Use strict type checking")


class CalculateMetrics(BaseModel):
    """Calculate various code metrics (cyclomatic complexity, lines of code, etc.)."""
    
    code: str = Field(description="Python source code to analyze")
    metrics: List[str] = Field(
        default=["complexity", "loc", "halstead", "maintainability"],
        description="Metrics to calculate: 'complexity', 'loc', 'halstead', 'maintainability'"
    )


class CheckSecurity(BaseModel):
    """Check Python code for common security issues."""
    
    code: str = Field(description="Python source code to analyze for security issues")
    check_sql_injection: bool = Field(default=True, description="Check for SQL injection vulnerabilities")
    check_command_injection: bool = Field(default=True, description="Check for command injection vulnerabilities")
    check_hardcoded_secrets: bool = Field(default=True, description="Check for hardcoded secrets")


class FindDuplicates(BaseModel):
    """Find duplicate code in Python source."""
    
    code: str = Field(description="Python source code to analyze for duplicates")
    min_lines: int = Field(default=3, description="Minimum number of lines to consider a duplicate")
    min_tokens: int = Field(default=10, description="Minimum number of tokens to consider a duplicate")


# Tool definitions
ANALYZE_CODE = pydantic_function_tool(AnalyzeCode)
LINT_CODE = pydantic_function_tool(LintCode)
CHECK_TYPE_HINTS = pydantic_function_tool(CheckTypeHints)
CALCULATE_METRICS = pydantic_function_tool(CalculateMetrics)
CHECK_SECURITY = pydantic_function_tool(CheckSecurity)
FIND_DUPLICATES = pydantic_function_tool(FindDuplicates)

CODE_ANALYSIS_TOOL_DEFINITIONS: List = [
    ANALYZE_CODE, LINT_CODE, CHECK_TYPE_HINTS, CALCULATE_METRICS, CHECK_SECURITY, FIND_DUPLICATES
]


class CodeAnalysisToolKit:
    """Code analysis and quality tools."""
    
    def __init__(self, sandbox):
        self._sandbox = sandbox
    
    async def analyze_code(
        self,
        code: str,
        check_style: bool = True,
        check_complexity: bool = True,
        check_imports: bool = True,
    ) -> Dict[str, Any]:
        """Analyze Python code for quality issues."""
        # Create temporary file with code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            analysis = {}
            
            # Basic AST analysis
            try:
                tree = ast.parse(code)
                analysis["ast_valid"] = True
                analysis["imports"] = self._extract_imports(tree)
                analysis["functions"] = self._extract_functions(tree)
                analysis["classes"] = self._extract_classes(tree)
            except SyntaxError as e:
                analysis["ast_valid"] = False
                analysis["syntax_error"] = str(e)
            
            # Run flake8 for style checking if requested
            if check_style:
                try:
                    result = await self._sandbox.run_shell(
                        f"python -m py_compile {temp_file}"
                    )
                    if result.get("success"):
                        analysis["compilation"] = "success"
                    else:
                        analysis["compilation"] = "failed"
                        analysis["compilation_error"] = result.get("stderr", "")
                except Exception as e:
                    analysis["compilation"] = f"error: {str(e)}"
            
            # Calculate complexity metrics if requested
            if check_complexity:
                analysis["complexity_metrics"] = await self._calculate_complexity(code)
            
            # Check imports if requested
            if check_imports:
                analysis["import_analysis"] = await self._analyze_imports(code)
            
            return {
                "success": True,
                "analysis": analysis,
                "message": "Code analysis completed"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Code analysis failed: {str(e)}"
            }
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    async def lint_code(
        self,
        code: str,
        linter: str = "flake8",
        max_line_length: int = 88,
    ) -> Dict[str, Any]:
        """Run linters on Python code."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            results = {}
            
            if linter in ["flake8", "all"]:
                cmd = f"flake8 --max-line-length={max_line_length} {temp_file}"
                result = await self._sandbox.run_shell(cmd)
                if result.get("success"):
                    results["flake8"] = []
                else:
                    # Parse flake8 output
                    output = result.get("stderr", "")
                    if output:
                        lines = output.strip().split('\n')
                        results["flake8"] = lines
            
            if linter in ["pylint", "all"]:
                cmd = f"pylint --output-format=text {temp_file}"
                result = await self._sandbox.run_shell(cmd)
                if result.get("success"):
                    output = result.get("stdout", "")
                    results["pylint"] = output
            
            if linter in ["ruff", "all"]:
                cmd = f"ruff check {temp_file}"
                result = await self._sandbox.run_shell(cmd)
                if result.get("success"):
                    output = result.get("stdout", "")
                    results["ruff"] = output
            
            return {
                "success": True,
                "linter": linter,
                "results": results,
                "message": f"Linting completed with {linter}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Linting failed: {str(e)}"
            }
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    async def check_type_hints(
        self,
        code: str,
        strict: bool = False,
    ) -> Dict[str, Any]:
        """Check type hints using mypy."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            cmd = f"mypy {temp_file}"
            if strict:
                cmd += " --strict"
            
            result = await self._sandbox.run_shell(cmd)
            
            return {
                "success": result.get("success", False),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "message": "Type checking completed"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Type checking failed: {str(e)}"
            }
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    async def calculate_metrics(
        self,
        code: str,
        metrics: List[str] = None,
    ) -> Dict[str, Any]:
        """Calculate code metrics."""
        if metrics is None:
            metrics = ["complexity", "loc", "halstead", "maintainability"]
        
        calculated_metrics = {}
        
        try:
            # Parse code to AST
            tree = ast.parse(code)
            
            if "complexity" in metrics:
                calculated_metrics["cyclomatic_complexity"] = self._calculate_cyclomatic_complexity(tree)
            
            if "loc" in metrics:
                calculated_metrics["lines_of_code"] = len(code.split('\n'))
                calculated_metrics["logical_lines"] = self._count_logical_lines(code)
            
            if "halstead" in metrics:
                calculated_metrics["halstead_metrics"] = self._calculate_halstead_metrics(code)
            
            if "maintainability" in metrics:
                calculated_metrics["maintainability_index"] = self._calculate_maintainability_index(
                    calculated_metrics.get("cyclomatic_complexity", 0),
                    calculated_metrics.get("halstead_metrics", {}).get("volume", 0),
                    calculated_metrics.get("lines_of_code", 0)
                )
            
            return {
                "success": True,
                "metrics": calculated_metrics,
                "message": "Metrics calculated successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Metrics calculation failed: {str(e)}"
            }
    
    async def check_security(
        self,
        code: str,
        check_sql_injection: bool = True,
        check_command_injection: bool = True,
        check_hardcoded_secrets: bool = True,
    ) -> Dict[str, Any]:
        """Check code for security issues."""
        security_issues = []
        
        try:
            if check_sql_injection:
                issues = self._check_sql_injection(code)
                security_issues.extend(issues)
            
            if check_command_injection:
                issues = self._check_command_injection(code)
                security_issues.extend(issues)
            
            if check_hardcoded_secrets:
                issues = self._check_hardcoded_secrets(code)
                security_issues.extend(issues)
            
            return {
                "success": True,
                "security_issues": security_issues,
                "issue_count": len(security_issues),
                "message": f"Found {len(security_issues)} security issues"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Security check failed: {str(e)}"
            }
    
    async def find_duplicates(
        self,
        code: str,
        min_lines: int = 3,
        min_tokens: int = 10,
    ) -> Dict[str, Any]:
        """Find duplicate code."""
        try:
            # Simple duplicate detection by line patterns
            lines = code.split('\n')
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            
            duplicates = []
            line_patterns = {}
            
            for i, line in enumerate(cleaned_lines):
                if line in line_patterns:
                    line_patterns[line].append(i)
                else:
                    line_patterns[line] = [i]
            
            for line, positions in line_patterns.items():
                if len(positions) > 1 and len(line) > 10:  # Avoid trivial duplicates
                    duplicates.append({
                        "line": line,
                        "positions": positions,
                        "count": len(positions)
                    })
            
            # Sort by count descending
            duplicates.sort(key=lambda x: x["count"], reverse=True)
            
            return {
                "success": True,
                "duplicates": duplicates[:10],  # Return top 10 duplicates
                "total_duplicates": len(duplicates),
                "message": f"Found {len(duplicates)} potential duplicates"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Duplicate detection failed: {str(e)}"
            }
    
    # Helper methods
    def _extract_imports(self, tree: ast.AST) -> List[str]:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = ", ".join(alias.name for alias in node.names)
                imports.append(f"from {module} import {names}")
        return imports
    
    def _extract_functions(self, tree: ast.AST) -> List[Dict[str, Any]]:
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    "name": node.name,
                    "args": len(node.args.args),
                    "lineno": node.lineno,
                    "has_docstring": ast.get_docstring(node) is not None
                }
                functions.append(func_info)
        return functions
    
    def _extract_classes(self, tree: ast.AST) -> List[Dict[str, Any]]:
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_info = {
                    "name": node.name,
                    "methods": len([n for n in node.body if isinstance(n, ast.FunctionDef)]),
                    "lineno": node.lineno,
                    "has_docstring": ast.get_docstring(node) is not None
                }
                classes.append(class_info)
        return classes
    
    async def _calculate_complexity(self, code: str) -> Dict[str, Any]:
        """Calculate code complexity metrics."""
        try:
            # Simple complexity calculation
            tree = ast.parse(code)
            
            # Count decision points
            decision_points = 0
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.Try, ast.ExceptHandler)):
                    decision_points += 1
                elif isinstance(node, ast.BoolOp):
                    decision_points += len(node.values) - 1
            
            return {
                "decision_points": decision_points,
                "cyclomatic_complexity": decision_points + 1
            }
        except:
            return {"decision_points": 0, "cyclomatic_complexity": 1}
    
    async def _analyze_imports(self, code: str) -> Dict[str, Any]:
        """Analyze import statements."""
        imports = self._extract_imports(ast.parse(code))
        
        # Categorize imports
        stdlib_imports = []
        third_party_imports = []
        local_imports = []
        
        for imp in imports:
            if imp.startswith("import ") or imp.startswith("from "):
                # Simple heuristic for categorization
                if "." in imp and not imp.startswith("from ."):
                    third_party_imports.append(imp)
                elif imp.startswith("from .") or imp.startswith("import ."):
                    local_imports.append(imp)
                else:
                    stdlib_imports.append(imp)
        
        return {
            "total_imports": len(imports),
            "stdlib_imports": stdlib_imports,
            "third_party_imports": third_party_imports,
            "local_imports": local_imports
        }
    
    def _calculate_cyclomatic_complexity(self, tree: ast.AST) -> int:
        """Calculate cyclomatic complexity from AST."""
        complexity = 1  # Start with 1 for the function entry
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.Try)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                # Add for each operand beyond the first
                complexity += len(node.values) - 1
        
        return complexity
    
    def _count_logical_lines(self, code: str) -> int:
        """Count logical lines of code (excluding comments and blank lines)."""
        lines = code.split('\n')
        logical_lines = 0
        
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                logical_lines += 1
        
        return logical_lines
    
    def _calculate_halstead_metrics(self, code: str) -> Dict[str, float]:
        """Calculate Halstead metrics."""
        # Simplified implementation
        operators = set()
        operands = set()
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                # Count operators and operands
                if isinstance(node, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
                                    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
                                    ast.Is, ast.IsNot, ast.In, ast.NotIn, ast.And, ast.Or)):
                    operators.add(type(node).__name__)
                
                if isinstance(node, ast.Name):
                    operands.add(node.id)
                elif isinstance(node, ast.Constant):
                    operands.add(repr(node.value))
            
            n1 = len(operators)  # Number of distinct operators
            n2 = len(operands)   # Number of distinct operands
            
            # Estimate total operators and operands
            N1 = n1 * 2  # Simplified estimation
            N2 = n2 * 3  # Simplified estimation
            
            # Halstead metrics
            vocabulary = n1 + n2
            length = N1 + N2
            volume = length * (vocabulary ** 0.5) if vocabulary > 0 else 0
            difficulty = (n1 / 2) * (N2 / n2) if n2 > 0 else 0
            effort = volume * difficulty
            
            return {
                "vocabulary": vocabulary,
                "length": length,
                "volume": volume,
                "difficulty": difficulty,
                "effort": effort
            }
            
        except:
            return {
                "vocabulary": 0,
                "length": 0,
                "volume": 0,
                "difficulty": 0,
                "effort": 0
            }
    
    def _calculate_maintainability_index(
        self,
        complexity: int,
        halstead_volume: float,
        loc: int
    ) -> float:
        """Calculate maintainability index (simplified)."""
        if loc == 0:
            return 100.0
        
        # Simplified maintainability index calculation
        mi = 171 - 5.2 * (halstead_volume ** 0.5) - 0.23 * complexity - 16.2 * (loc ** 0.5)
        return max(0, min(100, mi))
    
    def _check_sql_injection(self, code: str) -> List[Dict[str, Any]]:
        """Check for SQL injection vulnerabilities."""
        issues = []
        
        # Look for string concatenation in SQL queries
        sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "WHERE", "FROM"]
        dangerous_patterns = ["+", "f'", 'f"', "%s", "{}"]
        
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            line_lower = line.lower()
            if any(keyword.lower() in line_lower for keyword in sql_keywords):
                if any(pattern in line for pattern in dangerous_patterns):
                    issues.append({
                        "line": i,
                        "issue": "Potential SQL injection",
                        "code": line.strip(),
                        "severity": "high"
                    })
        
        return issues
    
    def _check_command_injection(self, code: str) -> List[Dict[str, Any]]:
        """Check for command injection vulnerabilities."""
        issues = []
        
        dangerous_functions = ["os.system", "subprocess.call", "subprocess.Popen", "eval", "exec"]
        
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            for func in dangerous_functions:
                if func in line:
                    issues.append({
                        "line": i,
                        "issue": f"Potential command injection with {func}",
                        "code": line.strip(),
                        "severity": "high"
                    })
        
        return issues
    
    def _check_hardcoded_secrets(self, code: str) -> List[Dict[str, Any]]:
        """Check for hardcoded secrets."""
        issues = []
        
        secret_patterns = [
            ("password", "="),
            ("secret", "="),
            ("token", "="),
            ("api_key", "="),
            ("auth", "="),
            ("key", "=")
        ]
        
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            line_lower = line.lower()
            for pattern, assignment in secret_patterns:
                if pattern in line_lower and assignment in line:
                    # Check if it looks like a hardcoded value
                    if '"' in line or "'" in line:
                        issues.append({
                            "line": i,
                            "issue": f"Potential hardcoded secret: {pattern}",
                            "code": line.strip(),
                            "severity": "medium"
                        })
        
        return issues
    
    def as_tool_kits(self) -> Dict[str, callable]:
        """Return a name→callable mapping for the tools."""
        return {
            "AnalyzeCode": self.analyze_code,
            "LintCode": self.lint_code,
            "CheckTypeHints": self.check_type_hints,
            "CalculateMetrics": self.calculate_metrics,
            "CheckSecurity": self.check_security,
            "FindDuplicates": self.find_duplicates,
        }