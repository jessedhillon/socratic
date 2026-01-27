"""Socratic assessment agent for LiveKit voice interface."""

from __future__ import annotations

import logging
import typing as t
import uuid
from collections.abc import AsyncIterable

import jinja2
import pydantic as p
from langchain_core.language_models import BaseChatModel
from livekit.agents import Agent, llm  # pyright: ignore [reportMissingTypeStubs]

from socratic.core import di
from socratic.llm.assessment import get_assessment_status, PostgresCheckpointer, run_assessment_turn, start_assessment
from socratic.llm.assessment.state import InterviewPhase
from socratic.model import AttemptID

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
    rubric_criteria: list[dict[str, t.Any]]
    scope_boundaries: str | None = None
    time_expectation_minutes: int | None = None
    challenge_prompts: list[str] | None = None
    extension_policy: str = "disallowed"


class SocraticAssessmentAgent(Agent):  # pyright: ignore [reportUntypedBaseClass]
    """LiveKit agent that wraps the Socratic assessment dialogue system.

    This agent bridges LiveKit's real-time voice interface with the existing
    LangGraph-based assessment agent. It overrides the llm_node to use our
    custom assessment logic instead of a standard LLM.

    The agent:
    - Receives transcribed speech from the learner via the chat context
    - Passes it to the assessment agent for processing
    - Streams the agent's response back for TTS synthesis
    """

    def __init__(
        self,
        context: AssessmentContext,
    ) -> None:
        """Initialize the assessment agent.

        Args:
            context: Assessment configuration including objective, prompts, and rubric.
        """
        super().__init__(
            instructions="You are a Socratic assessment proctor conducting a voice-based evaluation.",
        )
        self.context = context
        self.checkpointer = PostgresCheckpointer()
        self._initialized = False
        self._current_phase: InterviewPhase | None = None

    @property
    def attempt_id(self) -> AttemptID:
        """Get the attempt ID for this assessment."""
        return AttemptID(self.context.attempt_id)

    @di.inject
    async def _initialize_assessment(
        self,
        model: BaseChatModel = di.Provide["llm.dialogue_model"],  # noqa: B008
        env: jinja2.Environment = di.Provide["template.llm"],  # noqa: B008
    ) -> AsyncIterable[llm.ChatChunk]:  # pyright: ignore [reportUnknownParameterType]
        """Initialize the assessment and stream the orientation message."""
        logger.info(f"Starting assessment for attempt {self.attempt_id}")

        # Mark initialized before yielding so that if the user interrupts the
        # orientation, subsequent llm_node calls process their speech instead of
        # restarting the welcome message.
        self._initialized = True
        self._current_phase = InterviewPhase.Orientation

        chunk_id = str(uuid.uuid4())
        async for token in start_assessment(
            attempt_id=self.attempt_id,
            objective_id=self.context.objective_id,
            objective_title=self.context.objective_title,
            objective_description=self.context.objective_description,
            initial_prompts=self.context.initial_prompts,
            rubric_criteria=self.context.rubric_criteria,
            checkpointer=self.checkpointer,
            model=model,
            env=env,
            scope_boundaries=self.context.scope_boundaries,
            time_expectation_minutes=self.context.time_expectation_minutes,
            challenge_prompts=self.context.challenge_prompts,
            extension_policy=self.context.extension_policy,
        ):
            yield llm.ChatChunk(  # pyright: ignore [reportCallIssue]
                id=chunk_id,
                delta=llm.ChoiceDelta(content=token, role="assistant"),  # pyright: ignore [reportCallIssue]
            )

    @di.inject
    async def _process_learner_message(
        self,
        message: str,
        model: BaseChatModel = di.Provide["llm.dialogue_model"],  # noqa: B008
        env: jinja2.Environment = di.Provide["template.llm"],  # noqa: B008
    ) -> AsyncIterable[llm.ChatChunk]:  # pyright: ignore [reportUnknownParameterType]
        """Process a learner message and stream the response."""
        logger.info(f"Processing learner message: {message[:100]}...")

        chunk_id = str(uuid.uuid4())
        async for token in run_assessment_turn(
            attempt_id=self.attempt_id,
            learner_message=message,
            checkpointer=self.checkpointer,
            model=model,
            env=env,
        ):
            yield llm.ChatChunk(  # pyright: ignore [reportCallIssue]
                id=chunk_id,
                delta=llm.ChoiceDelta(content=token, role="assistant"),  # pyright: ignore [reportCallIssue]
            )

        # Update current phase
        status = get_assessment_status(self.attempt_id, self.checkpointer)
        if status:
            self._current_phase = InterviewPhase(status.get("phase", "orientation"))
            logger.info(f"Assessment phase: {self._current_phase}")

    async def llm_node(  # pyright: ignore [reportIncompatibleMethodOverride]
        self,
        chat_ctx: llm.ChatContext,  # pyright: ignore [reportUnknownParameterType]
        tools: list[t.Any],  # pyright: ignore [reportUnknownParameterType, reportMissingTypeArgument]
        model_settings: t.Any,
    ) -> AsyncIterable[llm.ChatChunk]:  # pyright: ignore [reportUnknownParameterType]
        """Override the LLM node to use our Socratic assessment agent.

        This method is called by the AgentSession when the LLM should generate
        a response. Instead of calling a standard LLM, we route to our custom
        assessment agent which uses LangGraph for dialogue management.

        Args:
            chat_ctx: The current chat context with conversation history.
            tools: Available function tools (not used for assessment).
            model_settings: Model configuration (not used for assessment).

        Yields:
            ChatChunk objects containing the streamed response tokens.
        """
        # If not initialized, run the orientation first
        if not self._initialized:
            async for chunk in self._initialize_assessment():
                yield chunk
            return

        # Get the last user message from the chat context
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
                    content="I didn't catch that. Could you please repeat?", role="assistant"
                ),
            )
            return

        # Process the learner message through our assessment agent
        async for chunk in self._process_learner_message(last_user_message):  # pyright: ignore [reportUnknownArgumentType]
            yield chunk

    @property
    def is_complete(self) -> bool:
        """Check if the assessment has reached the closure phase."""
        return self._current_phase == InterviewPhase.Closure


def create_assessment_agent_from_room_metadata(
    room: "Room",
) -> SocraticAssessmentAgent:
    """Create an assessment agent from LiveKit room metadata.

    The room metadata should contain JSON with the AssessmentContext fields.

    Args:
        room: LiveKit room with metadata containing assessment context.

    Returns:
        Configured SocraticAssessmentAgent.

    Raises:
        ValueError: If room metadata is missing or invalid.
    """
    if not room.metadata:
        raise ValueError("Room metadata is required for assessment context")

    try:
        context = AssessmentContext.model_validate_json(room.metadata)
    except p.ValidationError as e:
        raise ValueError(f"Invalid room metadata: {e}") from e

    return SocraticAssessmentAgent(
        context=context,
    )
