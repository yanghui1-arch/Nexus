from typing import Callable
from pydantic import BaseModel, Field
from openai import pydantic_function_tool
from mwin import track

from src.sandbox import Sandbox


class RunCode(BaseModel):
    """Execute Python (or the sandbox's default language) code and return stdout/stderr/exit_code."""

    code: str = Field(description="Source code to execute")


class RunCommand(BaseModel):
    """Run a shell command inside the sandbox (e.g. git, pip install, pytest, ls)."""

    cmd: str = Field(description="Shell command string to execute via /bin/sh -c")


class WriteFile(BaseModel):
    """Write (overwrite) a text file at the given path inside the sandbox workspace."""

    path: str = Field(description="Absolute path under /workspace, e.g. /workspace/src/main.py")
    content: str = Field(description="Complete file content to write")


class ReadFile(BaseModel):
    """Read a text file from the sandbox workspace and return its content."""

    path: str = Field(description="Absolute path under /workspace")


class AppendFile(BaseModel):
    """Append text to the end of a file (creates it if it does not exist)."""

    path: str = Field(description="Absolute path under /workspace")
    content: str = Field(description="Text to append")


class EditFile(BaseModel):
    """Replace the first occurrence of old_str with new_str inside a file.
    Use a unique, multi-line old_str to avoid ambiguity.
    """

    path: str = Field(description="Absolute path under /workspace")
    old_str: str = Field(description="Exact substring to find and replace (must be unique in the file)")
    new_str: str = Field(description="Replacement string (may be empty to delete old_str)")


class ListFiles(BaseModel):
    """List files and directories inside a sandbox directory."""

    path: str = Field(default="/workspace", description="Directory path to list (default: /workspace)")


class GetRepoContext(BaseModel):
    """Get comprehensive repository context in a single call.
    
    This tool aggregates multiple operations:
    1. Returns the directory structure (file tree)
    2. Reads content of key files (README, pyproject.toml, etc.)
    3. Returns recently modified files
    
    Use this tool when you need to understand the overall structure of a repository
    instead of making multiple separate ListFiles and ReadFile calls.
    """

    path: str = Field(default="/workspace", description="Root directory path (default: /workspace)")
    max_depth: int = Field(default=3, description="Maximum depth for directory tree (default: 3)")
    include_content: bool = Field(default=True, description="Whether to include content of key files (default: true)")



RUN_CODE    = pydantic_function_tool(RunCode)
RUN_SHELL = pydantic_function_tool(RunCommand)
WRITE_FILE  = pydantic_function_tool(WriteFile)
READ_FILE   = pydantic_function_tool(ReadFile)
APPEND_FILE = pydantic_function_tool(AppendFile)
EDIT_FILE   = pydantic_function_tool(EditFile)
LIST_FILES  = pydantic_function_tool(ListFiles)
GET_REPO_CONTEXT = pydantic_function_tool(GetRepoContext)

SANDBOX_TOOL_DEFINITIONS: list = [
    RUN_CODE, RUN_SHELL, WRITE_FILE, READ_FILE, APPEND_FILE, EDIT_FILE, LIST_FILES, GET_REPO_CONTEXT,
]


class SandboxToolKit:
    """Binds a live Sandbox instance to agent-dispatchable callables."""

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    @track(step_type="tool")
    async def run_code(self, code: str) -> dict:
        return await self._sandbox.run_code(code)


    @track(step_type="tool")
    async def run_shell(self, cmd: str) -> dict:
        return await self._sandbox.run_shell(cmd)


    @track(step_type="tool")
    async def write_file(self, path: str, content: str) -> dict:
        return await self._sandbox.write_file(path, content)


    @track(step_type="tool")
    async def read_file(self, path: str) -> dict:
        return await self._sandbox.read_file(path)


    @track(step_type="tool")
    async def append_file(self, path: str, content: str) -> dict:
        return await self._sandbox.append_file(path, content)


    @track(step_type="tool")
    async def edit_file(self, path: str, old_str: str, new_str: str) -> dict:
        return await self._sandbox.edit_file(path, old_str, new_str)


    @track(step_type="tool")
    async def list_files(self, path: str = "/workspace") -> dict:
        return await self._sandbox.list_files(path)

    @track(step_type="tool")
    async def get_repo_context(self, path: str = "/workspace", max_depth: int = 3, include_content: bool = True) -> dict:
        """Get comprehensive repository context including directory structure and key files."""
        from datetime import datetime, timezone
        import json

        result = {
            "success": True,
            "root_path": path,
            "directory_tree": {},
            "key_files": {},
            "recent_files": [],
            "message": f"Repository context for {path}",
        }

        # Get directory structure
        tree_result = await self._sandbox.run_shell(
            f"find '{path}' -maxdepth {max_depth} -type f -o -type d | head -100"
        )
        if tree_result.get("success"):
            paths = tree_result.get("stdout", "").strip().split("\n")
            tree = {"files": [], "directories": []}
            for p in paths:
                if p:
                    # Simple tree representation
                    if p.endswith('/'):
                        tree["directories"].append(p)
                    else:
                        tree["files"].append(p)
            result["directory_tree"] = tree

        # Identify and read key files
        key_file_patterns = [
            "README.md", "readme.md", "README.rst",
            "pyproject.toml", "setup.py", "setup.cfg",
            "requirements.txt", "requirements*.txt",
            ".gitignore", "LICENSE", "Makefile",
            "package.json", "Cargo.toml", "go.mod",
        ]

        if include_content:
            for pattern in key_file_patterns:
                find_result = await self._sandbox.run_shell(
                    f"find '{path}' -maxdepth 2 -name '{pattern}' -type f 2>/dev/null | head -1"
                )
                if find_result.get("success") and find_result.get("stdout", "").strip():
                    file_path = find_result.get("stdout", "").strip()
                    content_result = await self._sandbox.read_file(file_path)
                    if content_result.get("success"):
                        # Limit content length to avoid overwhelming context
                        content = content_result.get("content", "")
                        if len(content) > 5000:
                            content = content[:5000] + "\n... [content truncated]"
                        result["key_files"][file_path] = content

        # Get recently modified files
        recent_result = await self._sandbox.run_shell(
            f"find '{path}' -maxdepth {max_depth} -type f -mtime -7 -exec ls -lt {{}} + 2>/dev/null | head -20"
        )
        if recent_result.get("success"):
            lines = recent_result.get("stdout", "").strip().split("\n")
            recent_files = []
            for line in lines:
                parts = line.split()
                if len(parts) >= 9:
                    file_path = " ".join(parts[8:])
                    recent_files.append(file_path)
            result["recent_files"] = recent_files

        return result


    def as_tool_kits(self) -> dict[str, Callable]:
        """Return a name→callable mapping where names match pydantic_function_tool class names."""
        return {
            "RunCode":    self.run_code,
            "RunCommand": self.run_shell,
            "WriteFile":  self.write_file,
            "ReadFile":   self.read_file,
            "AppendFile": self.append_file,
            "EditFile":   self.edit_file,
            "ListFiles":  self.list_files,
            "GetRepoContext": self.get_repo_context,
        }
