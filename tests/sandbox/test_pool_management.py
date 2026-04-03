import pytest

from src.sandbox import PYTHON_312
from src.sandbox.pool_management import SandboxPoolManager, canonicalize_repo_url


class DummySandbox:
    def __init__(self, config) -> None:
        self.config = config
        self.enter_calls = 0
        self.exit_calls = 0

    async def __aenter__(self):
        self.enter_calls += 1
        return self

    async def __aexit__(self, *_):
        self.exit_calls += 1


@pytest.mark.asyncio
async def test_pool_reuses_released_sandbox_for_same_repo_and_config():
    manager = SandboxPoolManager(sandbox_factory=DummySandbox)

    first = await manager.acquire(PYTHON_312, repo_url="https://github.com/Owner/Repo.git")
    await manager.release(first)
    second = await manager.acquire(PYTHON_312, repo_url="git@github.com:owner/repo.git")

    assert second is first
    await manager.shutdown()


@pytest.mark.asyncio
async def test_pool_creates_new_sandbox_when_existing_entry_is_in_use():
    manager = SandboxPoolManager(sandbox_factory=DummySandbox)

    first = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo")
    second = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo")

    assert second is not first
    await manager.release(first)
    await manager.release(second)
    await manager.shutdown()


@pytest.mark.asyncio
async def test_pool_separates_sandboxes_for_different_repos():
    manager = SandboxPoolManager(sandbox_factory=DummySandbox)

    first = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo-a")
    await manager.release(first)
    second = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo-b")

    assert second is not first
    await manager.shutdown()


@pytest.mark.asyncio
async def test_invalidate_removes_sandbox_and_forces_recreate_on_next_acquire():
    manager = SandboxPoolManager(sandbox_factory=DummySandbox)

    first = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo")
    await manager.invalidate(first)
    second = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo")

    assert second is not first
    assert first.exit_calls == 1
    await manager.shutdown()


def test_canonicalize_repo_url_handles_auth_ssh_and_suffixes():
    assert canonicalize_repo_url("https://token@github.com/Owner/Repo.git") == "https://github.com/owner/repo"
    assert canonicalize_repo_url("git@github.com:Owner/Repo.git") == "https://github.com/owner/repo"
    assert canonicalize_repo_url("ssh://git@github.com/Owner/Repo") == "https://github.com/owner/repo"
