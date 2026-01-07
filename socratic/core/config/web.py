from __future__ import annotations

import typing as t

import annotated_types as ant
import pydantic as p

from .base import BaseSettings


class WebSettings(BaseSettings):
    example: ExampleWebSettings


class ServeSettings(BaseSettings):
    host: p.IPvAnyAddress
    port: t.Annotated[int, ant.Gt(0), ant.Le(65535)]


class ExampleWebSettings(BaseSettings):
    backend: ServeSettings
    frontend: ServeSettings | None = None
