"""Redis Streams implementation of the assessment stream broker."""

from __future__ import annotations

import typing as t

import redis.asyncio as redis

from socratic.model.id import AttemptID

from .broker import StreamEvent


class RedisStreamBroker(object):
    """Assessment stream broker using Redis Streams.

    Uses Redis Streams (XADD/XREAD) for pub/sub with:
    - Automatic message ID generation for Last-Event-ID support
    - MAXLEN to cap stream size and prevent unbounded growth
    - BLOCK for efficient long-polling on subscribe
    """

    def __init__(
        self,
        client: redis.Redis,  # type: ignore[type-arg]
        stream_prefix: str = "assessment:stream:",
        max_stream_len: int = 1000,
        block_timeout_ms: int = 30000,
    ) -> None:
        """Initialize the Redis stream broker.

        Args:
            client: Async Redis client.
            stream_prefix: Prefix for stream keys.
            max_stream_len: Maximum number of events to retain per stream.
            block_timeout_ms: Timeout for blocking reads (ms).
        """
        self._client = client
        self._stream_prefix = stream_prefix
        self._max_stream_len = max_stream_len
        self._block_timeout_ms = block_timeout_ms

    def _stream_key(self, attempt_id: AttemptID) -> str:
        """Get the Redis key for an attempt's stream."""
        return f"{self._stream_prefix}{attempt_id}"

    async def publish(self, attempt_id: AttemptID, event: StreamEvent) -> str:
        """Publish an event to the stream.

        Uses XADD with MAXLEN to add the event and cap stream size.

        Returns:
            The Redis stream ID (e.g., "1697312345678-0").
        """
        stream_key = self._stream_key(attempt_id)
        event_id = await self._client.xadd(
            stream_key,
            {"event": event.model_dump_json()},
            maxlen=self._max_stream_len,
        )
        # Redis returns bytes, decode to string
        if isinstance(event_id, bytes):
            return event_id.decode("utf-8")
        return str(event_id)

    async def subscribe(
        self,
        attempt_id: AttemptID,
        last_event_id: str | None = None,
    ) -> t.AsyncIterator[tuple[str, StreamEvent]]:
        """Subscribe to events on a stream.

        Uses XREAD with BLOCK for efficient long-polling. If last_event_id
        is provided, resumes from that position (exclusive). Otherwise,
        starts from the beginning of the stream ("0").

        The iterator terminates when an "assessment_complete" event is received.
        """
        stream_key = self._stream_key(attempt_id)
        cursor = last_event_id or "0"

        while True:
            # XREAD returns: [(stream_name, [(id, {field: value}), ...])]
            results = await self._client.xread(
                {stream_key: cursor},
                block=self._block_timeout_ms,
            )

            if not results:
                # Timeout with no events, continue polling
                continue

            for _stream_name, events in results:
                for event_id_bytes, fields in events:
                    # Decode event ID
                    if isinstance(event_id_bytes, bytes):
                        event_id = event_id_bytes.decode("utf-8")
                    else:
                        event_id = str(event_id_bytes)

                    # Update cursor to this event
                    cursor = event_id

                    # Parse event from JSON
                    event_json = fields.get(b"event") or fields.get("event")
                    if event_json is None:
                        continue

                    if isinstance(event_json, bytes):
                        event_json = event_json.decode("utf-8")

                    event = StreamEvent.model_validate_json(event_json)
                    yield (event_id, event)

                    # Stop iteration on assessment complete
                    if event.event_type == "assessment_complete":
                        return

    async def close_stream(self, attempt_id: AttemptID) -> None:
        """Delete the stream after assessment completes.

        Removes the stream key from Redis to free resources.
        """
        stream_key = self._stream_key(attempt_id)
        await self._client.delete(stream_key)
