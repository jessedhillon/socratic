"""Socratic assessment agent for LiveKit voice interface."""

from __future__ import annotations

import asyncio
import datetime
import logging
import typing as t
from collections.abc import AsyncIterable

import httpx
import jinja2
import pydantic as p
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables.schema import StreamEvent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from livekit.agents import Agent, CloseEvent, CloseReason, llm  # pyright: ignore [reportMissingTypeStubs]

import socratic.lib.json as json
import socratic.lib.uuid as uuid
from socratic import storage
from socratic.core import di
from socratic.core.config.llm import ModelSettings
from socratic.core.config.vendor import FlightsSettings
from socratic.core.provider import TimestampProvider
from socratic.llm.agent.assessment import AssessmentAgent
from socratic.llm.agent.assessment.state import AssessmentCriterion, AssessmentState, Conviviality, CriterionCoverage
from socratic.llm.livekit.event import AssessmentCompleteEvent, AssessmentErrorEvent
from socratic.model import AttemptID, FlightID, FlightStatus, UtteranceType
from socratic.storage import transcript as transcript_storage

if t.TYPE_CHECKING:
    from livekit.rtc import Room  # pyright: ignore [reportMissingTypeStubs]

logger = logging.getLogger(__name__)


class AssessmentContext(p.BaseModel):
    """Context needed to run an assessment via LiveKit."""

    attempt_id: str
    objective_id: str
    objective_title: str
    objective_description: str
    initial_prompts: list[str]
    rubric_criteria: list[AssessmentCriterion]
    scope_boundaries: str | None = None
    time_expectation_minutes: int | None = None
    challenge_prompts: list[str] | None = None
    extension_policy: str = "disallowed"


class SocraticAssessmentAgent(Agent):  # pyright: ignore [reportUntypedBaseClass]
    """LiveKit agent that bridges voice I/O to the AssessmentAgent graph.

    The agent:
    - Receives transcribed speech from the learner via the chat context
    - Invokes the AssessmentAgent LangGraph to generate a response
    - Streams response tokens back for TTS synthesis
    """

    def __init__(
        self,
        context: AssessmentContext,
        *,
        graph: CompiledStateGraph,
        model_settings: ModelSettings | None = None,
        env: jinja2.Environment | None = None,
    ) -> None:
        super().__init__(
            instructions="You are a Socratic assessment proctor conducting a voice-based evaluation.",
        )
        self.context = context
        self.graph = graph
        self.model_settings = model_settings
        self.env = env
        self._initialized = False
        self._failed = False
        self._pending_complete = False
        self._flight_completed = False
        self._thread_id = str(uuid.uuid4())
        self._flight_id: FlightID | None = None

    @property
    def attempt_id(self) -> AttemptID:
        return AttemptID(self.context.attempt_id)

    @property
    def _graph_config(self) -> dict[str, t.Any]:
        return {
            "configurable": {"thread_id": self._thread_id},
            "metadata": {
                "session_id": self._thread_id,
                "attempt_id": self.context.attempt_id,
                "objective_id": self.context.objective_id,
            },
            "tags": ["assessment", "livekit-voice"],
        }

    @di.inject
    async def _record_segment(
        self,
        utterance_type: UtteranceType,
        content: str,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        *,
        utcnow: TimestampProvider = di.Provide["utcnow"],  # noqa: B008
        session: storage.AsyncSession = di.Provide["storage.persistent.async_session"],  # noqa: B008
    ) -> None:
        """Store a transcript segment in the database."""
        if start_time is None:
            start_time = utcnow()
        try:
            async with session.begin():
                await transcript_storage.acreate(
                    attempt_id=self.attempt_id,
                    utterance_type=utterance_type,
                    content=content,
                    start_time=start_time,
                    end_time=end_time,
                    session=session,
                )
        except Exception:
            logger.exception(f"Failed to record {utterance_type.value} transcript segment")

    @di.inject
    async def _build_initial_state(
        self,
        *,
        env: jinja2.Environment = di.Provide["template.llm"],  # noqa: B008
        model_settings: ModelSettings = di.Provide["config.llm.models.dialogue", di.as_(ModelSettings)],  # noqa: B008
        flights_cf: FlightsSettings = di.Provide["config.vendor.flights", di.as_(FlightsSettings)],  # noqa: B008
        utcnow: TimestampProvider = di.Provide["utcnow"],  # noqa: B008
    ) -> AssessmentState:
        """Build the initial graph state from the assessment context.

        Creates a flight via the flights HTTP API to track this assessment
        instance.  The template source is read from the filesystem and sent
        for content-addressed resolution.
        """
        criteria_coverage: dict[str, CriterionCoverage] = {}
        for criterion in self.context.rubric_criteria:
            cid = str(criterion.criterion_id)
            criteria_coverage[cid] = CriterionCoverage(
                criterion_id=cid,
                criterion_name=criterion.name,
            )

        start_time = utcnow()
        flight_id: FlightID | None = None
        conviviality = Conviviality.Conversational

