import datetime
import inspect
import logging.config
import pathlib
import typing as t

from .logging import TraceLogLevelLogger

TimestampProvider = t.Callable[..., datetime.datetime]


def trace(msg: str, *args: t.Any, **kwargs: t.Any):
    if len(logging.root.handlers) == 0:
        logging.basicConfig()
    t.cast(TraceLogLevelLogger, logging.root).trace(msg, *args, **kwargs)


class LoggingProvider(object):
    Function: t.Final[t.Literal["fn"]] = "fn"
    Class: t.Final[t.Literal["cls"]] = "cls"
    Module: t.Final[t.Literal["mod"]] = "mod"

    def __init__(self, config: dict[str, t.Any], debug: bool):
        LoggingProvider.create_trace_loglevel()
        logging.config.dictConfig(config)
        if debug:
            self.capture_warnings(True)

    @staticmethod
    def create_trace_loglevel():
        """
        Create a log level TRACE = 5
        """
        logging.setLoggerClass(TraceLogLevelLogger)
        logging.addLevelName(5, "TRACE")
        logging.TRACE = 5  # pyright: ignore [reportAttributeAccessIssue]
        logging.trace = trace  # pyright: ignore [reportAttributeAccessIssue]

    @classmethod
    def get_logger(
        cls, scope: t.Literal["mod", "cls", "fn"] = "mod", name: str | None = None, n_frames: int = 1
    ) -> TraceLogLevelLogger:
        if name:
            return t.cast(TraceLogLevelLogger, logging.getLogger(name))

        stack = inspect.stack()
        match scope:
            case cls.Module:
                name = stack[n_frames].frame.f_globals["__name__"]

            case cls.Function:
                mod = stack[n_frames].frame.f_globals["__name__"]
                fn = stack[n_frames].function
                locals = stack[n_frames].frame.f_locals
                if "self" in locals and hasattr(locals["self"], "__class__"):
                    cls = locals["self"].__class__
                    name = f"{mod}.{cls.__name__}.{fn}"
                else:
                    name = f"{mod}.{fn}"

            case cls.Class:
                locals = stack[1].frame.f_locals
                if "self" in locals and hasattr(locals["self"], "__class__"):
                    cls = locals["self"].__class__
                elif "cls" in locals and isinstance(locals["cls"], type):
                    cls = locals["cls"]
                else:
                    raise RuntimeError("could not determine class")
                mod = cls.__module__
                name = f"{mod}.{cls.__name__}"

        return t.cast(TraceLogLevelLogger, logging.getLogger(name))

    @staticmethod
    def capture_warnings(capture: bool):
        logging.captureWarnings(capture)


class FixtureProvider(object):
    @t.overload
    @staticmethod
    def load(p: str | pathlib.Path, mode: t.Literal["r"] = "r") -> str: ...

    @t.overload
    @staticmethod
    def load(p: str | pathlib.Path, mode: t.Literal["rb"]) -> bytes: ...

    @staticmethod
    def load(p: str | pathlib.Path, mode: t.Literal["r", "rb"] = "r") -> str | bytes: ...

    @t.overload
    @staticmethod
    def open(path: str | pathlib.Path, mode: t.Literal["r"] = "r") -> t.TextIO: ...

    @t.overload
    @staticmethod
    def open(path: str | pathlib.Path, mode: t.Literal["rb"]) -> t.BinaryIO: ...

    @staticmethod
    def open(path: str | pathlib.Path, mode: t.Literal["r", "rb"] = "r") -> t.TextIO | t.BinaryIO: ...
