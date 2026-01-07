import pathlib
import typing as t

import pydantic as p

from .base import BaseSettings


class BaseFormatterSettings(BaseSettings):
    datefmt: str | None = None
    format: str | None = None


class ExtraFormatterSettings(BaseFormatterSettings):
    class_: t.Literal["socratic.lib.logging.ExtraFormatter"] = p.Field(alias="()")
    base: str
    log_colors: dict[str, str]
    no_color: bool = False
    indent: bool | None = None


class TTYColoredFormatterSettings(BaseFormatterSettings):
    class_: t.Literal["colorlog.TTYColoredFormatter"] = p.Field(alias="()")


class LogstashFormatterSettings(BaseFormatterSettings):
    class_: t.Literal["socratic.lib.logging.logstash.LogstashFormatter"] = p.Field(alias="()")
    extra: dict[str, str]
    extra_prefix: str


FormatterSettings = t.Annotated[
    LogstashFormatterSettings | TTYColoredFormatterSettings | ExtraFormatterSettings, p.Field(discriminator="class_")
]


# https://github.com/python/cpython/blob/3.10/Lib/logging/__init__.py#L91-L98
LogLevel = t.Literal["NOTSET", "TRACE", "DEBUG", "INFO", "WARNING", "WARN", "ERROR", "FATAL", "CRITICAL"]


class BaseHandlerSettings(BaseSettings):
    formatter: str
    level: LogLevel


class StreamHandlerSettings(BaseHandlerSettings):
    class_: t.Literal["colorlog.StreamHandler"] = p.Field(alias="class")
    stream: p.AnyUrl

    @p.field_serializer("stream")
    def serialize_stream(self, v: p.AnyUrl) -> str:
        return str(self.stream)


class TimedRotatingFileHandlerSettings(BaseHandlerSettings):
    class_: t.Literal["logging.handlers.TimedRotatingFileHandler"] = p.Field(alias="class")
    backupCount: int
    filename: pathlib.Path
    when: str


class AsynchronousLogstashHandlerSettings(BaseHandlerSettings):
    class_: t.Literal["socratic.lib.logging.logstash.AsynchronousLogstashHandler"] = p.Field(alias="class")
    emit_args: bool
    database_path: pathlib.Path
    host: str
    port: int
    transport: str


HandlerSettings = t.Annotated[
    AsynchronousLogstashHandlerSettings | TimedRotatingFileHandlerSettings | StreamHandlerSettings,
    p.Field(discriminator="class_"),
]


class LoggerSettings(BaseSettings):
    level: LogLevel = "NOTSET"
    propagate: bool = True
    handlers: list[str] | None = None


class RootLoggerSettings(BaseSettings):
    handlers: list[str]
    level: LogLevel = "NOTSET"


class LoggingSettings(BaseSettings):
    version: t.Literal[1]
    disable_existing_loggers: bool = True
    formatters: dict[str, FormatterSettings]
    handlers: dict[str, HandlerSettings]
    root: RootLoggerSettings
    loggers: dict[str, LoggerSettings]
