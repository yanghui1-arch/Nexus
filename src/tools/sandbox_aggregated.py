"""Aggregated sandbox tools for efficient context gathering.

This module provides high-level tools that combine multiple sandbox operations
into single calls, reducing LLM interaction overhead.
"""

import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from openai import pydantic_function_tool

from src.sandbox import Sandbox


class GetRepoContext(BaseModel):
    """Get comprehensive repository context in a single call.
    
    Returns the file tree structure and optionally the content of key files.
    This reduces multiple list_files and read_file calls into one operation.
    """
    
    repo_path: str = Field(
        default="/workspace",
        description="Root path of the repository"
    )
    max_depth: int = Field(
        default=3,
        description="Maximum directory depth to explore (default: 3)"
    )
    include_content: bool = Field(
        default=True,
        description="Whether to include content of key files (README, pyproject.toml, etc.)"
    )
    max_file_size: int = Field(
        default=50000,
        description="Maximum file size in bytes to read content (default: 50KB)"
    )
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [".git", "__pycache__", "*.pyc", "node_modules", ".venv", "venv", ".pytest_cache"],
        description="Patterns to exclude from the file tree"
    )


class BatchReadFiles(BaseModel):
    """Read multiple files in a single batch operation.
    
    This is more efficient than calling ReadFile multiple times sequentially.
    """
    
    paths: List[str] = Field(
        description="List of absolute file paths to read"
    )
    max_file_size: int = Field(
        default=50000,
        description="Maximum file size in bytes to read content (default: 50KB)"
    )


class FindFilesByPattern(BaseModel):
    """Find files matching a pattern in the repository.
    
    Useful for finding all Python files, test files, etc.
    """
    
    repo_path: str = Field(
        default="/workspace",
        description="Root path to search from"
    )
    pattern: str = Field(
        description="File pattern to match (e.g., '*.py', 'test_*.py')"
    )
    max_results: int = Field(
        default=100,
        description="Maximum number of results to return (default: 100)"
    )


GET_REPO_CONTEXT = pydantic_function_tool(GetRepoContext)
BATCH_READ_FILES = pydantic_function_tool(BatchReadFiles)
FIND_FILES_BY_PATTERN = pydantic_function_tool(FindFilesByPattern)

AGGREGATED_SANDBOX_TOOL_DEFINITIONS = [
    GET_REPO_CONTEXT,
    BATCH_READ_FILES,
    FIND_FILES_BY_PATTERN,
]


