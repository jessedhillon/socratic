from __future__ import annotations

import importlib
import sys
import threading
import types
import typing as t
from pathlib import Path

import pydantic as p

import socratic
import socratic.lib.cli as click
from socratic.core import di, SocraticContainer
from socratic.model import DeploymentEnvironment

_configured = False
_SocraticRoot = Path(socratic.__file__).resolve().parents[1]

_wiring: list[types.ModuleType] = []


class SocraticMultiCommand(click.Group):
    def list_commands(self, ctx: click.Context) -> t.List[str]:
        return ["data", "example", "schema", "script", "web"]

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Group:
        global _wiring
        assert cmd_name in self.list_commands(ctx)
        mod = importlib.import_module(f"socratic.cli.{cmd_name}")
        _wiring.append(mod)
        return getattr(mod, cmd_name)


@click.group(cls=SocraticMultiCommand)
@click.option("-E", "--env", default=DeploymentEnvironment.Local, type=click.EnumType(DeploymentEnvironment))
@click.option("-c", "--config-root", default=_SocraticRoot / "config", type=click.URIParamType(dir_ok=True))
@click.option("-s", "--secrets-path", default=None, type=click.URIParamType())
@click.option(
    "-o",
    "--override",
    multiple=True,
    help="configuration path parameter-value pairs to override config with, e.g., -o sync.socket.type=fifo",
)
@click.option("-D", "--debug", is_flag=True, default=False)
@click.pass_obj
@di.inject
def main(
    ct: SocraticContainer,
    env: DeploymentEnvironment,
    config_root: p.FileUrl,
    secrets_path: p.AnyUrl | None,
    override: tuple[str, ...],
    debug: bool,
):
    global _configured, _wiring
    SocraticContainer.boot(
        ct,
        debug=debug,
        env=env,
        config_root=config_root,
        secrets_path=secrets_path,
        override=override,
        wiring=tuple(_wiring),
    )
    _configured = True


def execute_command(*_args: str) -> None:
    threading.current_thread().name = "socratic-0"
    args = list(_args or sys.argv)

    # Strip away full path to fix program name in help message
    args[0] = Path(args[0]).name
    container = SocraticContainer()

    try:
        with main.make_context(args[0], args=args[1:]) as ctx:
            ctx.obj = container
            rs = t.cast(int, main.invoke(ctx))
            sys.exit(rs)
    except (EOFError, KeyboardInterrupt, click.Abort):
        click.echo("Aborted!", file=sys.stderr)
        sys.exit(1)
    except click.exceptions.Exit:
        sys.exit(0)
    except Exception as ex:
        click.echo(click.style("ERROR ", fg="red"), nl=False, file=sys.stderr)
        click.echo(str(ex), file=sys.stderr)

        if container.debug() or (not _configured and "-D" in sys.argv[1:]):
            import traceback

            import jdbpp

            traceback.print_exc()
            jdbpp.post_mortem()  # pyright: ignore [reportUnknownMemberType]
        if isinstance(ex, click.ClickException):
            sys.exit(ex.exit_code)
        sys.exit(-1)
    finally:
        container.shutdown_resources()


if __name__ == "__main__":
    execute_command(*sys.argv)
