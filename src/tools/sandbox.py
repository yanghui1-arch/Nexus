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


class CreateFile(BaseModel):
    """Create a new text file or completely replace an existing file in the sandbox workspace.
    For small edits to existing files, prefer EditFile.
    """

    path: str = Field(description="Absolute path under /workspace, e.g. /workspace/src/main.py")
    content: str = Field(description="Complete file content for the new or fully overwritten file")


class ReadFile(BaseModel):
    """Read a text file from the sandbox workspace and return its content."""

    path: str = Field(description="Absolute path under /workspace")


class AppendFile(BaseModel):
    """Append text to the end of a file (creates it if it does not exist)."""

    path: str = Field(description="Absolute path under /workspace")
    content: str = Field(description="Text to append")


class EditFile(BaseModel):
    """Replace the first occurrence of old_str with new_str inside an existing file.
    Use a unique, multi-line old_str to avoid ambiguity.
    Examples:
    - Change: old_str='x = 1', new_str='x = 2'.
    - Delete: old_str='debug = True\n', new_str=''.
    - Insert: old_str='def run():\n', new_str='def run():\n    print("start")\n'.
    """

    path: str = Field(description="Absolute path under /workspace")
    old_str: str = Field(description="Exact substring to find and replace; prefer a unique, multi-line block")
    new_str: str = Field(description="Replacement string; leave empty to delete old_str, or include old_str plus inserted text to insert")


class ListFiles(BaseModel):
    """List files and directories inside a sandbox directory."""

    path: str = Field(default="/workspace", description="Directory path to list (default: /workspace)")



RUN_CODE    = pydantic_function_tool(RunCode)
RUN_SHELL = pydantic_function_tool(RunCommand)
CREATE_FILE = pydantic_function_tool(CreateFile)
READ_FILE   = pydantic_function_tool(ReadFile)
APPEND_FILE = pydantic_function_tool(AppendFile)
EDIT_FILE   = pydantic_function_tool(EditFile)
LIST_FILES  = pydantic_function_tool(ListFiles)

SANDBOX_TOOL_DEFINITIONS: list = [
    RUN_CODE, RUN_SHELL, CREATE_FILE, READ_FILE, APPEND_FILE, EDIT_FILE, LIST_FILES,
]


class SandboxToolKit:
    """Binds a live Sandbox instance to agent-dispatchable callables."""

    def __init__(self, sandbox: Sandbox) -> None:
        """Initialize the object."""
        self._sandbox = sandbox

    @track(step_type="tool")
    async def run_code(self, code: str) -> dict:
        """Run Python code in the sandbox."""
        return await self._sandbox.run_code(code)


    @track(step_type="tool")
    async def run_shell(self, cmd: str) -> dict:
        """Run a shell command in the sandbox."""
        return await self._sandbox.run_shell(cmd)


    @track(step_type="tool")
    async def create_file(self, path: str, content: str) -> dict:
        """Create or replace a file in the sandbox."""
        return await self._sandbox.write_file(path, content)


    @track(step_type="tool")
    async def read_file(self, path: str) -> dict:
        """Read a file from the sandbox."""
        return await self._sandbox.read_file(path)


    @track(step_type="tool")
    async def append_file(self, path: str, content: str) -> dict:
        """Append content to a file in the sandbox."""
        return await self._sandbox.append_file(path, content)


    @track(step_type="tool")
    async def edit_file(self, path: str, old_str: str, new_str: str) -> dict:
        """Edit a file in the sandbox."""
        return await self._sandbox.edit_file(path, old_str, new_str)


    @track(step_type="tool")
    async def list_files(self, path: str = "/workspace") -> dict:
        """List files in the sandbox."""
        return await self._sandbox.list_files(path)


    @property
    def all_tools(self) -> dict[str, Callable]:
        """Return a name→callable mapping where names match pydantic_function_tool class names."""
        return {
            "RunCode":    self.run_code,
            "RunCommand": self.run_shell,
            "CreateFile": self.create_file,
            "ReadFile":   self.read_file,
            "AppendFile": self.append_file,
            "EditFile":   self.edit_file,
            "ListFiles":  self.list_files,
        }
