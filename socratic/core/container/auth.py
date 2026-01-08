"""Authentication container for dependency injection."""

from __future__ import annotations

from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration, Factory, Provider, Singleton
from sqlalchemy.orm import Session

from socratic.auth.jwt import JWTManager
from socratic.auth.local import LocalAuthProvider


class AuthContainer(DeclarativeContainer):
    """Container for authentication services."""

    config: Configuration = Configuration()
    secrets: Configuration = Configuration()
    session: Provider[Session] = Provider()

    jwt_manager: Provider[JWTManager] = Singleton(
        JWTManager,
        secret_key=secrets.jwt_secret,
        algorithm=config.jwt_algorithm,
        access_token_expire_minutes=config.access_token_expire_minutes,
    )

    provider: Provider[LocalAuthProvider] = Factory(
        LocalAuthProvider,
        session=session,
    )
