from __future__ import annotations

import enum
import gettext
import pathlib
import typing as t

import click
import pydantic as p
from click import *  # noqa: F401, F403 # pyright: ignore [reportWildcardImportFromLibrary]

import socratic.lib.uuid as uuid

# This module is a thin wrapper around Click, which is why we import `click.*`
# into our namespace. We create a class `SocraticCommand`. On invocation, we
# inject the `SocraticContainer` at runtime and add key artifacts from
# our current context into the container:
#
#   - `SocraticContainer.command`: a friendly name for the invoked command
#   - `SocraticContainer.contexts`: a list of command names and arguments which
#     click encountered during parsing


class EnumType(click.ParamType):
    """specify click params to be members of an enum"""

    def __init__(self, enum: t.Type[enum.Enum]):
        self.enum = enum
        self.name = self.enum_name

    @property
    def values(self) -> list[str]:
        return [e.value for e in self.enum]

    @property
    def enum_name(self) -> str:
        v = list(self.enum).pop()
        return v.__class__.__name__

    def convert(
        self, value: str | enum.Enum | None, param: click.Parameter | None, ctx: click.Context | None
    ) -> enum.Enum | None:
        if value is None:
            return None

        try:
            return self.enum(value)
        except ValueError:
            self.fail(f"valid {self.enum_name} values {self.values}")

    def __repr__(self) -> str:
        return self.enum_name


class RequiredXOROption(click.Option):
    """
    Exclusive option, ensures only one of a given set of options is set

    See https://stackoverflow.com/a/51235564"""

    def __init__(self, *args: t.Any, required_xor: list[str], **kwargs: t.Any):
        if not required_xor:
            raise ValueError(required_xor)
        self.required_xor = set(required_xor)

        h = f"{kwargs['help']} " if "help" in kwargs else ""
        kwargs["help"] = f"{h} (Option is mutually exclusive with {self.pretty_xor})".strip()
        super().__init__(*args, **kwargs)

    @property
    def pretty_xor(self) -> str:
        return ", ".join(self.required_xor)

    @property
    def pretty_self_xor(self) -> str:
        if self.name is None:
            return self.pretty_self_xor
        return ", ".join((self.name, self.pretty_xor))

    def handle_parse_result(self, ctx: click.Context, opts: t.Mapping[str, t.Any], args: t.Any):
        if self.name in opts:
            if any(set(opts.keys()) & self.required_xor):
                raise click.UsageError(f"Illegal usage: {self.name!s} is mutually exclusive with {self.pretty_xor}.")
        else:
            if not any(set(opts.keys()) & ({self.name} | self.required_xor)):
                raise click.UsageError(f"Exactly one of {self.pretty_self_xor} is required")
            self.prompt = None  # in case we are a prompting option, turn us off since we're not provided

        return super().handle_parse_result(ctx, opts, args)


class UUIDParamType(click.ParamType):
    name = "uuid"

    def convert(self, value: t.Any, param: click.Parameter | None, ctx: click.Context | None) -> uuid.UUID | None:
        if isinstance(value, uuid.UUID):
            return value

        value = value.strip()

        try:
            return uuid.UUID(value)
        except ValueError:
            self.fail(gettext.gettext(f"{value!r} is not a valid UUID."), param, ctx)

    def __repr__(self) -> str:
        return "UUID"


class URIParamType(click.ParamType):
    """
    Accept URIs as parameters, with optional existence enforcement on
    file:// URIs

    Arguments:

        - `file_ok`: (default `True`) param will accept a filesystem path as
          an argument and convert to a `file://` URI
        - `dir_ok`: (default `False`) if parsing results in `file://` URI,
          enforce path is not a directory
        - `file_exists`: (default `True`) if parsing results in `file://` URI,
          enforce that the path referenced exists
    """

    file_ok: bool
    dir_ok: bool
    file_exists: bool
    name: str

    def __init__(self, file_ok: bool = True, dir_ok: bool = False, file_exists: bool = True):
        self.file_ok = file_ok
        self.dir_ok = dir_ok
        self.file_exists = file_exists
        self.name = "URI OR PATH" if file_ok else "URI"

    def convert(
        self, value: str | pathlib.Path | None, param: click.Parameter | None, ctx: click.Context | None
    ) -> p.FileUrl | p.AnyUrl | None:
        if value is None:
            return None

        u = p.FileUrl(f"file://{value}") if isinstance(value, pathlib.Path) else p.AnyUrl(value)
        if u.scheme == "file":
            if self.file_ok:
                # promote paths to file:// URIs
                if u.path is None:
                    self.fail("file path not specified")
                path = pathlib.Path(u.path)
                if self.file_exists:
                    if not path.exists():
                        self.fail(f"{value}: no such file or directory", param, ctx)
                    if path.is_dir() and not self.dir_ok:
                        self.fail("directory path not accepted", param, ctx)
                return p.FileUrl(f"file://{path.absolute()}")
            else:
                self.fail("file URL not allowed")
        return u
