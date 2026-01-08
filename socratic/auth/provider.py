"""Auth provider protocol for pluggable authentication backends."""

from __future__ import annotations

import typing as t
from abc import abstractmethod

from socratic.model import OrganizationID, User, UserID


class AuthResult(t.NamedTuple):
    """Result of an authentication attempt."""

    success: bool
    user: User | None = None
    error: str | None = None


class AuthProvider(t.Protocol):
    """Protocol for authentication providers.

    Implementations can use different backends (local, Cognito, etc.)
    while exposing a consistent interface.
    """

    @abstractmethod
    def authenticate(self, email: str, password: str) -> AuthResult:
        """Authenticate a user with email and password.

        Returns:
            AuthResult with success=True and user if valid,
            or success=False and error message if invalid.
        """
        ...

    @abstractmethod
    def register(
        self,
        email: str,
        password: str,
        name: str,
        organization_id: OrganizationID,
        role: str,
    ) -> AuthResult:
        """Register a new user.

        Args:
            email: User's email address
            password: Plain text password to hash
            name: User's display name
            organization_id: Organization to add user to
            role: Role within organization (educator/learner)

        Returns:
            AuthResult with the created user or error.
        """
        ...

    @abstractmethod
    def get_user(self, user_id: UserID) -> User | None:
        """Get a user by ID."""
        ...

    @abstractmethod
    def set_password(self, user_id: UserID, password: str) -> bool:
        """Set/update a user's password.

        Returns:
            True if successful, False if user not found.
        """
        ...

    @abstractmethod
    def verify_password(self, user_id: UserID, password: str) -> bool:
        """Verify a user's password.

        Returns:
            True if password matches, False otherwise.
        """
        ...
