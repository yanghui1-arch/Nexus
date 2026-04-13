from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from src.logger import logger


class RedisClient:
    def __init__(self, redis_url: str, ttl_seconds: int = 86400) -> None:
        self._redis_url = redis_url
        self._ttl_seconds = ttl_seconds
        self._client: Redis | None = None

    async def connect(self) -> None:
        if self._client is not None:
            return
        self._client = Redis.from_url(self._redis_url, decode_responses=True)
        await self._client.ping()
        logger.info("Redis is connected.")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("Redis is closed.")

    async def ping(self) -> bool:
        if self._client is None:
            return False
        try:
            return bool(await self._client.ping())
        except Exception:
            return False

    async def append(self, key: str, value: Any, expiration_seconds: int | None = None) -> str | None:
        """Append value into key via rpush
        
        Args:
            key: key
            value: JSON serializable value
            expiration_seconds: expires
        
        Returns:
            key if success else none
        """
        
        encoded = self._encode(value)
        if encoded is None:
            return None

        client = self._require_client()
        await client.rpush(key, encoded)
        ok = await self._apply_expiration(key, expiration_seconds)
        if not ok:
            logger.warning(f"Key:{key} is updated without expiration.")
        return key

    async def set(self, key: str, value: Any, expiration_seconds: int | None = None) -> str | None:
        encoded = self._encode(value)
        if encoded is None:
            return None

        client = self._require_client()
        ttl = self._ttl_seconds if expiration_seconds is None else expiration_seconds
        await client.set(key, encoded, ex=ttl)
        ok = await self._apply_expiration(key, expiration_seconds)
        if not ok:
            logger.warning(f"Key:{key} is set without expiration.")
        return key

    async def delete(self, key: str) -> Any | None:
        client = self._require_client()

        key_type = await client.type(key)
        if key_type == "none":
            logger.warning("Redis key `%s` does not exist.", key)
            return None

        deleted_value = await self._read_deleted_value(key, key_type)
        if deleted_value is None:
            logger.warning(
                "Redis key `%s` has unsupported type `%s`; deleting without returning value.",
                key,
                key_type,
            )
        await client.delete(key)
        return deleted_value

    def _encode(self, value: Any) -> str | None:
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            logger.warning("Redis value type `%s` is not JSON serializable.", type(value).__name__)
            return None

    def _decode(self, value: str | None) -> Any:
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    async def _apply_expiration(self, key: str, expiration_seconds: int | None) -> bool:
        ttl = expiration_seconds if expiration_seconds is not None else self._ttl_seconds
        if ttl is None:
            return False
        client = self._require_client()
        await client.expire(key, ttl)
        return True

    async def _read_deleted_value(self, key: str, key_type: str) -> str | list | None:
        client = self._require_client()
        if key_type == "string":
            raw = await client.get(key)
            return self._decode(raw)
        if key_type == "list":
            rows = await client.lrange(key, 0, -1)
            return [self._decode(row) for row in rows]

        return None

    def _require_client(self) -> Redis:
        if self._client is None:
            raise RuntimeError("Redis client is not connected. Call connect() first.")
        return self._client
