import asyncio
from typing import Callable

async def make_async(func: Callable, *args, **kwargs):
    """Make a sync callable to be an async coroutine."""
    return await asyncio.to_thread(func, *args, **kwargs)