"""Streaming container for real-time event pub/sub."""

from __future__ import annotations

import typing as t

import redis.asyncio as aioredis
from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration, Factory, Provider, Singleton

from socratic.streaming.memory import InMemoryStreamBroker
from socratic.streaming.redis import RedisStreamBroker

from ..config.storage import RedisSettings


def provide_redis_client(config: RedisSettings | None) -> aioredis.Redis | None:  # type: ignore[type-arg]
    """Create an async Redis client.

    Uses Unix socket if configured, otherwise TCP connection.
    Returns None if Redis is not configured.
    """
    if config is None:
        return None

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


def provide_stream_broker(
    client: aioredis.Redis | None,  # type: ignore[type-arg]
) -> RedisStreamBroker | InMemoryStreamBroker:
    """Provide the stream broker implementation.

    Uses RedisStreamBroker if Redis is configured, otherwise InMemoryStreamBroker.
    """
    if client is not None:
        return RedisStreamBroker(client)
    return InMemoryStreamBroker()


class StreamingContainer(DeclarativeContainer):
    """Container for streaming infrastructure."""

    config: Provider[RedisSettings | None] = Configuration()

    redis_client: Provider[aioredis.Redis | None] = Singleton(  # type: ignore[type-arg]
        provide_redis_client,
        config=config.as_(t.cast(type[RedisSettings | None], RedisSettings)),
    )

    broker: Provider[RedisStreamBroker | InMemoryStreamBroker] = Factory(
        provide_stream_broker,
        client=redis_client,
    )
