from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Callable

from src.logger import logger
from .docker_sandbox import Sandbox, SandboxConfig


def canonicalize_repo_url(repo_url: str | None) -> str | None:
    """Normalize repository URLs for stable pool keying and comparison."""
    if repo_url is None:
        return None

    normalized = repo_url.strip()
    if not normalized:
        return None

    # Convert common SSH forms to an HTTPS-like comparable form.
    if normalized.startswith("git@"):
        host_path = normalized[4:]
        if ":" in host_path:
            host, path = host_path.split(":", 1)
            normalized = f"https://{host}/{path}"
    elif normalized.startswith("ssh://git@"):
        host_path = normalized[len("ssh://git@"):]
        if "/" in host_path:
            host, path = host_path.split("/", 1)
            normalized = f"https://{host}/{path}"

    # Drop credentials for comparisons (e.g. https://token@github.com/owner/repo).
    if "://" in normalized:
        scheme, rest = normalized.split("://", 1)
        if "@" in rest:
            rest = rest.split("@", 1)[1]
        normalized = f"{scheme}://{rest}"

    normalized = normalized.removesuffix(".git").rstrip("/")
    return normalized.lower()


def _sandbox_config_fingerprint(config: SandboxConfig) -> str:
    init_commands_fingerprint = "|".join(
        f"{cmd.name}:{cmd.type}:{cmd.command}" for cmd in config.init_commands
    )
    return (
        f"{config.image}|{config.code_runner}|{config.code_ext}|"
        f"{config.mem_limit}|{init_commands_fingerprint}"
    )


def _build_pool_key(config: SandboxConfig, repo_url: str | None) -> str:
    normalized_repo = canonicalize_repo_url(repo_url) or "__no_repo__"
    return f"{normalized_repo}::{_sandbox_config_fingerprint(config)}"


@dataclass
class _SandboxPoolEntry:
    key: str
    sandbox: Sandbox
    in_use: bool = False
    created_at: float = 0.0
    last_used_at: float = 0.0


class SandboxPoolManager:
    """In-process pool that reuses warm sandboxes for same repo + config."""

    def __init__(self, sandbox_factory: Callable[[SandboxConfig], Sandbox] = Sandbox) -> None:
        self._sandbox_factory = sandbox_factory
        self._entries_by_key: dict[str, list[_SandboxPoolEntry]] = {}
        self._entries_by_sandbox_id: dict[int, _SandboxPoolEntry] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, config: SandboxConfig, repo_url: str | None = None) -> Sandbox:
        key = _build_pool_key(config=config, repo_url=repo_url)

        async with self._lock:
            for entry in self._entries_by_key.get(key, []):
                if not entry.in_use:
                    entry.in_use = True
                    entry.last_used_at = time.time()
                    logger.info(f"Reusing sandbox from pool with key={key}")
                    return entry.sandbox

            sandbox = self._sandbox_factory(config)
            await sandbox.__aenter__()
            now = time.time()
            entry = _SandboxPoolEntry(
                key=key,
                sandbox=sandbox,
                in_use=True,
                created_at=now,
                last_used_at=now,
            )
            self._entries_by_key.setdefault(key, []).append(entry)
            self._entries_by_sandbox_id[id(sandbox)] = entry
            logger.info(f"Created new sandbox in pool with key={key}")
            return sandbox

    async def release(self, sandbox: Sandbox) -> None:
        async with self._lock:
            entry = self._entries_by_sandbox_id.get(id(sandbox))
            if entry is None:
                return
            entry.in_use = False
            entry.last_used_at = time.time()

    async def invalidate(self, sandbox: Sandbox) -> None:
        async with self._lock:
            entry = self._entries_by_sandbox_id.pop(id(sandbox), None)
            if entry is None:
                return

            entries = self._entries_by_key.get(entry.key, [])
            filtered_entries = [candidate for candidate in entries if candidate is not entry]
            if filtered_entries:
                self._entries_by_key[entry.key] = filtered_entries
            else:
                self._entries_by_key.pop(entry.key, None)

        await sandbox.__aexit__(None, None, None)
        logger.info("Invalidated sandbox and removed it from pool")

    async def shutdown(self) -> None:
        async with self._lock:
            sandboxes = [entry.sandbox for entry in self._entries_by_sandbox_id.values()]
            self._entries_by_key.clear()
            self._entries_by_sandbox_id.clear()

        for sandbox in sandboxes:
            await sandbox.__aexit__(None, None, None)

    def is_managed(self, sandbox: Sandbox) -> bool:
        return id(sandbox) in self._entries_by_sandbox_id


_SANDBOX_POOL_MANAGER: SandboxPoolManager | None = None


def get_sandbox_pool_manager() -> SandboxPoolManager:
    global _SANDBOX_POOL_MANAGER
    if _SANDBOX_POOL_MANAGER is None:
        _SANDBOX_POOL_MANAGER = SandboxPoolManager()
    return _SANDBOX_POOL_MANAGER
