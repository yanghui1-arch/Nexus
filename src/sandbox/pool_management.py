from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass

from src.logger import logger
from .docker_sandbox import Sandbox, SandboxConfig


_POOL_MANAGED_LABEL = "nexus.sandbox.managed"
_POOL_KEY_LABEL = "nexus.sandbox.pool_key"


def _sandbox_config_fingerprint(config: SandboxConfig) -> str:
    """Return a stable fingerprint for a sandbox config."""
    payload = {
        "image": config.image,
        "code_runner": config.code_runner,
        "code_ext": config.code_ext,
        "mem_limit": config.mem_limit,
        "init_commands": [
            {
                "name": cmd.name,
                "type": cmd.type,
                "command": cmd.command,
            }
            for cmd in config.init_commands
        ],
    }
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def _build_pool_key(
    config: SandboxConfig,
    repo_url: str | None,
    workspace_key: str | None,
    env: dict[str, str] | None = None,
) -> str:
    """Build a sandbox pool key."""
    base_key = workspace_key or ("__no_repo__" if repo_url is None else repo_url)
    env_names = ",".join(sorted((env or {}).keys()))
    return f"{base_key}::{_sandbox_config_fingerprint(config)}::{env_names}"


@dataclass
class _SandboxPoolEntry:
    key: str
    sandbox: Sandbox
    in_use: bool = False
    created_at: float = 0.0
    last_used_at: float = 0.0


class SandboxPoolManager:
    """In-process pool that reuses warm sandboxes with explicit workspace affinity."""

    def __init__(self) -> None:
        """Initialize the object."""
        self._entries_by_key: dict[str, list[_SandboxPoolEntry]] = {}
        self._lock = asyncio.Lock()

    def _find_entry_for_sandbox(
        self, sandbox: Sandbox
    ) -> tuple[str, _SandboxPoolEntry, list[_SandboxPoolEntry]] | None:
        """Find a managed pool entry for a sandbox."""
        sandbox_id = id(sandbox)
        for key, entries in self._entries_by_key.items():
            for entry in entries:
                if id(entry.sandbox) == sandbox_id:
                    return key, entry, entries
        return None

    async def acquire(
        self,
        config: SandboxConfig,
        repo_url: str | None = None,
        workspace_key: str | None = None,
        env: dict[str, str] | None = None,
    ) -> Sandbox:
        """Acquire a sandbox from the pool."""
        key = _build_pool_key(config=config, repo_url=repo_url, workspace_key=workspace_key, env=env)

        async with self._lock:
            for entry in self._entries_by_key.get(key, []):
                if not entry.in_use:
                    entry.in_use = True
                    entry.last_used_at = time.time()
                    logger.info(f"Reusing sandbox from pool with key={key}")
                    return entry.sandbox

            sandbox = Sandbox(config, env=env)
            labels = {_POOL_MANAGED_LABEL: "true", _POOL_KEY_LABEL: key}
            await sandbox.start(labels=labels)
            now = time.time()
            entry = _SandboxPoolEntry(
                key=key,
                sandbox=sandbox,
                in_use=True,
                created_at=now,
                last_used_at=now,
            )
            self._entries_by_key.setdefault(key, []).append(entry)
            logger.info(f"Created new sandbox in pool with key={key}")
            return sandbox

    async def release(self, sandbox: Sandbox) -> None:
        """Release a sandbox back to the pool."""
        async with self._lock:
            located_entry = self._find_entry_for_sandbox(sandbox)
            if located_entry is None:
                return
            _, entry, _ = located_entry
            entry.in_use = False
            entry.last_used_at = time.time()

    async def invalidate(self, sandbox: Sandbox) -> None:
        """Remove a sandbox from pool management."""
        async with self._lock:
            located_entry = self._find_entry_for_sandbox(sandbox)
            if located_entry is None:
                return
            key, entry, entries = located_entry

            filtered_entries = [candidate for candidate in entries if candidate is not entry]
            if filtered_entries:
                self._entries_by_key[key] = filtered_entries
            else:
                self._entries_by_key.pop(key, None)

        await sandbox.__aexit__(None, None, None)
        logger.info("Invalidated sandbox and removed it from pool")

    async def shutdown(self) -> None:
        """Shut down all managed sandboxes."""
        async with self._lock:
            sandboxes = [
                entry.sandbox
                for entries in self._entries_by_key.values()
                for entry in entries
            ]
            self._entries_by_key.clear()

        for sandbox in sandboxes:
            await sandbox.__aexit__(None, None, None)

    def is_managed(self, sandbox: Sandbox) -> bool:
        """Return whether a sandbox is pool-managed."""
        return self._find_entry_for_sandbox(sandbox) is not None


_SANDBOX_POOL_MANAGER: SandboxPoolManager | None = None


def get_sandbox_pool_manager() -> SandboxPoolManager:
    """Return the process-wide sandbox pool manager."""
    global _SANDBOX_POOL_MANAGER
    if _SANDBOX_POOL_MANAGER is None:
        _SANDBOX_POOL_MANAGER = SandboxPoolManager()
    return _SANDBOX_POOL_MANAGER
