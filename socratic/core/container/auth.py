"""Authentication container for dependency injection."""

from __future__ import annotations

from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration


class AuthContainer(DeclarativeContainer):
    """Container for authentication services.

    Note: JWT functionality is now provided via module-level functions
    in socratic.auth.jwt that inject secrets/config at call time.
    This container provides configuration that can be wired to those functions.
    """

    config: Configuration = Configuration()
    secrets: Configuration = Configuration()
