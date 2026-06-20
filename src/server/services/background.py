from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class BackgroundService(Protocol):
    """Lifecycle contract for singleton long-running background components."""

    def start(self) -> None:
        """Start the service without blocking the caller."""
        ...

    async def stop(self) -> None:
        """Stop the service and release external resources."""
        ...
