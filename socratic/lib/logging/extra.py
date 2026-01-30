import inspect
import json
import logging
import string
import textwrap
import typing as t

import pygments
from pygments.formatters import Terminal256Formatter
from pygments.lexers.data import JsonLexer  # pyright: ignore [reportMissingTypeStubs]
from pygments.style import Style

from socratic.lib.json import JSONValue

from .json import JSONEncoder
from .style import LogStyle

ReservedKeys = {
    "exception",
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "id",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "taskName",
    "thread",
    "threadName",
}


class ExtraFormatter(logging.Formatter):
    def __init__(
        self,
        base: type[logging.Formatter],
        format: str | None,
        datefmt: str | None = None,
        indent: bool = True,
        pyg_style: t.Type[Style] = LogStyle,
        style: t.Literal["%", "{", "$"] = "%",
        validate: bool = True,
        *,
        defaults: t.Any = None,
        **kwargs: t.Any,
    ):
        self.base = base(format, datefmt=datefmt, style=style, validate=validate, defaults=defaults, **kwargs)
        self.pyg_style = pyg_style
        self.handler = None
        self.indent = indent

    def format(self, record: logging.LogRecord) -> str:
        if "color_message" in record.__dict__:
            record.msg = record.__dict__.pop("color_message")

        msg = record.getMessage()
        if "\n" in msg:
            formatted = self.base.format(record)
            idx = formatted.find(msg)
            indent = " " * len([c for c in formatted[:idx] if c in string.printable])
            line, *lines = msg.splitlines()
            body = textwrap.indent("\n".join(lines), prefix=indent)
            record.msg = record.message = f"{line}\n{body}"
            record.args = None
        message = self.base.format(record)

        d = record.__dict__
        extra = {k: d[k] for k in set(d.keys()) - ReservedKeys}

        if not extra:
            return message

        encoder = JSONEncoder()

        def encode(obj: t.Any) -> JSONValue:
            try:
                return encoder.default(obj)
            except:  # noqa: E722
                return repr(obj)

        if self.handler is None:
            # we fix up our handler because we won't have access to it during construction
            frame = inspect.currentframe()
            assert frame is not None and frame.f_back is not None and "self" in frame.f_back.f_locals, (
                "where are we called from?"
            )
            self.handler = frame.f_back.f_locals["self"]

        js = json.dumps(extra, sort_keys=True, indent=(4 if self.indent else None), default=encode)
        do_color = not getattr(self.base, "no_color", False)
        if self.handler.stream.isatty() and do_color:
            hl = pygments.highlight  # pyright: ignore [reportUnknownMemberType, reportUnknownVariableType]
            ps = hl(js, JsonLexer(), Terminal256Formatter[str](style=self.pyg_style), None)
        else:
            ps = js
        return message + " " + ps.strip()

    def __getattr__(self, name: str) -> t.Any:
        return getattr(self.base, name)
