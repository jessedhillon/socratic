"""Pytest fixtures for Socratic integration tests.

This module provides fixtures for testing API endpoints with a real database
connection. Tests run within a transaction that is rolled back after each test,
ensuring isolation without requiring a separate test database.

Usage:
    def test_get_organization(client: TestClient, test_org: Organization):
        response = client.get(f"/api/organizations/by-slug/{test_org.slug}")
        assert response.status_code == 200
"""

from __future__ import annotations

import os
import typing as t
from pathlib import Path

import pydantic as p
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import socratic
from socratic.core import SocraticContainer
from socratic.model import DeploymentEnvironment, Organization, OrganizationID
from socratic.storage.table import organizations


@pytest.fixture(scope="session")
def container() -> t.Generator[SocraticContainer]:
    """Boot the DI container for the test session.

    This fixture boots the container once per test session, providing
    access to configuration and services. Uses the Test environment
    which connects to the socratic_test database.
    """
    ct = SocraticContainer()
    root = Path(os.path.dirname(socratic.__file__)).parent

    SocraticContainer.boot(
        ct,
        debug=True,
        env=DeploymentEnvironment.Test,
        config_root=p.FileUrl(f"file://{root}/config"),
        override=(),
    )

    yield ct

    ct.shutdown_resources()


@pytest.fixture(scope="session")
def app(container: SocraticContainer) -> FastAPI:
    """Create the FastAPI application for testing.

    Uses the booted container to create the app with proper wiring.
    """
    from socratic.core.config.web import SocraticWebSettings
    from socratic.web.socratic.main import _create_app  # pyright: ignore[reportPrivateUsage]

    container.wire(
        modules=[
            "socratic.web.socratic.main",
            "socratic.web.socratic.route.organization",
            "socratic.auth.middleware",
        ]
    )

    return _create_app(
        config=SocraticWebSettings(**container.config.web.socratic()),
        env=DeploymentEnvironment.Test,
        root_path=t.cast(Path, container.root()),
    )


@pytest.fixture
def db_session(container: SocraticContainer) -> t.Generator[Session]:
    """Provide a database session wrapped in a transaction.

    Each test gets a fresh session within a transaction that is rolled
    back after the test completes. This ensures test isolation without
    requiring a separate test database.

    Uses join_transaction_mode="create_savepoint" so that session.begin()
    creates savepoints instead of failing when already in a transaction.
    This allows production code using session.begin() to work correctly
    while still enabling rollback at test end.
    """
    engine = container.storage().persistent().engine()

    # Start outer transaction on connection - this will be rolled back
    connection = engine.connect()
    transaction = connection.begin()

    # Create session bound to connection with savepoint mode
    # autobegin=False matches production, join_transaction_mode makes
    # begin() create savepoints since we're already in a transaction
    session = Session(
        bind=connection,
        autobegin=False,
        join_transaction_mode="create_savepoint",
    )

    yield session

    # Clean up: close session and rollback outer transaction
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(app: FastAPI, container: SocraticContainer, db_session: Session) -> t.Generator[TestClient]:
    """Provide a TestClient with database session override.

    Overrides the container's session provider so API requests use the
    same transactional session as the test, enabling rollback isolation.
    """
    container.storage().persistent().session.override(db_session)

    with TestClient(app) as test_client:
        yield test_client

    container.storage().persistent().session.reset_override()


@pytest.fixture
def org_factory(db_session: Session) -> t.Callable[..., Organization]:
    """Factory fixture for creating test organizations.

    Returns a callable that creates organizations with sensible defaults.
    Created organizations are automatically cleaned up via transaction rollback.

    Usage:
        def test_something(org_factory):
            org = org_factory(name="Test Org", slug="test-org")
    """

    def create_organization(
        name: str = "Test Organization",
        slug: str | None = None,
    ) -> Organization:
        from sqlalchemy import select

        # Generate unique slug if not provided
        org_id = OrganizationID()
        if slug is None:
            slug = f"test-org-{org_id.key[:8]}"

        with db_session.begin():
            org = organizations(
                organization_id=org_id,
                name=name,
                slug=slug,
            )
            db_session.add(org)
            db_session.flush()

            # Re-fetch as mapping to properly construct pydantic model
            stmt = select(organizations.__table__).where(organizations.organization_id == org_id)
            row = db_session.execute(stmt).mappings().one()
            return Organization(**row)

    return create_organization


@pytest.fixture
def test_org(org_factory: t.Callable[..., Organization]) -> Organization:
    """Provide a pre-created test organization.

    Convenience fixture for tests that just need a single organization.
    """
    return org_factory(name="Acme School")
