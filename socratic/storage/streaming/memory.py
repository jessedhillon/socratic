"""In-memory implementation of the assessment stream broker for testing."""

from __future__ import annotations

import asyncio
import typing as t

from socratic.model.id import AttemptID

from .broker import StreamEvent


class InMemoryStreamBroker(object):
    """In-memory assessment stream broker for testing.

    Uses asyncio primitives to simulate Redis Streams behavior:
    - Events stored in lists per attempt
    - asyncio.Condition for signaling new events
    - Incrementing counter for event IDs
    """

    def __init__(self) -> None:
        """Initialize the in-memory broker."""
        self._streams: dict[AttemptID, list[tuple[str, StreamEvent]]] = {}
        self._conditions: dict[AttemptID, asyncio.Condition] = {}
        self._counter = 0
        self._lock = asyncio.Lock()

    async def publish(self, attempt_id: AttemptID, event: StreamEvent) -> str:
        """Publish an event to the stream.

        Returns:
            A string event ID based on an incrementing counter.
        """
        async with self._lock:
            self._counter += 1
            event_id = str(self._counter)

            if attempt_id not in self._streams:
                self._streams[attempt_id] = []
                self._conditions[attempt_id] = asyncio.Condition()

            self._streams[attempt_id].append((event_id, event))

        # Notify subscribers outside the lock
        condition = self._conditions.get(attempt_id)
        if condition:
            async with condition:
                condition.notify_all()

        return event_id

    async def subscribe(
        self,
        attempt_id: AttemptID,
        last_event_id: str | None = None,
    ) -> t.AsyncIterator[tuple[str, StreamEvent]]:
        """Subscribe to events on a stream.

        If last_event_id is provided, starts from events after that ID.
        Otherwise, starts from the beginning.

        The iterator terminates when an "assessment_complete" event is received.
        """
        # Ensure stream and condition exist
        async with self._lock:
            if attempt_id not in self._streams:
                self._streams[attempt_id] = []
                self._conditions[attempt_id] = asyncio.Condition()

        condition = self._conditions[attempt_id]

        # Find starting position
        start_idx = 0
        if last_event_id is not None:
            events = self._streams.get(attempt_id, [])
            for i, (eid, _) in enumerate(events):
                if eid == last_event_id:
                    start_idx = i + 1
                    break

        cursor = start_idx

        while True:
            # Check for new events
            events = self._streams.get(attempt_id, [])

            while cursor < len(events):
                event_id, event = events[cursor]
                cursor += 1
                yield (event_id, event)

                if event.event_type == "assessment_complete":
                    return

            # Wait for more events
            async with condition:
                # Re-check after acquiring lock
                events = self._streams.get(attempt_id, [])
                if cursor >= len(events):
                    try:
                        await asyncio.wait_for(condition.wait(), timeout=30.0)
                    except asyncio.TimeoutError:
                        # Timeout, continue loop to check again
                        pass

    async def close_stream(self, attempt_id: AttemptID) -> None:
        """Remove the stream data."""
        async with self._lock:
            self._streams.pop(attempt_id, None)
            self._conditions.pop(attempt_id, None)
