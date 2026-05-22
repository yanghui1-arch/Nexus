import json

import pytest

from src.server.redis.client import RedisClient


class FakeRedis:
    def __init__(self) -> None:
        """Initialize the test helper."""
        self.values: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}
        self.ttls: dict[str, int] = {}

    async def ping(self) -> bool:
        """Return the fake service health status."""
        return True

    async def aclose(self) -> None:
        """Close the fake Redis client."""
        return None

    async def rpush(self, key: str, value: str) -> None:
        """Append a value to a fake Redis list."""
        self.lists.setdefault(key, []).append(value)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """Set a fake Redis string value."""
        self.values[key] = value
        if ex is not None:
            self.ttls[key] = ex

    async def get(self, key: str) -> str | None:
        """Return a fake stored value."""
        return self.values.get(key)

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        """Return fake Redis list values."""
        rows = self.lists.get(key, [])
        if not rows:
            return []

        size = len(rows)
        if start < 0:
            start = size + start
        if end < 0:
            end = size + end

        start = max(start, 0)
        end = min(end, size - 1)
        if start > end:
            return []
        return rows[start : end + 1]

    async def type(self, key: str) -> str:
        """Return the fake Redis value type."""
        if key in self.lists:
            return "list"
        if key in self.values:
            return "string"
        return "none"

    async def delete(self, key: str) -> int:
        """Delete a fake Redis value."""
        deleted = 0
        if key in self.values:
            del self.values[key]
            deleted += 1
        if key in self.lists:
            del self.lists[key]
            deleted += 1
        self.ttls.pop(key, None)
        return deleted

    async def expire(self, key: str, ttl: int) -> None:
        """Record fake Redis expiration."""
        self.ttls[key] = ttl


@pytest.fixture
def redis_client() -> RedisClient:
    """Create a Redis client fixture."""
    client = RedisClient("redis://test", ttl_seconds=300)
    client._client = FakeRedis()
    return client


@pytest.mark.asyncio
async def test_append_returns_key_and_pushes_value(redis_client: RedisClient) -> None:
    """Verify append returns key and pushes value."""
    key = await redis_client.append("task:1:messages", {"status": "QUEUED"}, expiration_seconds=60)

    assert key == "task:1:messages"

    fake = redis_client._client
    assert isinstance(fake, FakeRedis)
    assert json.loads(fake.lists["task:1:messages"][0]) == {"status": "QUEUED"}
    assert fake.ttls["task:1:messages"] == 60


@pytest.mark.asyncio
async def test_append_returns_none_for_invalid_value(redis_client: RedisClient) -> None:
    """Verify append returns none for invalid value."""
    key = await redis_client.append("task:2:messages", object())

    assert key is None


@pytest.mark.asyncio
async def test_set_returns_key(redis_client: RedisClient) -> None:
    """Verify set returns key."""
    key = await redis_client.set("llm:context:user_1", {"turn": 4})

    assert key == "llm:context:user_1"

    fake = redis_client._client
    assert isinstance(fake, FakeRedis)
    assert json.loads(fake.values["llm:context:user_1"]) == {"turn": 4}


@pytest.mark.asyncio
async def test_delete_returns_deleted_string_value(redis_client: RedisClient) -> None:
    """Verify delete returns deleted string value."""
    await redis_client.set("user:1", {"id": "u1"})

    deleted = await redis_client.delete("user:1")

    assert deleted == {"id": "u1"}


@pytest.mark.asyncio
async def test_delete_returns_deleted_list_values(redis_client: RedisClient) -> None:
    """Verify delete returns deleted list values."""
    await redis_client.append("task:3:messages", {"status": "A"})
    await redis_client.append("task:3:messages", {"status": "B"})

    deleted = await redis_client.delete("task:3:messages")

    assert deleted == [{"status": "A"}, {"status": "B"}]


@pytest.mark.asyncio
async def test_delete_missing_key_returns_none(redis_client: RedisClient) -> None:
    """Verify delete missing key returns none."""
    deleted = await redis_client.delete("missing:key")

    assert deleted is None
