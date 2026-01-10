"""Authentication container for dependency injection."""

from __future__ import annotations

from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration, Provider, Singleton

from socratic.auth.jwt import JWTManager


class AuthContainer(DeclarativeContainer):
    """Container for authentication services."""

    config: Configuration = Configuration()
    secrets: Configuration = Configuration()

    jwt_manager: Provider[JWTManager] = Singleton(
        JWTManager,
        secret_key=secrets.jwt,
        algorithm=config.jwt_algorithm,
        access_token_expire_minutes=config.access_token_expire_minutes,
    )
