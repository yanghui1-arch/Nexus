import asyncio
import tempfile
import shutil
from dataclasses import dataclass
from pathlib import Path

import docker
import docker.errors


@dataclass(frozen=True)
class SandboxConfig:
    """Describes the Docker environment a sandbox should run in.

    Pick a built-in preset or build for custom images:

    ## Built-in
    Sandbox(PYTHON_312) \n
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
    code_runner: str   # executable used by run_code(), e.g. "python", "node", "java"
    code_ext: str      # file extension for the temp script, e.g. ".py", ".js", ".java"
    mem_limit: str = "128m"  # Docker memory limit; JVM needs at least 256m


PYTHON_310 = SandboxConfig("python:3.10-slim", "python", ".py")
PYTHON_311 = SandboxConfig("python:3.11-slim", "python", ".py")
PYTHON_312 = SandboxConfig("python:3.12-slim", "python", ".py")

NODE_18    = SandboxConfig("node:18-slim",  "node", ".js")
NODE_20    = SandboxConfig("node:20-slim",  "node", ".js")
NODE_22    = SandboxConfig("node:22-slim",  "node", ".js")

# eclipse-temurin ships a proper JDK; java <File>.java works since Java 11
# JVM requires more headroom than Python/Node
JAVA_17    = SandboxConfig("eclipse-temurin:17-jdk-jammy", "java", ".java", mem_limit="256m")
JAVA_21    = SandboxConfig("eclipse-temurin:21-jdk-jammy", "java", ".java", mem_limit="256m")



class Sandbox:
    """Async context manager that runs an isolated Docker container as a sandbox.

    A single container is started on entry and killed on exit. All operations
    share the same container, so state (installed packages, written files)
    persists across calls within the same session.

    Files live under /workspace inside the container, which is backed by a
    temporary directory on the host — making read/write operations fast (no
    docker cp round-trip needed).

    Requires Docker to be running locally. No API key or internet access needed.

    Usage::

        async with Sandbox(PYTHON_312) as sandbox:
            await sandbox.run_code("print('hello')")

        async with Sandbox(NODE_20) as sandbox:
            await sandbox.run_code("console.log('hello')")

        # Custom image
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
        return self
    

    async def __aexit__(self, *_) -> None:
        if self._container:
            await asyncio.to_thread(self._container.kill)
            self._container = None
        if self._workdir:
            shutil.rmtree(self._workdir, ignore_errors=True)
            self._workdir = None


    async def run_code(self, code: str) -> dict:
        """Write code to a temp script and execute it with the config's runner.

        Returns dict with keys: success, stdout, stderr, exit_code, error.
        """
        filename = f"_nexus_exec{self._config.code_ext}"
        (Path(self._workdir) / filename).write_text(code, encoding="utf-8")
        result = await self._exec([self._config.code_runner, f"/workspace/{filename}"])
        (Path(self._workdir) / filename).unlink(missing_ok=True)
        return result


    async def run_command(self, cmd: str) -> dict:
        """Run a shell command inside the container.

        Returns dict with keys: success, stdout, stderr, exit_code, error.
        """
        return await self._exec(["/bin/sh", "-c", cmd])

    
    async def write_file(self, path: str, content: str) -> dict:
        """Write a text file into the sandbox (path must be under /workspace).

        Returns dict with keys: success, path, error.
        """
        try:
            host_path = self._to_host_path(path)
            host_path.parent.mkdir(parents=True, exist_ok=True)
            host_path.write_text(content, encoding="utf-8")
            return {"success": True, "path": path, "error": None}
        except Exception as e:
            return {"success": False, "path": path, "error": str(e)}
        

    async def append_file(self, path: str, content: str) -> dict:
        """Append content to the end of a file (creates the file if it doesn't exist).

        Returns dict with keys: success, path, error.
        """
        try:
            host_path = self._to_host_path(path)
            host_path.parent.mkdir(parents=True, exist_ok=True)
            with host_path.open("a", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "path": path, "error": None}
        except Exception as e:
            return {"success": False, "path": path, "error": str(e)}
        

    async def edit_file(self, path: str, old_str: str, new_str: str) -> dict:
        """Replace the first occurrence of old_str with new_str inside a file.

        Covers all targeted edit cases:
          - Change:  old_str="x = 1",      new_str="x = 2"
          - Remove:  old_str="x = 1\\n",   new_str=""
          - Insert:  old_str="def foo():", new_str="def foo():\\n    # added"

        Returns dict with keys: success, path, replaced, error.
        `replaced` is False when old_str was not found (file left unchanged).
        """
        try:
            host_path = self._to_host_path(path)
            original = host_path.read_text(encoding="utf-8")
            if old_str not in original:
                return {"success": False, "path": path, "replaced": False, "error": f"old_str not found in {path}"}
            host_path.write_text(original.replace(old_str, new_str, 1), encoding="utf-8")
            return {"success": True, "path": path, "replaced": True, "error": None}
        except Exception as e:
            return {"success": False, "path": path, "replaced": False, "error": str(e)}
        

    async def read_file(self, path: str) -> dict:
        """Read a text file from inside the sandbox.

        Returns dict with keys: success, path, content, error.
        """
        try:
            content = self._to_host_path(path).read_text(encoding="utf-8")
            return {"success": True, "path": path, "content": content, "error": None}
        except Exception as e:
            return {"success": False, "path": path, "content": None, "error": str(e)}
        

    async def list_files(self, path: str = "/workspace") -> dict:
        """List files in a sandbox directory.

        Returns dict with keys: success, path, files, error.
        Each entry in files has keys: name, type ('file' or 'directory').
        """
        try:
            entries = [
                {"name": e.name, "type": "directory" if e.is_dir() else "file"}
                for e in sorted(self._to_host_path(path).iterdir())
            ]
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
        rel = container_path.removeprefix("/workspace").lstrip("/")
        return Path(self._workdir) / rel
