from __future__ import annotations

import shlex

from src.sandbox import Sandbox


def quote_git_command(local_path: str, *args: str) -> str:
    return " ".join(["git", "-C", shlex.quote(local_path), *(shlex.quote(arg) for arg in args)])


async def git_stdout(sandbox: Sandbox, local_path: str, *args: str) -> str:
    result = await sandbox.run_shell(quote_git_command(local_path, *args))
    if not result or not result.get("success", False):
        stderr = result.get("stderr", "") if result else "git command failed"
        stdout = result.get("stdout", "") if result else ""
        detail = stderr or stdout or "git command failed"
        raise RuntimeError(detail.strip())
    return result.get("stdout", "").strip()


def parse_numstat(numstat: str) -> tuple[list[str], int, int]:
    changed_files: list[str] = []
    additions = 0
    deletions = 0

    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue

        added, deleted, path = parts[0], parts[1], parts[-1]
        changed_files.append(path)
        if added.isdigit():
            additions += int(added)
        if deleted.isdigit():
            deletions += int(deleted)

    return changed_files, additions, deletions
