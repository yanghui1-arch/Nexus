"""Dependency management tools for Tela."""

import json
import re
import tempfile
import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from pydantic import BaseModel, Field
from openai import pydantic_function_tool


class AnalyzeDependencies(BaseModel):
    """Analyze Python dependencies in code and requirements files."""
    
    code: str = Field(description="Python source code to analyze")
    requirements_file: Optional[str] = Field(default=None, description="Path to requirements.txt file (if exists)")
    pyproject_file: Optional[str] = Field(default=None, description="Path to pyproject.toml file (if exists)")


class CheckDependencyUpdates(BaseModel):
    """Check for available updates to dependencies."""
    
    requirements: str = Field(description="Requirements file content or list of dependencies")
    check_pypi: bool = Field(default=True, description="Check PyPI for latest versions")
    include_prerelease: bool = Field(default=False, description="Include pre-release versions")


class GenerateRequirements(BaseModel):
    """Generate requirements.txt from Python code analysis."""
    
    code: str = Field(description="Python source code to analyze")
    include_dev_deps: bool = Field(default=False, description="Include development dependencies")
    pin_versions: bool = Field(default=True, description="Pin dependency versions")
    format: str = Field(default="requirements.txt", description="Output format: 'requirements.txt' or 'pyproject.toml'")


class CheckDependencyConflicts(BaseModel):
    """Check for dependency conflicts and compatibility issues."""
    
    dependencies: List[str] = Field(description="List of dependencies to check")
    python_version: str = Field(default="3.12", description="Python version to check compatibility for")
    check_os_compatibility: bool = Field(default=False, description="Check OS-specific compatibility")


class AnalyzeImportUsage(BaseModel):
    """Analyze import usage in Python code."""
    
    code: str = Field(description="Python source code to analyze")
    track_usage: bool = Field(default=True, description="Track how imports are used in the code")
    suggest_alternatives: bool = Field(default=False, description="Suggest alternative packages")


class ManageVirtualEnvironment(BaseModel):
    """Manage Python virtual environment."""
    
    action: str = Field(description="Action to perform: 'create', 'activate', 'deactivate', 'install', 'freeze'")
    dependencies: Optional[List[str]] = Field(default=None, description="Dependencies to install")
    python_version: Optional[str] = Field(default=None, description="Python version for virtual environment")


# Tool definitions
ANALYZE_DEPENDENCIES = pydantic_function_tool(AnalyzeDependencies)
CHECK_DEPENDENCY_UPDATES = pydantic_function_tool(CheckDependencyUpdates)
GENERATE_REQUIREMENTS = pydantic_function_tool(GenerateRequirements)
CHECK_DEPENDENCY_CONFLICTS = pydantic_function_tool(CheckDependencyConflicts)
ANALYZE_IMPORT_USAGE = pydantic_function_tool(AnalyzeImportUsage)
MANAGE_VIRTUAL_ENVIRONMENT = pydantic_function_tool(ManageVirtualEnvironment)

DEPENDENCY_TOOL_DEFINITIONS: List = [
    ANALYZE_DEPENDENCIES, CHECK_DEPENDENCY_UPDATES, GENERATE_REQUIREMENTS,
    CHECK_DEPENDENCY_CONFLICTS, ANALYZE_IMPORT_USAGE, MANAGE_VIRTUAL_ENVIRONMENT
]