<<<<<<< HEAD
        try:
            # Read the template source for content-addressed resolution
            template_source = env.loader.get_source(env, "agent/assessment_system.j2")[0]  # pyright: ignore[reportOptionalMemberAccess]

            async with httpx.AsyncClient(base_url=flights_cf.base_url) as client:
                resp = await client.post(
                    "/api/flights",
                    json={
                        "template": "assessment_system",
                        "template_content": template_source,
                        "created_by": "system",
                        "feature_flags": {
                            "conviviality": conviviality.value,
                            "extension_policy": self.context.extension_policy,
                        },
                        "context": {
                            "objective_id": self.context.objective_id,
                            "objective_title": self.context.objective_title,
                            "objective_description": self.context.objective_description,
                            "rubric_criteria": [c.model_dump() for c in self.context.rubric_criteria],
                            "initial_prompts": self.context.initial_prompts,
                            "time_budget_minutes": self.context.time_expectation_minutes,
                        },
                        "model_provider": model_settings.provider.value,
                        "model_name": model_settings.model,
                        "model_config_data": {
                            "temperature": model_settings.temperature,
                            "max_tokens": model_settings.max_tokens,
                        },
                        "labels": {"attempt_id": str(self.attempt_id)},
                    },
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()
                flight_id = FlightID(data["flight_id"])
                self._flight_id = flight_id
                logger.info(f"Created flight {flight_id} for attempt {self.attempt_id}")
        except Exception:
            # Flight tracking is optional — don't fail the assessment if it errors
            logger.exception("Failed to create flight for assessment tracking")
||||||| parent of 7893ce1 (feat(livekit): integrate flights tracking with assessment agent)
=======
        # Try to create a flight if we have template tracking enabled
        if self.env is not None and self.model_settings is not None:
            try:
                async with session.begin():
                    # Look up the assessment system template
                    template = await flight_storage.aget_template(
                        name="assessment_system",
                        session=session,
                    )
                    if template is not None:
                        # Render the template (same as AssessmentAgent.system_prompt does)
                        # Use default conviviality — could be enhanced to accept via context
                        conviviality = Conviviality.Conversational
                        jinja_template = self.env.get_template("agent/assessment_system.j2")
                        rendered_content = jinja_template.render(
                            objective_title=self.context.objective_title,
                            objective_description=self.context.objective_description,
                            rubric_criteria=self.context.rubric_criteria,
                            initial_prompts=self.context.initial_prompts,
                            conviviality=conviviality,
                            time_budget_minutes=self.context.time_expectation_minutes,
                        )

                        # Create the flight
                        flight = await flight_storage.acreate_flight(
                            template_id=template.template_id,
                            created_by="system",  # Could be enhanced to track user
                            rendered_content=rendered_content,
                            model_provider=self.model_settings.provider.value,
                            model_name=self.model_settings.model,
                            started_at=start_time,
                            feature_flags={
                                "conviviality": conviviality.value,
                                "extension_policy": self.context.extension_policy,
                            },
                            context={
                                "objective_id": self.context.objective_id,
                                "objective_title": self.context.objective_title,
                                "rubric_criteria_count": len(self.context.rubric_criteria),
                                "initial_prompts_count": len(self.context.initial_prompts),
                                "time_expectation_minutes": self.context.time_expectation_minutes,
                            },
                            model_config={
                                "temperature": self.model_settings.temperature,
                                "max_tokens": self.model_settings.max_tokens,
                            },
                            attempt_id=self.attempt_id,
                            session=session,
                        )
                        flight_id = flight.flight_id
                        self._flight_id = flight_id
                        logger.info(f"Created flight {flight_id} for attempt {self.attempt_id}")
            except Exception:
                # Flight tracking is optional — don't fail the assessment if it errors
                logger.exception("Failed to create flight for assessment tracking")
>>>>>>> 7893ce1 (feat(livekit): integrate flights tracking with assessment agent)

        return AssessmentState(
            attempt_id=self.context.attempt_id,
            flight_id=flight_id,
            objective_title=self.context.objective_title,
            objective_description=self.context.objective_description,
            rubric_criteria=self.context.rubric_criteria,
            initial_prompts=self.context.initial_prompts,
            time_budget_minutes=self.context.time_expectation_minutes,
            start_time=start_time,
            criteria_coverage=criteria_coverage,
            messages=[],
        )

    @di.inject
    async def _stream_graph(
        self,
        input_state: AssessmentState | dict[str, t.Any],
        *,
        utcnow: TimestampProvider = di.Provide["utcnow"],  # noqa: B008
    ) -> AsyncIterable[llm.ChatChunk]:  # pyright: ignore [reportUnknownParameterType]
        """Invoke the graph and stream model tokens as ChatChunks."""
        chunk_id = str(uuid.uuid4())
        full_response = ""
        start_time = utcnow()

        try:
            event: StreamEvent
            async for event in self.graph.astream_events(
                input_state,
                config=self._graph_config,  # pyright: ignore [reportArgumentType]
                version="v2",
            ):
                if event["event"] != "on_chat_model_stream":
                    continue
                token: str = event["data"]["chunk"].content  # pyright: ignore [reportTypedDictNotRequiredAccess]
                if not token:
                    continue
                full_response += token
                yield llm.ChatChunk(  # pyright: ignore [reportCallIssue]
                    id=chunk_id,
                    delta=llm.ChoiceDelta(content=token, role="assistant"),  # pyright: ignore [reportCallIssue]
                )
        finally:
            if full_response:
                await self._record_segment(
                    utterance_type=UtteranceType.Interviewer,
                    content=full_response,
                    start_time=start_time,
                    end_time=utcnow(),
                )

    async def _revise_interrupted_message(self, spoken_text: str) -> AIMessage | None:
        """Build a replacement AIMessage reflecting only what the learner heard.

        Uses the same message ``id`` so the ``add_messages`` reducer replaces
        the original full-length response in graph state.
        """
        state_snapshot = await self.graph.aget_state(self._graph_config)  # pyright: ignore [reportUnknownMemberType, reportArgumentType]
        graph_messages: list[t.Any] = state_snapshot.values.get("messages", [])  # pyright: ignore [reportUnknownMemberType]

        # Find the last AI message in graph state
        last_ai_msg: AIMessage | None = None
        for msg in reversed(graph_messages):  # pyright: ignore [reportUnknownVariableType]
            if isinstance(msg, AIMessage):
                last_ai_msg = msg
                break

        if last_ai_msg is None:
            return None

        if spoken_text:
            revised_content = (
                f"{spoken_text} <interruption>learner interrupted your speech after this point</interruption>"
            )
        else:
            revised_content = (
                "<interruption>your response was not delivered — "
                "the learner interrupted before hearing any of it</interruption>"
            )

        return AIMessage(content=revised_content, id=last_ai_msg.id)

    def _on_agent_state_changed(self, event: t.Any) -> None:
        """Handle agent state transitions to detect farewell TTS completion.

        When ``_pending_complete`` is set (the graph finished with
        ``assessment_complete=True``), we wait for the agent to finish
        speaking the farewell before publishing the completion event to
        the frontend.  This prevents a race where the data-channel event
        arrives before the farewell is audible.
        """
        if (
            self._pending_complete
            and getattr(event, "old_state", None) == "speaking"
            and getattr(event, "new_state", None) == "listening"
        ):
            self._pending_complete = False
            asyncio.create_task(self._publish_complete())

    async def _completion_failsafe(self) -> None:
        """Publish completion after a timeout if the TTS state change was missed.

        This handles edge cases where the ``speaking → listening`` transition
        never fires (e.g. agent disconnects mid-speech, TTS pipeline error).
        """
        timeout_seconds = 15.0
        await asyncio.sleep(timeout_seconds)
        if self._pending_complete:
            logger.warning(
                f"TTS completion not detected within {timeout_seconds}s "
                f"for attempt {self.attempt_id}, publishing completion anyway"
            )
            self._pending_complete = False
            await self._publish_complete()

    async def llm_node(  # pyright: ignore [reportIncompatibleMethodOverride]
        self,
        chat_ctx: llm.ChatContext,  # pyright: ignore [reportUnknownParameterType]
        tools: list[t.Any],  # pyright: ignore [reportUnknownParameterType, reportMissingTypeArgument]
        model_settings: t.Any,
    ) -> AsyncIterable[llm.ChatChunk]:  # pyright: ignore [reportUnknownParameterType]
        """Override the LLM node to use our AssessmentAgent graph.

        First call: initializes the graph with full assessment state.
        Subsequent calls: adds the learner's message and invokes the graph.
        """
        if self._failed:
            return

        if not self._initialized:
            logger.info(f"Starting assessment for attempt {self.attempt_id}")
            self.session.on("agent_state_changed", self._on_agent_state_changed)  # pyright: ignore [reportUnknownMemberType]
<<<<<<< HEAD
            self.session.on("close", self._on_session_close)  # pyright: ignore [reportUnknownMemberType]
||||||| parent of 7893ce1 (feat(livekit): integrate flights tracking with assessment agent)
            input_state: AssessmentState | dict[str, t.Any] = self._build_initial_state()
=======
>>>>>>> 7893ce1 (feat(livekit): integrate flights tracking with assessment agent)
            input_state: AssessmentState | dict[str, t.Any] = await self._build_initial_state()
        else:
            # Check if the agent's previous response was interrupted — this
            # means the learner started speaking before hearing it fully.
            # Scan backwards: the first assistant message before the trailing
            # user message tells us whether TTS was cut off.
            interrupted_spoken_text: str | None = None
            for item in reversed(chat_ctx.items):  # pyright: ignore [reportUnknownMemberType, reportUnknownVariableType]
                if not hasattr(item, "role"):  # pyright: ignore [reportUnknownMemberType]
                    continue
                if item.role == "assistant":  # pyright: ignore [reportUnknownMemberType, reportAttributeAccessIssue]
                    if getattr(item, "interrupted", False):
                        interrupted_spoken_text = item.text_content or ""  # pyright: ignore [reportUnknownMemberType, reportAttributeAccessIssue, reportUnknownVariableType]
                    break
                if item.role == "user":  # pyright: ignore [reportUnknownMemberType, reportAttributeAccessIssue]
                    # Haven't found an assistant message yet — no interruption
                    break

            # Extract the last user message from the chat context
            last_user_message: str | None = None
            for item in reversed(chat_ctx.items):  # pyright: ignore [reportUnknownMemberType, reportUnknownVariableType]
                if hasattr(item, "role") and item.role == "user":  # pyright: ignore [reportUnknownMemberType, reportAttributeAccessIssue]
                    last_user_message = item.text_content  # pyright: ignore [reportUnknownMemberType, reportAttributeAccessIssue, reportUnknownVariableType]
                    break

            if last_user_message is None:
                logger.warning("No user message found in chat context")
                last_user_message = (
                    "<unintelligible>the learner's speech could not be transcribed — "
                    "ask them to repeat</unintelligible>"
                )

            # Record learner speech (skip for unintelligible input)
            if "<unintelligible>" not in last_user_message:
                await self._record_segment(
                    utterance_type=UtteranceType.Learner,
                    content=last_user_message,  # pyright: ignore [reportUnknownArgumentType]
                )

            # Build messages for the graph.  If the agent was interrupted,
            # revise the last AI message in graph state so it reflects only
            # what the learner actually heard, with a marker at the cut-off.
            messages: list[AIMessage | HumanMessage] = []
            if interrupted_spoken_text is not None:
                logger.info("Previous agent response was interrupted by learner")
                revised = await self._revise_interrupted_message(interrupted_spoken_text)  # pyright: ignore [reportUnknownArgumentType]
                if revised is not None:
                    messages.append(revised)
            messages.append(HumanMessage(content=last_user_message))  # pyright: ignore [reportUnknownArgumentType]

            # Pass messages to the graph — it merges via add_messages reducer.
            # A revised AIMessage with the same id replaces the original.
            input_state = {"messages": messages}

        try:
            async for chunk in self._stream_graph(input_state):
                yield chunk
            self._initialized = True

            # Check if the assessment ended during this turn (e.g. the agent
            # called end_assessment).  If so, defer the completion signal
            # until after the farewell finishes playing via TTS.  The
            # _on_agent_state_changed handler publishes the data-channel
            # event when the agent transitions from speaking → listening.
            state_snapshot = await self.graph.aget_state(self._graph_config)  # pyright: ignore [reportUnknownMemberType, reportArgumentType]
            if state_snapshot.values.get("assessment_complete", False):  # pyright: ignore [reportUnknownMemberType]
                logger.info(f"Assessment ending for attempt {self.attempt_id}, waiting for farewell TTS")
                self._pending_complete = True
                asyncio.create_task(self._completion_failsafe())
        except asyncio.CancelledError:
            # Normal interruption flow — the framework cancelled this
            # generation because the learner kept speaking.  Not fatal.
            logger.debug(f"Graph invocation cancelled for attempt {self.attempt_id}")
        except Exception:
            self._failed = True
            logger.exception(f"Fatal assessment error for attempt {self.attempt_id}")
            await self._publish_error("An unexpected error occurred during the assessment.")

    @di.inject
<<<<<<< HEAD
    async def _complete_flight(
        self,
        *,
        completion_reason: str,
        status: FlightStatus = FlightStatus.Completed,
        flights_cf: FlightsSettings = di.Provide["config.vendor.flights", di.as_(FlightsSettings)],  # noqa: B008
    ) -> None:
        """Mark the tracked flight as completed or abandoned via the flights HTTP API.

        Includes ``completion_reason`` in the outcome metadata so we can
        distinguish agent-initiated completion from user disconnect, etc.
        Guarded by ``_flight_completed`` to prevent double-completion.
        """
        if self._flight_completed or self._flight_id is None:
            return

        self._flight_completed = True

        try:
            outcome_metadata: dict[str, t.Any] = {
                "completion_reason": completion_reason,
            }

            # Try to capture criteria coverage from graph state
            try:
                state_snapshot = await self.graph.aget_state(self._graph_config)  # pyright: ignore [reportUnknownMemberType, reportArgumentType]
                criteria_coverage = state_snapshot.values.get("criteria_coverage", {})  # pyright: ignore [reportUnknownMemberType]
                outcome_metadata["criteria_coverage"] = {
                    cid: {
                        "coverage": cov.get("coverage", "unknown") if isinstance(cov, dict) else "unknown",
                        "evidence_count": len(cov.get("evidence", [])) if isinstance(cov, dict) else 0,  # pyright: ignore [reportUnknownArgumentType]
                    }
                    for cid, cov in criteria_coverage.items()  # pyright: ignore [reportUnknownVariableType]
                }
            except Exception:
                logger.warning(f"Could not retrieve graph state for flight {self._flight_id} outcome metadata")

            async with httpx.AsyncClient(base_url=flights_cf.base_url) as client:
                resp = await client.patch(
                    f"/api/flights/{self._flight_id}",
                    json={
                        "status": status.value,
                        "outcome_metadata": outcome_metadata,
                    },
                    timeout=10.0,
                )
                resp.raise_for_status()
            logger.info(f"Marked flight {self._flight_id} as {status.value} (reason: {completion_reason})")
        except Exception:
            logger.exception(f"Failed to update flight {self._flight_id} (reason: {completion_reason})")

    def _on_session_close(self, event: CloseEvent) -> None:
        """Handle session close to ensure the flight is marked complete or abandoned.

        Maps the LiveKit ``CloseReason`` to a flight completion reason:

        - ``PARTICIPANT_DISCONNECTED``: user left — abandon the flight
        - ``ERROR``: something went wrong — abandon the flight
        - ``JOB_SHUTDOWN``: server-side shutdown — abandon the flight
        - ``USER_INITIATED`` / ``TASK_COMPLETED``: triggered by our own
          ``session.shutdown()`` call in ``_publish_complete`` — the flight
          is already completed, so the ``_flight_completed`` guard prevents
          double-writes.
        """
        reason = event.reason
        abandoned = FlightStatus.Abandoned
        if reason == CloseReason.PARTICIPANT_DISCONNECTED:
            asyncio.create_task(self._complete_flight(completion_reason="participant_disconnected", status=abandoned))
        elif reason == CloseReason.ERROR:
            asyncio.create_task(self._complete_flight(completion_reason="error", status=abandoned))
        elif reason == CloseReason.JOB_SHUTDOWN:
            asyncio.create_task(self._complete_flight(completion_reason="job_shutdown", status=abandoned))

    async def _publish_complete(self) -> None:
||||||| parent of 7893ce1 (feat(livekit): integrate flights tracking with assessment agent)
    async def _publish_complete(self) -> None:
=======
    async def _publish_complete(
        self,
        *,
        session: storage.AsyncSession = di.Provide["storage.persistent.async_session"],  # noqa: B008
    ) -> None:
>>>>>>> 7893ce1 (feat(livekit): integrate flights tracking with assessment agent)
        """Publish assessment completion to the room data channel and shut down."""
        logger.info(f"Assessment complete for attempt {self.attempt_id}")

<<<<<<< HEAD
        await self._complete_flight(completion_reason="agent")
||||||| parent of 7893ce1 (feat(livekit): integrate flights tracking with assessment agent)
=======
        # Mark the flight as completed if one was created
        if self._flight_id is not None:
            try:
                async with session.begin():
                    # Get final state to extract outcome metadata
                    state_snapshot = await self.graph.aget_state(self._graph_config)  # pyright: ignore [reportUnknownMemberType, reportArgumentType]
                    criteria_coverage = state_snapshot.values.get("criteria_coverage", {})  # pyright: ignore [reportUnknownMemberType]

                    outcome_metadata: dict[str, t.Any] = {
                        "criteria_coverage": {
                            cid: {
                                "coverage": cov.get("coverage", "unknown") if isinstance(cov, dict) else "unknown",
                                "evidence_count": len(cov.get("evidence", [])) if isinstance(cov, dict) else 0,  # pyright: ignore [reportUnknownArgumentType]
                            }
                            for cid, cov in criteria_coverage.items()  # pyright: ignore [reportUnknownVariableType]
                        },
                    }

                    await flight_storage.acomplete_flight(
                        self._flight_id,
                        outcome_metadata=outcome_metadata,
                        session=session,
                    )
                    logger.info(f"Marked flight {self._flight_id} as completed")
            except Exception:
                logger.exception(f"Failed to complete flight {self._flight_id}")
>>>>>>> 7893ce1 (feat(livekit): integrate flights tracking with assessment agent)

        event = AssessmentCompleteEvent(attempt_id=self.attempt_id)
        try:
            room = self.session.room_io.room  # pyright: ignore [reportUnknownMemberType]
            await room.local_participant.publish_data(  # pyright: ignore [reportUnknownMemberType]
                payload=json.dumps(event),
                topic="assessment.complete",
                reliable=True,
            )
        except Exception:
            logger.exception("Failed to publish assessment completion to room data channel")

        # Gracefully end the session — drain=True waits for pending TTS to
        # finish before disconnecting, so any farewell text the agent just
        # yielded will be spoken in full.
        self.session.shutdown()  # pyright: ignore [reportUnknownMemberType]

    async def _publish_error(self, message: str) -> None:
        """Publish a fatal error to the room data channel for the frontend to handle."""
        event = AssessmentErrorEvent(attempt_id=self.attempt_id, message=message, fatal=True)
        try:
            room = self.session.room_io.room  # pyright: ignore [reportUnknownMemberType]
            await room.local_participant.publish_data(  # pyright: ignore [reportUnknownMemberType]
                payload=json.dumps(event),
                topic="assessment.error",
                reliable=True,
            )
        except Exception:
            logger.exception("Failed to publish error to room data channel")


@di.inject
def create_assessment_agent_from_room_metadata(
    room: "Room",
    *,
    model: BaseChatModel = di.Provide["llm.dialogue_model"],  # noqa: B008
    model_settings: ModelSettings = di.Provide["config.llm.models.dialogue", di.as_(ModelSettings)],  # noqa: B008
    env: jinja2.Environment = di.Provide["template.llm"],  # noqa: B008
) -> SocraticAssessmentAgent:
    """Create an assessment agent from LiveKit room metadata.

    Parses the room metadata JSON into an AssessmentContext, constructs the
    AssessmentAgent graph with a MemorySaver checkpointer, and wraps it in
    the LiveKit agent adapter.
    """
    if not room.metadata:
        raise ValueError("Room metadata is required for assessment context")

    try:
        context = AssessmentContext.model_validate_json(room.metadata)
    except p.ValidationError as e:
        raise ValueError(f"Invalid room metadata: {e}") from e

    # Build the assessment graph with in-memory checkpointing
    agent = AssessmentAgent(model, env=env)
    graph = agent.compile(checkpointer=MemorySaver())

    return SocraticAssessmentAgent(
        context=context,
        graph=graph,
        model_settings=model_settings,
        env=env,
    )