class AggregatedSandboxToolKit:
    """High-level sandbox operations that combine multiple basic operations."""
    
    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox
    
    async def get_repo_context(
        self,
        repo_path: str = "/workspace",
        max_depth: int = 3,
        include_content: bool = True,
        max_file_size: int = 50000,
        exclude_patterns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get comprehensive repository context.
        
        Returns a dict with:
        - tree: File/directory structure
        - key_files: Content of important files (README, config files, etc.)
        - stats: Repository statistics
        """
        if exclude_patterns is None:
            exclude_patterns = [".git", "__pycache__", "*.pyc", "node_modules", 
                               ".venv", "venv", ".pytest_cache"]
        
        # Build file tree
        tree = await self._build_file_tree(repo_path, max_depth, exclude_patterns)
        
        result = {
            "tree": tree,
            "key_files": {},
            "stats": {
                "total_files": 0,
                "total_dirs": 0,
                "file_types": {},
            }
        }
        
        # Count stats
        self._count_stats(tree, result["stats"])
        
        # Read key files if requested
        if include_content:
            key_files_to_read = [
                "README.md",
                "README.rst",
                "pyproject.toml",
                "setup.py",
                "setup.cfg",
                "requirements.txt",
                "requirements-dev.txt",
                "package.json",
                "Makefile",
                ".github/workflows",
                "src",
            ]
            
            for key_file in key_files_to_read:
                full_path = os.path.join(repo_path, key_file)
                content = await self._try_read_file(full_path, max_file_size)
                if content:
                    result["key_files"][key_file] = content
        
        return result
    
    async def _build_file_tree(
        self,
        path: str,
        max_depth: int,
        exclude_patterns: List[str],
        current_depth: int = 0,
    ) -> Dict[str, Any]:
        """Recursively build file tree structure."""
        if current_depth > max_depth:
            return {"name": os.path.basename(path), "type": "directory", "truncated": True}
        
        # Check if path should be excluded
        name = os.path.basename(path)
        if self._should_exclude(name, exclude_patterns):
            return None
        
        # List directory contents
        result = await self._sandbox.list_files(path)
        
        if not result.get("success", False):
            return {"name": name, "type": "directory", "error": result.get("error", "Failed to list")}
        
        entries = result.get("files", [])
        children = []
        
        for entry in entries:
            entry_name = entry["name"]
            entry_type = entry["type"]
            
            if self._should_exclude(entry_name, exclude_patterns):
                continue
            
            if entry_type == "directory":
                child_path = os.path.join(path, entry_name)
                child_tree = await self._build_file_tree(
                    child_path, max_depth, exclude_patterns, current_depth + 1
                )
                if child_tree:
                    children.append(child_tree)
            else:
                children.append({
                    "name": entry_name,
                    "type": "file",
                    "size": entry.get("size", 0),
                })
        
        return {
            "name": name or path,
            "type": "directory",
            "children": children,
        }
    
    def _should_exclude(self, name: str, patterns: List[str]) -> bool:
        """Check if a name matches any exclude pattern."""
        import fnmatch
        for pattern in patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        return False
    
    def _count_stats(self, tree: Dict[str, Any], stats: Dict[str, Any]) -> None:
        """Count files and directories in the tree."""
        if tree["type"] == "directory":
            stats["total_dirs"] += 1
            for child in tree.get("children", []):
                self._count_stats(child, stats)
        else:
            stats["total_files"] += 1
            # Count by extension
            name = tree["name"]
            ext = os.path.splitext(name)[1] or "(no extension)"
            stats["file_types"][ext] = stats["file_types"].get(ext, 0) + 1
    
    async def _try_read_file(self, path: str, max_size: int) -> Optional[str]:
        """Try to read a file, return None if it doesn't exist or is too large."""
        result = await self._sandbox.read_file(path)
        
        if not result.get("success", False):
            # Try as directory (for .github/workflows)
            if "/workflows" in path:
                dir_result = await self._sandbox.list_files(path)
                if dir_result.get("success", False):
                    files = dir_result.get("files", [])
                    content_parts = []
                    for f in files:
                        if f["type"] == "file" and f["name"].endswith(".yml", ".yaml"):
                            file_path = os.path.join(path, f["name"])
                            file_result = await self._sandbox.read_file(file_path)
                            if file_result.get("success", False):
                                content = file_result.get("content", "")
                                if len(content) <= max_size:
                                    content_parts.append(f"=== {f['name']} ===\n{content}")
                    return "\n\n".join(content_parts) if content_parts else None
            return None
        
        content = result.get("content", "")
        if len(content) > max_size:
            return content[:max_size] + f"\n... [truncated, file size: {len(content)} bytes]"
        
        return content
    
    async def batch_read_files(
        self,
        paths: List[str],
        max_file_size: int = 50000,
    ) -> Dict[str, Any]:
        """Read multiple files in parallel.
        
        Returns a dict mapping file paths to their content or error message.
        """
        import asyncio
        
        async def read_single(path: str) -> Dict[str, Any]:
            result = await self._sandbox.read_file(path)
            if result.get("success", False):
                content = result.get("content", "")
                if len(content) > max_file_size:
                    content = content[:max_file_size] + f"\n... [truncated, {len(content)} bytes]"
                return {
                    "path": path,
                    "success": True,
                    "content": content,
                    "size": len(content),
                }
            else:
                return {
                    "path": path,
                    "success": False,
                    "error": result.get("error", "Failed to read file"),
                }
        
        # Read all files in parallel
        tasks = [read_single(path) for path in paths]
        results = await asyncio.gather(*tasks)
        
        return {
            "files": {r["path"]: r for r in results},
            "success_count": sum(1 for r in results if r["success"]),
            "failed_count": sum(1 for r in results if not r["success"]),
        }
    
    async def find_files_by_pattern(
        self,
        repo_path: str = "/workspace",
        pattern: str = "*.py",
        max_results: int = 100,
    ) -> Dict[str, Any]:
        """Find files matching a pattern using shell find command."""
        import fnmatch
        
        # First try using find command
        cmd = f"find '{repo_path}' -type f -name '{pattern}' 2>/dev/null | head -n {max_results}"
        result = await self._sandbox.run_shell(cmd)
        
        if result.get("success", False):
            stdout = result.get("stdout", "")
            files = [f.strip() for f in stdout.split("\n") if f.strip()]
            
            return {
                "success": True,
                "pattern": pattern,
                "matches": files,
                "count": len(files),
                "truncated": len(files) >= max_results,
            }
        
        # Fallback: manual search if find fails
        return await self._manual_find(repo_path, pattern, max_results)
    
    async def _manual_find(
        self,
        repo_path: str,
        pattern: str,
        max_results: int,
    ) -> Dict[str, Any]:
        """Manual file search using list_files."""
        import fnmatch
        
        matches = []
        
        async def search_directory(path: str) -> None:
            if len(matches) >= max_results:
                return
            
            result = await self._sandbox.list_files(path)
            if not result.get("success", False):
                return
            
            for entry in result.get("files", []):
                if len(matches) >= max_results:
                    return
                
                entry_name = entry["name"]
                entry_path = os.path.join(path, entry_name)
                
                if entry["type"] == "directory":
                    if entry_name not in [".git", "__pycache__", "node_modules"]:
                        await search_directory(entry_path)
                else:
                    if fnmatch.fnmatch(entry_name, pattern):
                        matches.append(entry_path)
        
        await search_directory(repo_path)
        
        return {
            "success": True,
            "pattern": pattern,
            "matches": matches,
            "count": len(matches),
            "truncated": False,
        }
    
    def as_tool_kits(self) -> Dict[str, Any]:
        """Return tool callables for the aggregated tools."""
        return {
            "GetRepoContext": self.get_repo_context,
            "BatchReadFiles": self.batch_read_files,
            "FindFilesByPattern": self.find_files_by_pattern,
        }
