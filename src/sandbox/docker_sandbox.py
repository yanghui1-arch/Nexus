import asyncio
import base64
import tempfile
import shutil
from typing import Literal
from dataclasses import dataclass
from pathlib import Path

import docker

from src.logger import logger

@dataclass
class CommandConfig:
    name: str
    command: str
    type: Literal["install", "env", "other_shell"]

@dataclass(frozen=True)
class SandboxConfig:
    """Describes the Docker environment a sandbox should run in.

    Pick a built-in preset or build for custom images:

    ## Built-in
    Sandbox(PYTHON_312) \n
    Sandbox(PYTHON_312_GIT)  # includes git \n
    Sandbox(NODE_20) \n
    Sandbox(JAVA_21) \n

    ## Custom image (e.g. Python + Nginx, TS + Java, specific version)
    Sandbox(SandboxConfig(
        image="myorg/python-nginx:latest",
        code_runner="python",
        code_ext=".py",
    ))
    """

    image: str
    code_runner: str            # executable used by run_code(), e.g. "python", "node", "java"
    code_ext: str               # file extension for the temp script, e.g. ".py", ".js", ".java"
    mem_limit: str = "128m"    # Docker memory limit; JVM needs at least 256m
    init_commands: tuple[CommandConfig, ...] = ()  # shell commands run once after the container starts


_GIT_INSTALL = CommandConfig(name="git", command="apt-get update && apt-get install -y --no-install-recommends git", type="install")
_NODE_REACT_SETUP = CommandConfig(
    name="node-react-setup",
    command="apt-get update && apt-get install -y --no-install-recommends git && npm install -g tsx",
    type="install",
)

PYTHON_310 = SandboxConfig("python:3.10-slim", "python", ".py", init_commands=(_GIT_INSTALL,))
PYTHON_311 = SandboxConfig("python:3.11-slim", "python", ".py", init_commands=(_GIT_INSTALL,))
PYTHON_312 = SandboxConfig("python:3.12-slim", "python", ".py", init_commands=(_GIT_INSTALL,))

NODE_18    = SandboxConfig("node:18-slim",  "node", ".js")
NODE_20    = SandboxConfig("node:20-slim",  "node", ".js")
NODE_22    = SandboxConfig("node:22-slim",  "node", ".js")

VITE_REACT_TS = SandboxConfig("node:20-slim", "tsx", ".ts", mem_limit="512m", init_commands=(_NODE_REACT_SETUP, _GIT_INSTALL))

# eclipse-temurin ships a proper JDK; java <File>.java works since Java 11
# JVM requires more headroom than Python/Node
JAVA_17    = SandboxConfig("eclipse-temurin:17-jdk-jammy", "java", ".java", mem_limit="256m")
JAVA_21    = SandboxConfig("eclipse-temurin:21-jdk-jammy", "java", ".java", mem_limit="256m")


