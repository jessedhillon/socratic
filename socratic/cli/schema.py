from __future__ import annotations

import alembic.command
import alembic.config

import socratic.lib.cli as click
from socratic.core import di


@click.group("schema")
def schema(): ...


@schema.command()
@click.option("--verbose", "-v", is_flag=True, default=False)
@di.inject
def current(verbose: bool, alembic_conf: alembic.config.Config = di.Provide["storage.persistent.alembic_config"]):
    alembic.command.current(alembic_conf, verbose=verbose)


@schema.command()
@di.inject
def init(alembic_conf: alembic.config.Config = di.Provide["storage.persistent.alembic_config"]):
    path = alembic_conf.get_main_option("script_location")
    assert path is not None
    alembic_conf.config_file_name = "alembic.ini"
    alembic.command.init(alembic_conf, path)


@schema.command()
@click.argument("message")
@di.inject
def generate(message: str, alembic_conf: alembic.config.Config = di.Provide["storage.persistent.alembic_config"]):
    alembic.command.revision(alembic_conf, message)


@schema.command()
@click.argument("revision")
@di.inject
def up(revision: str, alembic_conf: alembic.config.Config = di.Provide["storage.persistent.alembic_config"]):
    alembic.command.upgrade(alembic_conf, revision)


@schema.command()
@click.argument("revision")
@di.inject
def down(revision: str, alembic_conf: alembic.config.Config = di.Provide["storage.persistent.alembic_config"]):
    alembic.command.downgrade(alembic_conf, revision)


@schema.command()
@di.inject
def branches(alembic_conf: alembic.config.Config = di.Provide["storage.persistent.alembic_config"]):
    alembic.command.branches(alembic_conf, verbose=True)


@schema.command()
@click.option("--verbose", "-v", is_flag=True, default=False)
@di.inject
def history(verbose: bool, alembic_conf: alembic.config.Config = di.Provide["storage.persistent.alembic_config"]):
    alembic.command.history(alembic_conf, verbose=verbose, indicate_current=True)


@schema.command()
@click.argument("revision")
@di.inject
def stamp(revision: str, alembic_conf: alembic.config.Config = di.Provide["storage.persistent.alembic_config"]):
    alembic.command.stamp(alembic_conf, revision)


command = schema
