"""Tests for authentication API endpoints."""

from __future__ import annotations

import datetime
import typing as t

import jwt as pyjwt
import pydantic as p
from fastapi.testclient import TestClient

from socratic.core import di
from socratic.model import Organization, User, UserRole


@di.inject
def encode_jwt(
    payload: dict[str, t.Any],
    jwt_secret: p.Secret[str] = di.Provide["secrets.auth.jwt"],
    jwt_algorithm: str = di.Provide["config.web.socratic.auth.jwt_algorithm"],
) -> str:
    """Encode a JWT token using injected config."""
    return pyjwt.encode(payload, jwt_secret.get_secret_value(), algorithm=jwt_algorithm)


@di.inject
def decode_jwt(
    token: str,
    jwt_secret: p.Secret[str] = di.Provide["secrets.auth.jwt"],
    jwt_algorithm: str = di.Provide["config.web.socratic.auth.jwt_algorithm"],
) -> dict[str, t.Any]:
    """Decode a JWT token using injected config."""
    return pyjwt.decode(token, jwt_secret.get_secret_value(), algorithms=[jwt_algorithm])


class TestLogin:
    """Tests for POST /api/auth/login."""

    def test_login_success_returns_token(
        self,
        client: TestClient,
        test_user: User,
        test_org: Organization,
    ) -> None:
        """Successfully login with valid credentials."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": "learner@test.com",
                "password": "password123",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Check user info
        assert data["user"]["email"] == "learner@test.com"
        assert data["user"]["name"] == "Test Learner"
        assert data["user"]["organization_id"] == str(test_org.organization_id)
        assert data["user"]["role"] == "learner"

        # Check token
        assert "access_token" in data["token"]
        assert "expires_at" in data["token"]
        assert data["token"]["access_token"] is not None

    def test_login_invalid_email_returns_401(
        self,
        client: TestClient,
        test_user: User,
    ) -> None:
        """Return 401 for non-existent email."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@test.com",
                "password": "password123",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_login_invalid_password_returns_401(
        self,
        client: TestClient,
        test_user: User,
    ) -> None:
        """Return 401 for incorrect password."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": "learner@test.com",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_login_user_without_org_returns_403(
        self,
        client: TestClient,
        user_factory: t.Callable[..., User],
    ) -> None:
        """Return 403 when user has no organization membership."""
        # Create user without organization
        user_factory(
            email="orphan@test.com",
            password="password123",
            organization_id=None,
        )

        response = client.post(
            "/api/auth/login",
            json={
                "email": "orphan@test.com",
                "password": "password123",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "User has no organization membership"

    def test_login_token_can_be_decoded(
        self,
        client: TestClient,
        test_user: User,
        test_org: Organization,
    ) -> None:
        """Token returned from login is valid and contains expected claims."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": "learner@test.com",
                "password": "password123",
            },
        )

        assert response.status_code == 200
        token = response.json()["token"]["access_token"]

        # Decode and verify token
        payload = decode_jwt(token)

        assert payload["sub"] == str(test_user.user_id)
        assert payload["org"] == str(test_org.organization_id)
        assert payload["role"] == "learner"
        assert "exp" in payload
        assert "iat" in payload


