"""Assessment stream broker protocol and event types."""

from __future__ import annotations

import typing as t

import pydantic as p

from socratic.model.id import AttemptID

StreamEventType = t.Literal["token", "message_done", "assessment_complete", "error"]


class StreamEvent(p.BaseModel):
    """Event to be pushed through the assessment stream."""

    model_config = p.ConfigDict(frozen=True)

    event_type: StreamEventType
    data: dict[str, t.Any] = p.Field(default_factory=dict)


class AssessmentStreamBroker(t.Protocol):
    """Protocol for assessment stream pub/sub.

    Implementations must support:
    - Publishing events to a stream identified by attempt_id
    - Subscribing to a stream with optional resume from last_event_id
    - Cleaning up stream resources after assessment completes
    """

    async def publish(self, attempt_id: AttemptID, event: StreamEvent) -> str:
        """Publish an event to the stream.

        Args:
            attempt_id: The attempt ID identifying the stream.
            event: The event to publish.

        Returns:
            The event ID (can be used as Last-Event-ID for reconnection).
        """
        ...

    def subscribe(
        self,
        attempt_id: AttemptID,
        last_event_id: str | None = None,
    ) -> t.AsyncIterator[tuple[str, StreamEvent]]:
        """Subscribe to events on a stream.

        Args:
            attempt_id: The attempt ID identifying the stream.
            last_event_id: Optional ID to resume from (for reconnection).

        Yields:
            Tuples of (event_id, event).

        Note: This is an async generator, not an async function returning an iterator.
        """
        ...

    async def close_stream(self, attempt_id: AttemptID) -> None:
        """Clean up stream resources after assessment completes.

        Args:
            attempt_id: The attempt ID identifying the stream to close.
        """
        ...
