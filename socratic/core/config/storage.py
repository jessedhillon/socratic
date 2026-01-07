from __future__ import annotations

import typing as t

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
    # ephemeral: MemcachedDsn
    # messaging: p.AmqpDsn


class PersistentSettings(BaseSettings):
    postgresql: PostgresqlSettings


class PostgresqlSettings(BaseSettings):
    host: p.IPvAnyAddress | str | None = None
    port: int = 5432
    database: str
    driver: t.Literal["postgresql+psycopg"] = "postgresql+psycopg"
