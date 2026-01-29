"""Socratic assessment agent for LiveKit voice interface."""

from __future__ import annotations

import datetime
import json
import logging
import typing as t
from collections.abc import AsyncIterable

import jinja2
import pydantic as p
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables.schema import StreamEvent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from livekit.agents import Agent, llm  # pyright: ignore [reportMissingTypeStubs]

import socratic.lib.uuid as uuid
from socratic import storage
from socratic.core import di
from socratic.core.provider import TimestampProvider
from socratic.llm.agent.assessment import AssessmentAgent
from socratic.llm.agent.assessment.state import AssessmentCriterion, AssessmentState, CriterionCoverage
from socratic.model import AttemptID, UtteranceType
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
    ) -> None:
        super().__init__(
            instructions="You are a Socratic assessment proctor conducting a voice-based evaluation.",
        )
        self.context = context
        self.graph = graph
        self._initialized = False
        self._failed = False
        self._thread_id = str(uuid.uuid4())

    @property
    def attempt_id(self) -> AttemptID:
        return AttemptID(self.context.attempt_id)

    @property
    def _graph_config(self) -> dict[str, t.Any]:
        return {"configurable": {"thread_id": self._thread_id}}

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
    def _build_initial_state(
        self,
        *,
        utcnow: TimestampProvider = di.Provide["utcnow"],  # noqa: B008
    ) -> AssessmentState:
        """Build the initial graph state from the assessment context."""
        criteria_coverage: dict[str, CriterionCoverage] = {}
        for criterion in self.context.rubric_criteria:
            cid = str(criterion.criterion_id)
            criteria_coverage[cid] = CriterionCoverage(
                criterion_id=cid,
                criterion_name=criterion.name,
            )

        return AssessmentState(
            attempt_id=self.context.attempt_id,
            objective_title=self.context.objective_title,
            objective_description=self.context.objective_description,
            rubric_criteria=self.context.rubric_criteria,
            initial_prompts=self.context.initial_prompts,
            time_budget_minutes=self.context.time_expectation_minutes,
            start_time=utcnow(),
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
            revised_content = f"{spoken_text} -- [learner interrupted your speech after this point]"
        else:
            revised_content = "[your response was not delivered — the learner interrupted before hearing any of it]"

        return AIMessage(content=revised_content, id=last_ai_msg.id)

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
            input_state: AssessmentState | dict[str, t.Any] = self._build_initial_state()
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
                yield llm.ChatChunk(  # pyright: ignore [reportCallIssue]
                    id=str(uuid.uuid4()),
                    delta=llm.ChoiceDelta(  # pyright: ignore [reportCallIssue]
                        content="I didn't catch that. Could you please repeat?",
                        role="assistant",
                    ),
                )
                return

            # Record learner speech
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
        except Exception:
            self._failed = True
            logger.exception(f"Fatal assessment error for attempt {self.attempt_id}")
            await self._publish_error("An unexpected error occurred during the assessment.")

    async def _publish_error(self, message: str) -> None:
        """Publish a fatal error to the room data channel for the frontend to handle."""
        try:
            room = self.session.room_io.room  # pyright: ignore [reportUnknownMemberType]
            payload = json.dumps({
                "type": "assessment.error",
                "attempt_id": str(self.attempt_id),
                "message": message,
                "fatal": True,
            })
            await room.local_participant.publish_data(  # pyright: ignore [reportUnknownMemberType]
                payload=payload,
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
    )
