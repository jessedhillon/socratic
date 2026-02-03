from __future__ import annotations

import typing as t

import annotated_types as ant
import pydantic as p

from .base import BaseSettings


class WebSettings(BaseSettings):
    example: ExampleWebSettings
    socratic: SocraticWebSettings | None = None
    flights: FlightsWebSettings | None = None


class ServeSettings(BaseSettings):
    host: p.IPvAnyAddress
    port: t.Annotated[int, ant.Gt(0), ant.Le(65535)]


class AuthSettings(BaseSettings):
    """Authentication settings for JWT tokens."""

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30


class ExampleWebSettings(BaseSettings):
    backend: ServeSettings
    frontend: ServeSettings | None = None


class SocraticWebSettings(BaseSettings):
    """Settings for the main Socratic web application."""

    backend: ServeSettings
    frontend: ServeSettings | None = None
    auth: AuthSettings = AuthSettings()


class FlightsWebSettings(BaseSettings):
    """Settings for the flights prompt experimentation service."""

    backend: ServeSettings
    frontend: ServeSettings | None = None
