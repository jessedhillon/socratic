"""Tests for organization API endpoints."""

from __future__ import annotations

import typing as t

from fastapi.testclient import TestClient

from socratic.model import Organization


class TestGetOrganizationBySlug:
    """Tests for GET /api/organizations/by-slug/{slug}."""

    def test_returns_organization_for_valid_slug(
        self,
        client: TestClient,
        test_org: Organization,
    ) -> None:
        """Successfully fetch an organization by its slug."""
        response = client.get(f"/api/organizations/by-slug/{test_org.slug}")

        assert response.status_code == 200
        data = response.json()
        assert data["organization_id"] == str(test_org.organization_id)
        assert data["name"] == test_org.name
        assert data["slug"] == test_org.slug

    def test_returns_404_for_nonexistent_slug(
        self,
        client: TestClient,
    ) -> None:
        """Return 404 when organization slug does not exist."""
        response = client.get("/api/organizations/by-slug/nonexistent-org")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Organization not found"

    def test_does_not_require_authentication(
        self,
        client: TestClient,
        test_org: Organization,
    ) -> None:
        """Endpoint should be accessible without authentication headers."""
        # Make request without any auth headers
        response = client.get(
            f"/api/organizations/by-slug/{test_org.slug}",
            headers={},
        )

        assert response.status_code == 200

    def test_returns_only_public_fields(
        self,
        client: TestClient,
        test_org: Organization,
    ) -> None:
        """Response should contain only public organization info."""
        response = client.get(f"/api/organizations/by-slug/{test_org.slug}")

        assert response.status_code == 200
        data = response.json()

        # Should have these public fields
        assert "organization_id" in data
        assert "name" in data
        assert "slug" in data

        # Should NOT have sensitive/private fields
        assert "create_time" not in data
        assert "update_time" not in data

    def test_multiple_organizations(
        self,
        client: TestClient,
        org_factory: t.Callable[..., Organization],
    ) -> None:
        """Can fetch different organizations by their respective slugs."""
        org1 = org_factory(name="First School", slug="first-school")
        org2 = org_factory(name="Second School", slug="second-school")

        response1 = client.get(f"/api/organizations/by-slug/{org1.slug}")
        response2 = client.get(f"/api/organizations/by-slug/{org2.slug}")

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        assert data1["name"] == "First School"
        assert data2["name"] == "Second School"
