"""Flights service SDK — async client for the flights HTTP API."""

from __future__ import annotations

import typing as t

import httpx

from socratic.model import FlightID, FlightStatus, SurveyDimension, SurveySchemaID


class SurveySchemaResult(object):
    """Result of creating or fetching a survey schema."""

    def __init__(
        self,
        schema_id: SurveySchemaID,
        name: str,
        version: int,
        dimensions_hash: str,
        is_default: bool,
    ) -> None:
        self.schema_id = schema_id
        self.name = name
        self.version = version
        self.dimensions_hash = dimensions_hash
        self.is_default = is_default


class FlightCreateResult(object):
    """Result of creating a flight."""

    def __init__(self, flight_id: FlightID, rendered_content: str) -> None:
        self.flight_id = flight_id
        self.rendered_content = rendered_content


class FlightsClient(object):
    """Async client for the flights HTTP API."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def create_flight(
        self,
        *,
        template: str,
        template_content: str,
        created_by: str,
        feature_flags: dict[str, t.Any],
        context: dict[str, t.Any],
        model_provider: str,
        model_name: str,
        model_config_data: dict[str, t.Any] | None = None,
        labels: dict[str, t.Any] | None = None,
    ) -> FlightCreateResult:
        """Create a flight via the flights API.

        Sends the template source for content-addressed resolution and returns
        the flight ID and server-rendered content.
        """
        payload: dict[str, t.Any] = {
            "template": template,
            "template_content": template_content,
            "created_by": created_by,
            "feature_flags": feature_flags,
            "context": context,
            "model_provider": model_provider,
            "model_name": model_name,
        }
        if model_config_data is not None:
            payload["model_config_data"] = model_config_data
        if labels is not None:
            payload["labels"] = labels

        async with httpx.AsyncClient(base_url=self._base_url) as client:
            resp = await client.post("/api/flights", json=payload, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            return FlightCreateResult(
                flight_id=FlightID(data["flight_id"]),
                rendered_content=data["rendered_content"],
            )

    async def update_flight(
        self,
        flight_id: FlightID,
        *,
        status: FlightStatus,
        outcome_metadata: dict[str, t.Any] | None = None,
    ) -> None:
        """Update a flight's status and optional outcome metadata."""
        payload: dict[str, t.Any] = {"status": status.value}
        if outcome_metadata is not None:
            payload["outcome_metadata"] = outcome_metadata

        async with httpx.AsyncClient(base_url=self._base_url) as client:
            resp = await client.patch(
                f"/api/flights/{flight_id}",
                json=payload,
                timeout=10.0,
            )
            resp.raise_for_status()

    async def create_survey_schema(
        self,
        *,
        name: str,
        dimensions: list[SurveyDimension],
        is_default: bool = False,
    ) -> SurveySchemaResult:
        """Create a survey schema via the flights API.

        Returns the created schema with its ID, version, and hash.
        """
        payload: dict[str, t.Any] = {
            "name": name,
            "dimensions": [d.model_dump() for d in dimensions],
            "is_default": is_default,
        }

        async with httpx.AsyncClient(base_url=self._base_url) as client:
            resp = await client.post("/api/survey-schemas", json=payload, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            return SurveySchemaResult(
                schema_id=SurveySchemaID(data["schema_id"]),
                name=data["name"],
                version=data["version"],
                dimensions_hash=data["dimensions_hash"],
                is_default=data["is_default"],
            )


class FlightsClientSync(object):
    """Synchronous client for the flights HTTP API (for CLI scripts)."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    def create_survey_schema(
        self,
        *,
        name: str,
        dimensions: list[SurveyDimension],
        is_default: bool = False,
    ) -> SurveySchemaResult:
        """Create a survey schema via the flights API.

        Returns the created schema with its ID, version, and hash.
        """
        payload: dict[str, t.Any] = {
            "name": name,
            "dimensions": [d.model_dump() for d in dimensions],
            "is_default": is_default,
        }

        with httpx.Client(base_url=self._base_url) as client:
            resp = client.post("/api/survey-schemas", json=payload, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            return SurveySchemaResult(
                schema_id=SurveySchemaID(data["schema_id"]),
                name=data["name"],
                version=data["version"],
                dimensions_hash=data["dimensions_hash"],
                is_default=data["is_default"],
            )
