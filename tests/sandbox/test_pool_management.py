import hashlib
import json

import pytest

import src.sandbox.pool_management as pool_management
from src.sandbox import PYTHON_312
from src.sandbox.pool_management import SandboxPoolManager, _sandbox_config_fingerprint


class DummySandbox:
    start_calls = []

    def __init__(self, config) -> None:
        self.config = config
        self.enter_calls = 0
        self.exit_calls = 0

    async def start(self, *, labels=None):
        self.enter_calls += 1
        self.start_calls.append(labels)
        return self

    async def __aenter__(self):
        return await self.start()

    async def __aexit__(self, *_):
        self.exit_calls += 1


@pytest.fixture
def sandbox_stub(monkeypatch):
    DummySandbox.start_calls = []
    monkeypatch.setattr(pool_management, "Sandbox", DummySandbox)


@pytest.mark.asyncio
async def test_pool_reuses_released_sandbox_for_same_repo_and_config(sandbox_stub):
    manager = SandboxPoolManager()

    first = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo")
    await manager.release(first)
    second = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo")

    assert second is first
    await manager.shutdown()


@pytest.mark.asyncio
async def test_pool_labels_new_sandboxes_for_cross_process_reuse(sandbox_stub):
    manager = SandboxPoolManager()

    await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo")

    labels = DummySandbox.start_calls[-1]
    assert labels[pool_management._POOL_MANAGED_LABEL] == "true"
    assert labels[pool_management._POOL_KEY_LABEL].startswith("https://github.com/owner/repo::")
    await manager.shutdown()


@pytest.mark.asyncio
async def test_pool_uses_distinct_keys_for_distinct_repo_urls(sandbox_stub):
    manager = SandboxPoolManager()

    first = await manager.acquire(PYTHON_312, repo_url="https://github.com/Owner/Repo.git")
    await manager.release(first)
    second = await manager.acquire(PYTHON_312, repo_url="git@github.com:owner/repo.git")

    assert second is not first
    await manager.shutdown()


@pytest.mark.asyncio
async def test_pool_creates_new_sandbox_when_existing_entry_is_in_use(sandbox_stub):
    manager = SandboxPoolManager()

    first = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo")
    second = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo")

    assert second is not first
    await manager.release(first)
    await manager.release(second)
    await manager.shutdown()


@pytest.mark.asyncio
async def test_pool_separates_sandboxes_for_different_repos(sandbox_stub):
    manager = SandboxPoolManager()

    first = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo-a")
    await manager.release(first)
    second = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo-b")

    assert second is not first
    await manager.shutdown()


@pytest.mark.asyncio
async def test_invalidate_removes_sandbox_and_forces_recreate_on_next_acquire(sandbox_stub):
    manager = SandboxPoolManager()

    first = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo")
    await manager.invalidate(first)
    second = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo")

    assert second is not first
    assert first.exit_calls == 1
    await manager.shutdown()


@pytest.mark.asyncio
async def test_is_managed_tracks_membership_without_reverse_index(sandbox_stub):
    manager = SandboxPoolManager()

    sandbox = await manager.acquire(PYTHON_312, repo_url="https://github.com/owner/repo")

    assert manager.is_managed(sandbox)

    await manager.release(sandbox)
    assert manager.is_managed(sandbox)

    await manager.invalidate(sandbox)
    assert not manager.is_managed(sandbox)


def test_sandbox_config_fingerprint_uses_sha256_of_canonical_payload():
    payload = {
        "image": PYTHON_312.image,
        "code_runner": PYTHON_312.code_runner,
        "code_ext": PYTHON_312.code_ext,
        "mem_limit": PYTHON_312.mem_limit,
        "init_commands": [
            {
                "name": cmd.name,
                "type": cmd.type,
                "command": cmd.command,
            }
            for cmd in PYTHON_312.init_commands
        ],
    }
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    expected = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

    assert _sandbox_config_fingerprint(PYTHON_312) == expected

