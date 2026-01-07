from __future__ import annotations

import importlib.machinery
import importlib.util
import re as regex
import typing as t
from pathlib import Path

import socratic.lib.cli as click
from socratic.core import SocraticContainer

_subcommands: dict[str, tuple[str, click.Command]] = {}


@click.group("script")
def script():
    pass


def make_command(name: str):
    global _subcommands

    @click.command(
        add_help_option=False,
        context_settings={
            "ignore_unknown_options": True,
        },
    )
    @click.pass_obj
    @click.pass_context
    @click.argument("script_args", nargs=-1, default=None, type=click.UNPROCESSED)
    def execute(
        ctx: click.Context,
        ct: SocraticContainer,
        script_args: tuple[str, ...],
    ) -> t.Any:
        fn, _ = _subcommands[name]
        spec = t.cast(importlib.machinery.ModuleSpec, importlib.util.find_spec(f"socratic.cli.script.{fn}"))
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        ct.wire([mod])
        nctx = mod.execute.make_context(ctx.command_path, args=list(script_args))
        return nctx.forward(mod.execute)

    return execute


# NOTE: we have to do it this way instead of using importlib because it's not
#       possible to unconditionally import arbitrary scripts and guarantee no
#       consequential (i.e. global) side effects
_slug_pattern = regex.compile("[^a-z0-9-]")
for p in Path(__file__).parent.glob("*.py"):
    fn = p.stem
    if fn.startswith("__"):
        continue
    cmd_name = _slug_pattern.sub("-", fn.lower())
    cmd = make_command(cmd_name)
    script.add_command(cmd, cmd_name)
    _subcommands[cmd_name] = (fn, cmd)
