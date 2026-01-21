from __future__ import annotations

import typing as t
from pathlib import Path

import pydantic as p

from .base import BaseSettings


class MemcachedDsn(p.AnyUrl):
    _constraints = p.UrlConstraints(
        allowed_schemes=[
            "memcached",
        ],
        default_host="localhost",
        default_port=11211,
    )


class ObjectSettings(BaseSettings):
    """Object storage settings for file uploads (videos, etc.)."""

    backend: t.Literal["local", "s3"] = "local"
    local_path: Path | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_prefix: str = "uploads/"


class StorageSettings(BaseSettings):
    persistent: PersistentSettings
    streaming: StreamingSettings | None = None
    object: ObjectSettings = ObjectSettings()
    # ephemeral: MemcachedDsn


class PersistentSettings(BaseSettings):
    postgresql: PostgresqlSettings


class StreamingSettings(BaseSettings):
    redis: RedisSettings


class PostgresqlSettings(BaseSettings):
    host: p.IPvAnyAddress | str | None = None
    port: int = 5432
    database: str
    driver: t.Literal["postgresql+psycopg"] = "postgresql+psycopg"


class RedisSettings(BaseSettings):
    """Redis connection settings.

    Supports either Unix socket or TCP connection.
    If socket_path is set, it takes precedence over host/port.
    """

    socket_path: Path | None = None
    host: str = "localhost"
    port: int = 6379
    database: int = 0