class TestRegister:
    """Tests for POST /api/auth/register."""

    def test_register_success_with_valid_invite(
        self,
        client: TestClient,
        test_org: Organization,
        user_factory: t.Callable[..., User],
    ) -> None:
        """Successfully register with a valid invite token."""
        # Create inviter user
        inviter = user_factory(
            email="educator@test.com",
            organization_id=test_org.organization_id,
            role=UserRole.Educator,
        )

        # Create invite token
        expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=7)
        invite_payload = {
            "type": "invite",
            "email": "newuser@test.com",
            "org": str(test_org.organization_id),
            "role": "learner",
            "inviter": str(inviter.user_id),
            "exp": int(expires_at.timestamp()),
        }
        invite_token = encode_jwt(invite_payload)

        response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "securepassword",
                "name": "New User",
                "invite_token": invite_token,
            },
        )

        assert response.status_code == 201
        data = response.json()

        # Check user info
        assert data["user"]["email"] == "newuser@test.com"
        assert data["user"]["name"] == "New User"
        assert data["user"]["organization_id"] == str(test_org.organization_id)
        assert data["user"]["role"] == "learner"

        # Check token
        assert "access_token" in data["token"]

    def test_register_expired_invite_returns_400(
        self,
        client: TestClient,
        test_org: Organization,
    ) -> None:
        """Return 400 for expired invite token."""
        # Create expired invite token
        expired_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)
        invite_payload = {
            "type": "invite",
            "email": "newuser@test.com",
            "org": str(test_org.organization_id),
            "role": "learner",
            "inviter": "some-user-id",
            "exp": int(expired_at.timestamp()),
        }
        invite_token = encode_jwt(invite_payload)

        response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "securepassword",
                "name": "New User",
                "invite_token": invite_token,
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invite token has expired"

    def test_register_invalid_invite_returns_400(
        self,
        client: TestClient,
    ) -> None:
        """Return 400 for invalid invite token."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "securepassword",
                "name": "New User",
                "invite_token": "invalid-token",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid invite token"

    def test_register_email_mismatch_returns_400(
        self,
        client: TestClient,
        test_org: Organization,
    ) -> None:
        """Return 400 when email doesn't match invite."""
        expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=7)
        invite_payload = {
            "type": "invite",
            "email": "invited@test.com",
            "org": str(test_org.organization_id),
            "role": "learner",
            "inviter": "some-user-id",
            "exp": int(expires_at.timestamp()),
        }
        invite_token = encode_jwt(invite_payload)

        response = client.post(
            "/api/auth/register",
            json={
                "email": "different@test.com",  # Different from invite
                "password": "securepassword",
                "name": "New User",
                "invite_token": invite_token,
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Email does not match invite"

    def test_register_wrong_token_type_returns_400(
        self,
        client: TestClient,
        test_org: Organization,
    ) -> None:
        """Return 400 when token is not an invite type."""
        expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=7)
        # Create a regular access token, not an invite
        payload = {
            "sub": "some-user-id",
            "org": str(test_org.organization_id),
            "role": "learner",
            "exp": int(expires_at.timestamp()),
            "iat": int(datetime.datetime.now(datetime.UTC).timestamp()),
        }
        token = encode_jwt(payload)

        response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "securepassword",
                "name": "New User",
                "invite_token": token,
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid invite token"


class TestGetCurrentUser:
    """Tests for GET /api/auth/me."""

    def test_get_me_with_valid_token(
        self,
        client: TestClient,
        test_user: User,
        test_org: Organization,
    ) -> None:
        """Successfully get current user with valid token."""
        # First login to get token
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": "learner@test.com",
                "password": "password123",
            },
        )
        token = login_response.json()["token"]["access_token"]

        # Get current user
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "learner@test.com"
        assert data["name"] == "Test Learner"
        assert data["organization_id"] == str(test_org.organization_id)
        assert data["role"] == "learner"

    def test_get_me_without_token_returns_401(
        self,
        client: TestClient,
    ) -> None:
        """Return 401 when no token provided."""
        response = client.get("/api/auth/me")

        assert response.status_code == 401

    def test_get_me_with_invalid_token_returns_401(
        self,
        client: TestClient,
    ) -> None:
        """Return 401 for invalid token."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401


class TestLogout:
    """Tests for POST /api/auth/logout."""

    def test_logout_with_valid_token(
        self,
        client: TestClient,
        test_user: User,
    ) -> None:
        """Successfully logout with valid token."""
        # First login to get token
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": "learner@test.com",
                "password": "password123",
            },
        )
        token = login_response.json()["token"]["access_token"]

        # Logout
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"

    def test_logout_without_token_returns_401(
        self,
        client: TestClient,
    ) -> None:
        """Return 401 when no token provided."""
        response = client.post("/api/auth/logout")

        assert response.status_code == 401
