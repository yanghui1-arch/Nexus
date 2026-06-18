from unittest.mock import AsyncMock, MagicMock

import pytest

import src.sandbox.docker_sandbox as docker_sandbox
from src.sandbox.docker_sandbox import CommandConfig, Sandbox, SandboxConfig


def test_git_install_includes_ca_certificates():
    """Verify Git-enabled sandboxes install a trusted HTTPS certificate bundle."""
    command = docker_sandbox._GIT_INSTALL.command

    assert "ca-certificates" in command
    assert "update-ca-certificates" in command


@pytest.mark.asyncio
async def test_start_runs_init_command_without_interpreting_shell_result(monkeypatch):
    """Verify start delegates initialization command execution to run_shell."""
    container = MagicMock()
    client = MagicMock()
    client.containers.run.return_value = container
    monkeypatch.setattr(docker_sandbox.docker, "from_env", lambda: client)

    config = SandboxConfig(
        image="test-image",
        code_runner="python",
        code_ext=".py",
        init_commands=(CommandConfig("broken", "exit 1", "install"),),
    )
    sandbox = Sandbox(config)
    sandbox.run_shell = AsyncMock(
        return_value={
            "success": False,
            "stdout": "",
            "stderr": "command failed",
            "exit_code": 1,
            "error": "command failed",
        }
    )

    result = await sandbox.start()

    assert result is sandbox
    sandbox.run_shell.assert_awaited_once_with("exit 1")
    container.kill.assert_not_called()
    assert sandbox._container is container
