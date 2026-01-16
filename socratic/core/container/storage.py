from __future__ import annotations

import importlib.util
import os
import sys
import types
import typing as t
from pathlib import Path

import alembic.config
import psycopg
import sqlalchemy
import sqlalchemy.event
import sqlalchemy.orm
from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration, Container, Factory, Object, Provider, Resource, Singleton
from psycopg.adapt import Buffer, Loader
from psycopg.types import TypeInfo
from psycopg.types.array import register_array
from psycopg.types.string import StrDumper
from sqlalchemy.engine.url import URL as DSN

import socratic.lib.json as json
import socratic.lib.uuid as uuid
from socratic.lib.sql import DebugQuery, DebugSession

from ..config.secrets import PostgresqlSecrets
from ..config.storage import PostgresqlSettings, StorageSettings
from ..di import NotReady
from ..provider import LoggingProvider
from .streaming import StreamingContainer


def provide_alembic_conf(
    migration_path: Path, config: PostgresqlSettings, secrets: PostgresqlSecrets, root: Path | NotReady
) -> alembic.config.Config:
    if isinstance(root, NotReady):
        raise RuntimeError("root path is unavailable")

    dsn = DSN.create(
        config.driver,
        port=config.port,
        host=str(config.host) if config.host else None,
        username=secrets.username.get_secret_value() if secrets.username else None,
        password=secrets.password.get_secret_value() if secrets.password else None,
        database=config.database,
    )
    escaped_str = dsn.render_as_string(hide_password=False).replace("%", "%%")

    ac = alembic.config.Config()
    ac.set_main_option("script_location", str(root / migration_path))
    ac.set_section_option("alembic", "sqlalchemy.url", escaped_str)
    ac.set_section_option("alembic", "file_template", "%%(year)d-%%(month).2d-%%(day).2d-%%(slug)s-%%(rev)s")
    return ac


def provide_engine(
    config: PostgresqlSettings, secrets: PostgresqlSecrets, logging: LoggingProvider
) -> sqlalchemy.Engine:
    logger = logging.get_logger()

    dsn = DSN.create(
        config.driver,
        database=config.database,
        username=secrets.username.get_secret_value() if secrets.username else None,
        password=secrets.password.get_secret_value() if secrets.password else None,
        port=config.port,
        host=str(config.host) if config.host else None,
    )

    engine = sqlalchemy.create_engine(dsn, json_serializer=json.dumps, json_deserializer=json.loads)
    sqlalchemy.event.listen(engine, "connect", register_uuid)
    sqlalchemy.event.listen(engine, "connect", register_path)
    sqlalchemy.event.listen(engine, "connect", register_timezone)
    logger.info(
        "initialized SQLAlchemy engine",
        extra={
            "driver": config.driver,
            "database": config.database,
            "host": config.host,
            "port": config.port,
        },
    )
    return engine


def provide_session(debug: bool, engine: sqlalchemy.Engine) -> sqlalchemy.orm.Session:
    """Create a new session. Caller is responsible for closing it (via di.Manage)."""
    if debug:
        maker = sqlalchemy.orm.sessionmaker(engine, class_=DebugSession, expire_on_commit=False, autoflush=False)
        return maker(query_cls=DebugQuery, autobegin=False)
    else:
        maker = sqlalchemy.orm.sessionmaker(engine, expire_on_commit=False, autoflush=False)
        return maker(autobegin=False)


def provide_fixtures(root: Path | NotReady) -> types.ModuleType:
    if isinstance(root, NotReady):
        raise RuntimeError("root path is unavailable")

    fp = root / "fixtures"
    spec = importlib.util.spec_from_file_location("socratic_fixtures", os.path.join(fp, "__init__.py"))
    if not (spec and spec.loader):
        raise RuntimeError(f"could not provide fixture loader: {fp}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["socratic_fixtures"] = module  # register in sys.modules
    spec.loader.exec_module(module)  # Execute the module
    return module


class PersistentContainer(DeclarativeContainer):
    config = Configuration()
    secrets = Configuration()
    debug: Provider[bool] = Object()
    logging: Provider[LoggingProvider] = Resource()
    root: Provider[Path | NotReady] = Object()

    alembic_config: Provider[alembic.config.Config] = Singleton(
        provide_alembic_conf,
        migration_path=Path("migrations/"),
        config=config.postgresql.as_(PostgresqlSettings),
        secrets=secrets.postgresql.as_(PostgresqlSecrets),
        root=root,
    )
    engine: Provider[sqlalchemy.Engine] = Singleton(
        provide_engine,
        config=config.postgresql.as_(PostgresqlSettings),
        secrets=secrets.postgresql.as_(PostgresqlSecrets),
        logging=logging,
    )
    session: Provider[sqlalchemy.orm.Session] = Factory(provide_session, debug=debug, engine=engine)


class StorageContainer(DeclarativeContainer):
    config: Provider[StorageSettings] = Configuration(strict=True)
    secrets: Provider[StorageSettings] = Configuration(strict=True)
    debug: Provider[bool] = Object()
    logging: Provider[LoggingProvider] = Resource()
    root: Provider[Path | NotReady] = Object()

    fixtures: Provider[types.ModuleType] = Singleton(provide_fixtures, root=root)
    persistent: Provider[PersistentContainer] = Container(
        PersistentContainer, config=config.persistent, secrets=secrets, debug=debug, logging=logging, root=root
    )
    streaming: Provider[StreamingContainer] = Container(StreamingContainer, config=config.streaming)


class UUIDLoader(Loader):
    def load(self, data: Buffer | None) -> uuid.UUID | None:
        if data is None:
            return None
        return uuid.UUID(bytes=bytes(data))


def register_uuid(conn: psycopg.connection.Connection[t.Any], _: t.Any) -> None:
    uuid_oid, uuid_array_oid = 2950, 2951
    psycopg.adapters.register_loader("uuid", UUIDLoader)
    info = TypeInfo("uuid", uuid_oid, uuid_array_oid)
    register_array(info)


def register_path(conn: psycopg.connection.Connection[t.Any], _: t.Any) -> None:
    psycopg.adapters.register_dumper(Path, StrDumper)


def register_timezone(dbapi_conn: t.Any, _: t.Any) -> None:
    """Set connection timezone to UTC for consistent datetime handling.

    PostgreSQL TIMESTAMP WITH TIME ZONE stores timestamps in UTC but returns
    them converted to the connection's timezone. Setting UTC ensures consistent
    timezone-aware datetimes across all environments.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("SET TIMEZONE TO 'UTC'")
    cursor.close()
