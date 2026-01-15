"""Streaming container for real-time event pub/sub."""

from __future__ import annotations

import redis.asyncio as aioredis
from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration, Factory, Provider, Singleton

from socratic.storage.streaming.redis import RedisStreamBroker

from ..config.storage import RedisSettings


def provide_redis_client(config: RedisSettings) -> aioredis.Redis:
    """Create an async Redis client.

    Uses Unix socket if configured, otherwise TCP connection.
    """
    if config.socket_path:
        return aioredis.Redis(
            unix_socket_path=str(config.socket_path),
            db=config.database,
            decode_responses=False,
        )

    return aioredis.Redis(
        host=config.host,
        port=config.port,
        db=config.database,
        decode_responses=False,
    )


class StreamingContainer(DeclarativeContainer):
    """Container for streaming infrastructure (Redis Streams pub/sub)."""

    config = Configuration()

    redis: Provider[aioredis.Redis] = Singleton(
        provide_redis_client,
        config=config.redis.as_(RedisSettings),
    )

    broker: Provider[RedisStreamBroker] = Factory(
        RedisStreamBroker,
        client=redis,
    )
