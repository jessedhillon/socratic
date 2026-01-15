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


class StorageSettings(BaseSettings):
    persistent: PersistentSettings
    redis: RedisSettings | None = None
    # ephemeral: MemcachedDsn
    # messaging: p.AmqpDsn


class PersistentSettings(BaseSettings):
    postgresql: PostgresqlSettings


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