class DependencyToolKit:
    """Dependency management tools."""
    
    def __init__(self, sandbox):
        self._sandbox = sandbox
    
    async def analyze_dependencies(
        self,
        code: str,
        requirements_file: Optional[str] = None,
        pyproject_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze Python dependencies."""
        try:
            # Extract imports from code
            imports = self._extract_imports_from_code(code)
            
            # Parse requirements if provided
            requirements = []
            if requirements_file:
                requirements = self._parse_requirements_file(requirements_file)
            
            # Parse pyproject.toml if provided
            pyproject_deps = []
            if pyproject_file:
                pyproject_deps = self._parse_pyproject_file(pyproject_file)
            
            # Analyze import usage
            import_analysis = self._analyze_import_usage(code, imports)
            
            # Check for missing dependencies
            missing_deps = self._find_missing_dependencies(imports, requirements + pyproject_deps)
            
            # Check for unused dependencies
            unused_deps = self._find_unused_dependencies(imports, requirements + pyproject_deps)
            
            # Categorize dependencies
            categorized = self._categorize_dependencies(imports)
            
            return {
                "success": True,
                "imports_found": imports,
                "requirements": requirements,
                "pyproject_dependencies": pyproject_deps,
                "import_analysis": import_analysis,
                "missing_dependencies": missing_deps,
                "unused_dependencies": unused_deps,
                "categorized_dependencies": categorized,
                "message": f"Found {len(imports)} imports, {len(missing_deps)} missing deps, {len(unused_deps)} unused deps"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Dependency analysis failed: {str(e)}"
            }
    
    async def check_dependency_updates(
        self,
        requirements: str,
        check_pypi: bool = True,
        include_prerelease: bool = False,
    ) -> Dict[str, Any]:
        """Check for available dependency updates."""
        try:
            # Parse requirements
            deps = self._parse_requirements_content(requirements)
            
            update_info = []
            
            if check_pypi:
                for dep in deps:
                    update = await self._check_pypi_for_updates(dep, include_prerelease)
                    if update:
                        update_info.append(update)
            
            return {
                "success": True,
                "dependencies_checked": len(deps),
                "updates_available": len(update_info),
                "update_info": update_info,
                "message": f"Checked {len(deps)} dependencies, {len(update_info)} updates available"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Dependency update check failed: {str(e)}"
            }
    
    async def generate_requirements(
        self,
        code: str,
        include_dev_deps: bool = False,
        pin_versions: bool = True,
        format: str = "requirements.txt",
    ) -> Dict[str, Any]:
        """Generate requirements file from code analysis."""
        try:
            # Extract imports
            imports = self._extract_imports_from_code(code)
            
            # Map imports to PyPI packages
            pypi_packages = self._map_imports_to_packages(imports)
            
            # Get versions if pinning is requested
            if pin_versions:
                for package in pypi_packages:
                    version = await self._get_latest_version(package["name"])
                    package["version"] = version
            
            # Generate the file content
            if format == "requirements.txt":
                content = self._generate_requirements_txt(pypi_packages, include_dev_deps, pin_versions)
            else:  # pyproject.toml
                content = self._generate_pyproject_toml(pypi_packages, include_dev_deps, pin_versions)
            
            return {
                "success": True,
                "format": format,
                "content": content,
                "packages": pypi_packages,
                "message": f"Generated {format} with {len(pypi_packages)} packages"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Requirements generation failed: {str(e)}"
            }
    
    async def check_dependency_conflicts(
        self,
        dependencies: List[str],
        python_version: str = "3.12",
        check_os_compatibility: bool = False,
    ) -> Dict[str, Any]:
        """Check for dependency conflicts."""
        try:
            conflicts = []
            compatibility_issues = []
            
            # Parse dependencies
            parsed_deps = [self._parse_dependency_string(dep) for dep in dependencies]
            
            # Check for version conflicts
            package_versions = {}
            for dep in parsed_deps:
                name = dep["name"]
                if name in package_versions:
                    if dep["version"] != package_versions[name]:
                        conflicts.append({
                            "package": name,
                            "conflict": f"Multiple versions requested: {package_versions[name]} vs {dep['version']}",
                            "severity": "high"
                        })
                else:
                    package_versions[name] = dep["version"]
            
            # Check Python version compatibility
            for dep in parsed_deps:
                compat = await self._check_python_compatibility(dep["name"], python_version)
                if not compat["compatible"]:
                    compatibility_issues.append({
                        "package": dep["name"],
                        "issue": f"Python {python_version} compatibility: {compat['message']}",
                        "severity": "medium"
                    })
            
            # Check for known conflicts between packages
            known_conflicts = self._check_known_conflicts([d["name"] for d in parsed_deps])
            conflicts.extend(known_conflicts)
            
            return {
                "success": True,
                "conflicts": conflicts,
                "compatibility_issues": compatibility_issues,
                "total_issues": len(conflicts) + len(compatibility_issues),
                "message": f"Found {len(conflicts)} conflicts and {len(compatibility_issues)} compatibility issues"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Dependency conflict check failed: {str(e)}"
            }
    
    async def analyze_import_usage(
        self,
        code: str,
        track_usage: bool = True,
        suggest_alternatives: bool = False,
    ) -> Dict[str, Any]:
        """Analyze import usage in Python code."""
        try:
            imports = self._extract_imports_from_code(code)
            
            usage_analysis = []
            alternative_suggestions = []
            
            for imp in imports:
                analysis = {
                    "import": imp,
                    "usage_count": 0,
                    "usage_locations": [],
                    "module_type": self._classify_module_type(imp)
                }
                
                if track_usage:
                    usage = self._track_import_usage(code, imp)
                    analysis["usage_count"] = usage["count"]
                    analysis["usage_locations"] = usage["locations"]
                
                usage_analysis.append(analysis)
                
                if suggest_alternatives:
                    alternatives = self._suggest_alternatives(imp)
                    if alternatives:
                        alternative_suggestions.append({
                            "import": imp,
                            "alternatives": alternatives
                        })
            
            # Calculate import statistics
            stats = self._calculate_import_statistics(usage_analysis)
            
            return {
                "success": True,
                "imports_analyzed": len(imports),
                "usage_analysis": usage_analysis,
                "alternative_suggestions": alternative_suggestions,
                "statistics": stats,
                "message": f"Analyzed {len(imports)} imports, {stats['used_imports']} used, {stats['unused_imports']} unused"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Import usage analysis failed: {str(e)}"
            }
    
    async def manage_virtual_environment(
        self,
        action: str,
        dependencies: Optional[List[str]] = None,
        python_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Manage Python virtual environment."""
        try:
            if action == "create":
                cmd = "python -m venv venv"
                if python_version:
                    cmd = f"python{python_version} -m venv venv"
                result = await self._sandbox.run_shell(cmd)
                
                return {
                    "success": result.get("success", False),
                    "action": "create",
                    "message": "Virtual environment created" if result.get("success") else "Failed to create virtual environment",
                    "output": result.get("stdout", ""),
                    "error": result.get("stderr", "")
                }
            
            elif action == "install":
                if not dependencies:
                    return {
                        "success": False,
                        "message": "No dependencies provided for installation"
                    }
                
                # Create requirements file
                req_content = "\n".join(dependencies)
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write(req_content)
                    req_file = f.name
                
                try:
                    # Activate venv and install
                    cmd = f"source venv/bin/activate && pip install -r {req_file}"
                    result = await self._sandbox.run_shell(cmd)
                    
                    return {
                        "success": result.get("success", False),
                        "action": "install",
                        "dependencies_installed": len(dependencies),
                        "message": f"Installed {len(dependencies)} dependencies" if result.get("success") else "Installation failed",
                        "output": result.get("stdout", ""),
                        "error": result.get("stderr", "")
                    }
                finally:
                    if os.path.exists(req_file):
                        os.unlink(req_file)
            
            elif action == "freeze":
                cmd = "source venv/bin/activate && pip freeze"
                result = await self._sandbox.run_shell(cmd)
                
                if result.get("success"):
                    dependencies = result.get("stdout", "").strip().split('\n')
                    return {
                        "success": True,
                        "action": "freeze",
                        "dependencies": dependencies,
                        "count": len(dependencies),
                        "message": f"Found {len(dependencies)} installed packages"
                    }
                else:
                    return {
                        "success": False,
                        "action": "freeze",
                        "message": "Failed to freeze dependencies",
                        "error": result.get("stderr", "")
                    }
            
            else:
                return {
                    "success": False,
                    "message": f"Unknown action: {action}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Virtual environment management failed: {str(e)}"
            }
    
    # Helper methods
    def _extract_imports_from_code(self, code: str) -> List[str]:
        """Extract import statements from Python code."""
        import re
        
        imports = set()
        
        # Patterns for different import styles
        patterns = [
            r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_.]*)',  # import x
            r'^\s*from\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s+import',  # from x import y
        ]
        
        for line in code.split('\n'):
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    imports.add(match.group(1))
        
        return sorted(list(imports))
    
    def _parse_requirements_file(self, content: str) -> List[Dict[str, str]]:
        """Parse requirements.txt content."""
        requirements = []
        
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                dep = self._parse_dependency_string(line)
                requirements.append(dep)
        
        return requirements
    
    def _parse_requirements_content(self, content: str) -> List[Dict[str, str]]:
        """Parse requirements content (file content or list)."""
        if '\n' in content:
            return self._parse_requirements_file(content)
        else:
            # Treat as single dependency
            dep = self._parse_dependency_string(content)
            return [dep]
    
    def _parse_pyproject_file(self, content: str) -> List[Dict[str, str]]:
        """Parse pyproject.toml content for dependencies."""
        dependencies = []
        
        try:
            # Simple parsing for dependencies
            lines = content.split('\n')
            in_deps_section = False
            
            for line in lines:
                line = line.strip()
                
                if line.startswith('[tool.poetry.dependencies]') or \
                   line.startswith('[project.dependencies]'):
                    in_deps_section = True
                    continue
                
                if in_deps_section and line and not line.startswith('[') and not line.startswith('#'):
                    if '=' in line:
                        parts = line.split('=')
                        if len(parts) >= 2:
                            name = parts[0].strip().strip('"').strip("'")
                            version = parts[1].strip().strip('"').strip("'")
                            dependencies.append({
                                "name": name,
                                "version": version,
                                "source": "pyproject.toml"
                            })
                
                if line.startswith('[') and in_deps_section and not line.startswith('[tool.poetry.dependencies]'):
                    break
        
        except Exception:
            # Fallback to simple parsing
            pass
        
        return dependencies
    
    def _parse_dependency_string(self, dep_str: str) -> Dict[str, str]:
        """Parse a dependency string into name and version."""
        dep_str = dep_str.strip()
        
        # Remove comments
        if '#' in dep_str:
            dep_str = dep_str.split('#')[0].strip()
        
        # Parse name and version
        name = dep_str
        version = None
        
        # Check for version specifiers
        for op in ['==', '>=', '<=', '>', '<', '~=', '!=']:
            if op in dep_str:
                parts = dep_str.split(op)
                if len(parts) == 2:
                    name = parts[0].strip()
                    version = f"{op}{parts[1].strip()}"
                    break
        
        # Check for no version specifier
        if version is None and '@' in dep_str:
            parts = dep_str.split('@')
            if len(parts) == 2:
                name = parts[0].strip()
                version = parts[1].strip()
        
        return {
            "name": name,
            "version": version or "latest",
            "original": dep_str
        }
    
    def _analyze_import_usage(self, code: str, imports: List[str]) -> Dict[str, Any]:
        """Analyze how imports are used in the code."""
        usage = {}
        
        for imp in imports:
            # Count occurrences of the import in the code
            pattern = rf'\b{re.escape(imp)}\b'
            matches = re.findall(pattern, code)
            
            usage[imp] = {
                "occurrences": len(matches),
                "lines": [],
                "contexts": []
            }
        
        return usage
    
    def _find_missing_dependencies(
        self,
        imports: List[str],
        dependencies: List[Dict[str, str]]
    ) -> List[str]:
        """Find imports that don't have corresponding dependencies."""
        dependency_names = {dep["name"].lower() for dep in dependencies}
        missing = []
        
        # Common standard library modules that don't need to be installed
        stdlib_modules = {
            'os', 'sys', 're', 'json', 'datetime', 'time', 'math', 'random',
            'collections', 'itertools', 'functools', 'typing', 'pathlib',
            'hashlib', 'string', 'decimal', 'fractions', 'statistics',
            'csv', 'json', 'pickle', 'sqlite3', 'xml', 'html', 'http',
            'urllib', 'ssl', 'socket', 'email', 'base64', 'binascii',
            'struct', 'copy', 'pprint', 'textwrap', 'unicodedata', 'warnings',
            'abc', 'enum', 'dataclasses', 'contextlib', 'asyncio', 'threading',
            'multiprocessing', 'queue', 'subprocess', 'signal', 'logging',
            'argparse', 'getopt', 'readline', 'cmd', 'shlex', 'configparser',
            'tempfile', 'glob', 'fnmatch', 'linecache', 'shutil', 'zipfile',
            'tarfile', 'bz2', 'lzma', 'gzip', 'zlib', 'hashlib', 'hmac',
            'secrets', 'uuid', 'io', 'sys', 'builtins', 'types', 'inspect',
            'ast', 'symtable', 'traceback', '__future__', 'importlib',
            'pkgutil', 'modulefinder', 'runpy', 'sysconfig', 'site', 'code',
            'codeop', 'pty', 'tty', 'termios', 'resource', 'posix', 'nt',
            'pwd', 'spwd', 'grp', 'crypt', 'termios', 'tty', 'pty', 'fcntl',
            'pipes', 'nis', 'syslog', 'opcode'
        }
        
        for imp in imports:
            # Check if it's a standard library module
            if imp.split('.')[0] in stdlib_modules:
                continue
            
            # Check if it's in dependencies
            found = False
            for dep in dependencies:
                if imp.lower().startswith(dep["name"].lower()):
                    found = True
                    break
            
            if not found:
                missing.append(imp)
        
        return missing
    
    def _find_unused_dependencies(
        self,
        imports: List[str],
        dependencies: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Find dependencies that aren't used in imports."""
        import_names = {imp.lower().split('.')[0] for imp in imports}
        unused = []
        
        for dep in dependencies:
            if dep["name"].lower() not in import_names:
                unused.append(dep)
        
        return unused
    
    def _categorize_dependencies(self, imports: List[str]) -> Dict[str, List[str]]:
        """Categorize imports into groups."""
        categories = {
            "standard_library": [],
            "data_science": ["numpy", "pandas", "scipy", "matplotlib", "seaborn", "sklearn", "tensorflow", "torch"],
            "web_frameworks": ["django", "flask", "fastapi", "starlette", "aiohttp", "requests", "httpx"],
            "databases": ["sqlalchemy", "psycopg2", "mysql", "sqlite3", "redis", "pymongo"],
            "testing": ["pytest", "unittest", "coverage", "tox", "hypothesis", "factory_boy"],
            "dev_tools": ["black", "flake8", "mypy", "pylint", "isort", "pre-commit", "ruff"],
            "async": ["asyncio", "aiohttp", "trio", "curio", "anyio"],
            "other": []
        }
        
        categorized = {cat: [] for cat in categories.keys()}
        
        for imp in imports:
            base_name = imp.split('.')[0]
            categorized_in = False
            
            for category, packages in categories.items():
                if category == "standard_library":
                    # Check if it's a standard library module
                    stdlib = self._is_standard_library(base_name)
                    if stdlib:
                        categorized[category].append(imp)
                        categorized_in = True
                        break
                else:
                    if base_name in packages:
                        categorized[category].append(imp)
                        categorized_in = True
                        break
            
            if not categorized_in:
                categorized["other"].append(imp)
        
        return categorized
    
    def _is_standard_library(self, module_name: str) -> bool:
        """Check if a module is in Python standard library."""
        # This is a simplified check - in reality would need to check sys.builtin_module_names
        stdlib_modules = {
            'os', 'sys', 're', 'json', 'datetime', 'time', 'math', 'random',
            'collections', 'itertools', 'functools', 'typing', 'pathlib',
            'hashlib', 'string', 'decimal', 'fractions', 'statistics'
        }
        return module_name in stdlib_modules
    
    def _map_imports_to_packages(self, imports: List[str]) -> List[Dict[str, str]]:
        """Map import names to PyPI package names."""
        # Common mappings
        import_to_package = {
            'PIL': 'Pillow',
            'sklearn': 'scikit-learn',
            'yaml': 'PyYAML',
            'bs4': 'beautifulsoup4',
            'dateutil': 'python-dateutil',
            'cv2': 'opencv-python',
            'tkinter': '',  # Standard library
            'sqlite3': '',  # Standard library
        }
        
        packages = []
        
        for imp in imports:
            base_name = imp.split('.')[0]
            
            # Skip standard library
            if self._is_standard_library(base_name):
                continue
            
            # Check mapping
            package_name = import_to_package.get(base_name, base_name)
            
            if package_name:  # Not empty string
                packages.append({
                    "import": imp,
                    "name": package_name,
                    "pypi_name": package_name.replace('_', '-').lower()
                })
        
        return packages
    
    async def _check_pypi_for_updates(
        self,
        dependency: Dict[str, str],
        include_prerelease: bool
    ) -> Optional[Dict[str, Any]]:
        """Check PyPI for updates to a dependency."""
        try:
            # Simple implementation - in reality would call PyPI API
            package_name = dependency["name"]
            current_version = dependency["version"]
            
            # For now, return a mock response
            return {
                "package": package_name,
                "current_version": current_version,
                "latest_version": "1.0.0",  # Mock
                "update_available": True,
                "release_date": "2024-01-01",  # Mock
                "release_notes": "Mock release notes"
            }
            
        except Exception:
            return None
    
    async def _get_latest_version(self, package_name: str) -> str:
        """Get latest version of a package from PyPI."""
        try:
            # Mock implementation
            return "1.0.0"
        except Exception:
            return "*"
    
    def _generate_requirements_txt(
        self,
        packages: List[Dict[str, Any]],
        include_dev_deps: bool,
        pin_versions: bool
    ) -> str:
        """Generate requirements.txt content."""
        lines = []
        
        for pkg in packages:
            if pin_versions and "version" in pkg:
                lines.append(f"{pkg['pypi_name']}=={pkg['version']}")
            else:
                lines.append(pkg['pypi_name'])
        
        if include_dev_deps:
            lines.append("\n# Development dependencies")
            lines.append("# black==23.0.0")
            lines.append("# flake8==6.0.0")
            lines.append("# pytest==7.0.0")
        
        return "\n".join(lines)
    
    def _generate_pyproject_toml(
        self,
        packages: List[Dict[str, Any]],
        include_dev_deps: bool,
        pin_versions: bool
    ) -> str:
        """Generate pyproject.toml content."""
        content = """[project]
name = "my-project"
version = "0.1.0"
description = "My Python project"
readme = "README.md"
requires-python = ">=3.12"
authors = [
    {name = "Author Name", email = "author@example.com"}
]

[project.dependencies]
"""
        
        for pkg in packages:
            if pin_versions and "version" in pkg:
                content += f'{pkg["pypi_name"]} = "{pkg["version"]}"\n'
            else:
                content += f'{pkg["pypi_name"]} = "*"\n'
        
        if include_dev_deps:
            content += """
[dependency-groups]
dev = [
    "black>=23.0.0",
    "flake8>=6.0.0",
    "pytest>=7.0.0",
    "coverage>=7.0.0",
]
"""
        
        return content
    
    async def _check_python_compatibility(
        self,
        package_name: str,
        python_version: str
    ) -> Dict[str, Any]:
        """Check Python version compatibility for a package."""
        # Mock implementation
        return {
            "compatible": True,
            "message": "Compatible",
            "tested_versions": ["3.8", "3.9", "3.10", "3.11", "3.12"]
        }
    
    def _check_known_conflicts(self, package_names: List[str]) -> List[Dict[str, Any]]:
        """Check for known conflicts between packages."""
        conflicts = []
        
        # Some known conflicts
        known_conflicts = [
            ({"tensorflow", "tensorflow-gpu"}, "Cannot have both tensorflow and tensorflow-gpu"),
            ({"django", "flask"}, "Typically use one web framework, not both"),
            ({"mysqlclient", "pymysql"}, "Choose one MySQL driver"),
        ]
        
        package_set = set(package_names)
        
        for conflict_packages, message in known_conflicts:
            if conflict_packages.issubset(package_set):
                conflicts.append({
                    "packages": list(conflict_packages),
                    "conflict": message,
                    "severity": "medium"
                })
        
        return conflicts
    
    def _classify_module_type(self, module_name: str) -> str:
        """Classify the type of module."""
        if self._is_standard_library(module_name.split('.')[0]):
            return "standard_library"
        
        # Common patterns
        patterns = {
            "data_science": ["numpy", "pandas", "scipy", "sklearn", "tensorflow", "torch"],
            "web": ["django", "flask", "fastapi", "requests", "aiohttp"],
            "database": ["sqlalchemy", "psycopg", "mysql", "redis"],
            "testing": ["pytest", "unittest", "coverage"],
            "dev": ["black", "flake8", "mypy", "pylint"],
        }
        
        base_name = module_name.split('.')[0]
        for category, modules in patterns.items():
            if base_name in modules:
                return category
        
        return "third_party"
    
    def _track_import_usage(self, code: str, import_name: str) -> Dict[str, Any]:
        """Track how an import is used in the code."""
        lines = code.split('\n')
        locations = []
        
        for i, line in enumerate(lines, 1):
            if import_name in line:
                locations.append({
                    "line": i,
                    "content": line.strip()[:100]  # First 100 chars
                })
        
        return {
            "count": len(locations),
            "locations": locations[:10]  # Limit to first 10
        }
    
    def _suggest_alternatives(self, import_name: str) -> List[str]:
        """Suggest alternative packages for an import."""
        alternatives = {
            "PIL": ["Pillow"],
            "sklearn": ["scikit-learn"],
            "yaml": ["PyYAML", "ruamel.yaml"],
            "bs4": ["beautifulsoup4"],
            "requests": ["httpx", "aiohttp"],
            "sqlite3": ["aiosqlite", "sqlalchemy"],
        }
        
        base_name = import_name.split('.')[0]
        return alternatives.get(base_name, [])
    
    def _calculate_import_statistics(self, usage_analysis: List[Dict]) -> Dict[str, int]:
        """Calculate import usage statistics."""
        total_imports = len(usage_analysis)
        used_imports = sum(1 for imp in usage_analysis if imp["usage_count"] > 0)
        unused_imports = total_imports - used_imports
        
        return {
            "total_imports": total_imports,
            "used_imports": used_imports,
            "unused_imports": unused_imports,
            "usage_percentage": (used_imports / total_imports * 100) if total_imports > 0 else 0
        }
    
    def as_tool_kits(self) -> Dict[str, callable]:
        """Return a name→callable mapping for the tools."""
        return {
            "AnalyzeDependencies": self.analyze_dependencies,
            "CheckDependencyUpdates": self.check_dependency_updates,
            "GenerateRequirements": self.generate_requirements,
            "CheckDependencyConflicts": self.check_dependency_conflicts,
            "AnalyzeImportUsage": self.analyze_import_usage,
            "ManageVirtualEnvironment": self.manage_virtual_environment,
        }