class Sandbox:
    """Async context manager that runs an isolated Docker container as a sandbox.

    A single container is started on entry and killed on exit. All operations
    share the same container, so state (installed packages, written files)
    persists across calls within the same session.

    All file I/O runs through Docker exec — the host filesystem is never
    touched directly. The /workspace volume mount is kept for potential
    future use but is not relied on by any operation.

    Requires Docker to be running locally. No API key or internet access needed.

    Usage::

        async with Sandbox(PYTHON_312) as sandbox:
            await sandbox.run_code("print('hello')")

        async with Sandbox(NODE_20) as sandbox:
            await sandbox.run_code("console.log('hello')")

        # Custom image (e.g. Python + Nginx, TS + Java, specific version)
        cfg = SandboxConfig("myorg/ts-java:latest", "ts-node", ".ts")
        async with Sandbox(cfg) as sandbox:
            await sandbox.run_code("console.log('hello from ts')")
    """

    def __init__(self, config: SandboxConfig) -> None:
        self._config = config
        self._client: docker.DockerClient | None = None
        self._container = None
        self._workdir: str | None = None


    async def __aenter__(self) -> "Sandbox":
        self._client = await asyncio.to_thread(docker.from_env)
        self._workdir = tempfile.mkdtemp(prefix="nexus_sandbox_")
        self._container = await asyncio.to_thread(
            self._client.containers.run,
            self._config.image,
            command="sleep infinity",
            detach=True,
            auto_remove=True,
            mem_limit=self._config.mem_limit,
            security_opt=["no-new-privileges"],
            volumes={self._workdir: {"bind": "/workspace", "mode": "rw"}},
            working_dir="/workspace",
        )
        for cmd in self._config.init_commands:
            if cmd.type == "install":
                logger.info(f"Installing {cmd.name}")
            else:
                logger.info(f"Initializing {cmd.name}")
            await self.run_shell(cmd.command)
        return self


    async def __aexit__(self, *_) -> None:
        if self._container:
            await asyncio.to_thread(self._container.kill)
            self._container = None
        if self._workdir:
            shutil.rmtree(self._workdir, ignore_errors=True)
            self._workdir = None


    async def recreate(self) -> "Sandbox":
        """Recreate the underlying container and workspace in-place."""
        await self.__aexit__(None, None, None)
        await self.__aenter__()
        return self


    async def run_code(self, code: str) -> dict:
        """Write code to a temp script inside the container and execute it.

        Returns dict with keys: success, stdout, stderr, exit_code, error.
        """
        script_path = f"/workspace/_nexus_exec{self._config.code_ext}"
        write_result = await self.write_file(script_path, code)
        if not write_result["success"]:
            return {
                "success": False,
                "stdout": "",
                "stderr": write_result.get("error", ""),
                "exit_code": 1,
                "error": write_result.get("error"),
            }
        result = await self._exec([self._config.code_runner, script_path])
        await self._exec(["/bin/sh", "-c", f"rm -f '{script_path}'"])
        return result


    async def run_shell(self, cmd: str) -> dict:
        """Run a shell command inside the container.

        Returns dict with keys: success, stdout, stderr, exit_code, error.
        """
        return await self._exec(["/bin/sh", "-c", cmd])


    async def write_file(self, path: str, content: str) -> dict:
        """Write (overwrite) a text file at the given path inside the container.

        Returns dict with keys: success, path, error.
        """
        try:
            encoded = base64.b64encode(content.encode()).decode()
            dir_path = str(Path(path).parent)
            result = await self._exec([
                "/bin/sh", "-c",
                f"mkdir -p '{dir_path}' && echo '{encoded}' | base64 -d > '{path}'",
            ])
            if not result["success"]:
                return {"success": False, "path": path, "error": result.get("stderr", "write failed")}
            return {"success": True, "path": path, "error": None}
        except Exception as e:
            return {"success": False, "path": path, "error": str(e)}


    async def read_file(self, path: str) -> dict:
        """Read a text file from inside the container.

        Returns dict with keys: success, path, content, error.
        """
        result = await self._exec(["/bin/sh", "-c", f"cat '{path}'"])
        if not result["success"]:
            return {"success": False, "path": path, "content": None, "error": result.get("stderr")}
        return {"success": True, "path": path, "content": result["stdout"], "error": None}


    async def append_file(self, path: str, content: str) -> dict:
        """Append text to the end of a file (creates it if it does not exist).

        Returns dict with keys: success, path, error.
        """
        try:
            encoded = base64.b64encode(content.encode()).decode()
            dir_path = str(Path(path).parent)
            result = await self._exec([
                "/bin/sh", "-c",
                f"mkdir -p '{dir_path}' && echo '{encoded}' | base64 -d >> '{path}'",
            ])
            if not result["success"]:
                return {"success": False, "path": path, "error": result.get("stderr", "append failed")}
            return {"success": True, "path": path, "error": None}
        except Exception as e:
            return {"success": False, "path": path, "error": str(e)}


    async def edit_file(self, path: str, old_str: str, new_str: str) -> dict:
        """Replace the first occurrence of old_str with new_str inside a file.

        Returns dict with keys: success, path, replaced, error.
        `replaced` is False when old_str was not found (file left unchanged).
        """
        read_result = await self.read_file(path)
        if not read_result["success"]:
            return {"success": False, "path": path, "replaced": False, "error": read_result["error"]}

        content = read_result["content"]
        if old_str not in content:
            return {"success": False, "path": path, "replaced": False, "error": f"old_str not found in {path}"}

        write_result = await self.write_file(path, content.replace(old_str, new_str, 1))
        if not write_result["success"]:
            return {"success": False, "path": path, "replaced": False, "error": write_result["error"]}

        return {"success": True, "path": path, "replaced": True, "error": None}


    async def list_files(self, path: str = "/workspace") -> dict:
        """List files and directories inside a container directory.

        Returns dict with keys: success, path, files, error.
        Each entry in files has keys: name, type ('file' or 'directory').
        """
        try:
            result = await self._exec([
                "/bin/sh", "-c",
                f"find '{path}' -maxdepth 1 -mindepth 1 -printf '%f\\t%y\\n' | sort",
            ])
            if not result["success"]:
                return {"success": False, "path": path, "files": [], "error": result.get("stderr")}

            entries = []
            for line in result["stdout"].strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) == 2:
                    name, ftype = parts
                    entries.append({"name": name, "type": "directory" if ftype == "d" else "file"})

            return {"success": True, "path": path, "files": entries, "error": None}
        except Exception as e:
            return {"success": False, "path": path, "files": [], "error": str(e)}


    async def _exec(self, cmd: list[str]) -> dict:
        exit_code, output = await asyncio.to_thread(
            self._container.exec_run, cmd, demux=True
        )
        stdout_b, stderr_b = output if output else (b"", b"")
        stdout = stdout_b.decode() if stdout_b else ""
        stderr = stderr_b.decode() if stderr_b else ""
        return {
            "success": exit_code == 0,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "error": stderr if exit_code != 0 else None,
        }

    def _to_host_path(self, container_path: str) -> Path:
        """Translate a /workspace container path to the host-side temp directory.
        Available for use when the volume mount is active.
        Currently it's not used and must keep it.
        """
        rel = container_path.removeprefix("/workspace").lstrip("/")
        return Path(self._workdir) / rel

