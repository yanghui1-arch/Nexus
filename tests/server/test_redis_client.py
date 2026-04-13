import json

import pytest

from src.server.redis.client import RedisClient


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}
        self.ttls: dict[str, int] = {}

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    async def rpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).append(value)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.values[key] = value
        if ex is not None:
            self.ttls[key] = ex

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
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
        if key in self.lists:
            return "list"
        if key in self.values:
            return "string"
        return "none"

    async def delete(self, key: str) -> int:
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
        self.ttls[key] = ttl


@pytest.fixture
def redis_client() -> RedisClient:
    client = RedisClient("redis://test", ttl_seconds=300)
    client._client = FakeRedis()
    return client


@pytest.mark.asyncio
async def test_append_returns_key_and_pushes_value(redis_client: RedisClient) -> None:
    key = await redis_client.append("task:1:messages", {"status": "QUEUED"}, expiration_seconds=60)

    assert key == "task:1:messages"

    fake = redis_client._client
    assert isinstance(fake, FakeRedis)
    assert json.loads(fake.lists["task:1:messages"][0]) == {"status": "QUEUED"}
    assert fake.ttls["task:1:messages"] == 60


@pytest.mark.asyncio
async def test_append_returns_none_for_invalid_value(redis_client: RedisClient) -> None:
    key = await redis_client.append("task:2:messages", object())

    assert key is None


@pytest.mark.asyncio
async def test_set_returns_key(redis_client: RedisClient) -> None:
    key = await redis_client.set("llm:context:user_1", {"turn": 4})

    assert key == "llm:context:user_1"

    fake = redis_client._client
    assert isinstance(fake, FakeRedis)
    assert json.loads(fake.values["llm:context:user_1"]) == {"turn": 4}


@pytest.mark.asyncio
async def test_delete_returns_deleted_string_value(redis_client: RedisClient) -> None:
    await redis_client.set("user:1", {"id": "u1"})

    deleted = await redis_client.delete("user:1")

    assert deleted == {"id": "u1"}


@pytest.mark.asyncio
async def test_delete_returns_deleted_list_values(redis_client: RedisClient) -> None:
    await redis_client.append("task:3:messages", {"status": "A"})
    await redis_client.append("task:3:messages", {"status": "B"})

    deleted = await redis_client.delete("task:3:messages")

    assert deleted == [{"status": "A"}, {"status": "B"}]


@pytest.mark.asyncio
async def test_delete_missing_key_returns_none(redis_client: RedisClient) -> None:
    deleted = await redis_client.delete("missing:key")

    assert deleted is None
