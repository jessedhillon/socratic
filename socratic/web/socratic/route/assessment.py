"""Assessment chat API routes for conducting Socratic dialogues."""

from __future__ import annotations

import datetime
import json
import typing as t

import jinja2
from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from socratic.auth import AuthContext, require_learner
from socratic.core import di
from socratic.llm.assessment import get_assessment_status, PostgresCheckpointer, run_assessment_turn, start_assessment
from socratic.model import AssignmentID, AttemptID, AttemptStatus, UtteranceType
from socratic.storage import assignment as assignment_storage
from socratic.storage import attempt as attempt_storage
from socratic.storage import objective as obj_storage
from socratic.storage import rubric as rubric_storage
from socratic.storage import transcript as transcript_storage
from socratic.storage.attempt import AttemptCreateParams, AttemptUpdateParams
from socratic.storage.transcript import TranscriptSegmentCreateParams

from ..view.assessment import AssessmentStatusResponse, CompleteAssessmentRequest, CompleteAssessmentResponse, \
    SendMessageRequest, TranscriptMessageResponse, TranscriptResponse

if t.TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

router = APIRouter(prefix="/api/assessments", tags=["assessments"])


def _get_checkpointer(session_factory: Callable[[], Session]) -> PostgresCheckpointer:
    """Create a checkpointer with the session factory."""
    return PostgresCheckpointer(session_factory)


@router.post("/{assignment_id}/start", operation_id="start_assessment")
@di.inject
async def start_assessment_route(
    assignment_id: str,
    auth: AuthContext = Depends(require_learner),
    session: Session = di.Provide["storage.persistent.session"],
    model: BaseChatModel = di.Provide["llm.dialogue_model"],
    env: jinja2.Environment = di.Provide["template.llm"],
    session_factory: Callable[[], Session] = di.Provide["storage.persistent.session_factory"],
) -> EventSourceResponse:
    """Start a new assessment attempt.

    Streams the orientation message via SSE, then returns completion with attempt ID.
    """
    aid = AssignmentID(assignment_id)

    # Validate assignment exists and belongs to the learner
    assignment = assignment_storage.get(aid, session=session)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )

    if assignment.assigned_to != auth.user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This assignment is not yours",
        )

    # Check availability window
    now = datetime.datetime.now(datetime.UTC)
    if assignment.available_from and now < assignment.available_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignment is not yet available",
        )
    if assignment.available_until and now > assignment.available_until:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignment is no longer available",
        )

    # Check attempt limits
    existing_attempts = attempt_storage.find(assignment_id=aid, session=session)
    if len(existing_attempts) >= assignment.max_attempts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum attempts reached",
        )

    # Get objective and rubric data
    objective = obj_storage.get(assignment.objective_id, session=session)
    if objective is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objective not found",
        )

    rubric_criteria = rubric_storage.find(objective_id=objective.objective_id, session=session)
    serialized_criteria = [
        {
            "criterion_id": str(c.criterion_id),
            "name": c.name,
            "description": c.description,
            "evidence_indicators": c.evidence_indicators,
            "failure_modes": c.failure_modes,
        }
        for c in rubric_criteria
    ]

    # Create new attempt record
    create_params: AttemptCreateParams = {
        "assignment_id": aid,
        "learner_id": auth.user.user_id,
        "status": AttemptStatus.InProgress,
    }
    attempt = attempt_storage.create(create_params, session=session)
    session.commit()

    attempt_id = attempt.attempt_id
    checkpointer = _get_checkpointer(session_factory)

    async def event_generator() -> AsyncIterator[dict[str, t.Any]]:
        """Generate SSE events for the orientation message."""
        full_message = ""
        async for token in start_assessment(
            attempt_id=attempt_id,
            objective_id=str(objective.objective_id),
            objective_title=objective.title,
            objective_description=objective.description,
            initial_prompts=objective.initial_prompts,
            rubric_criteria=serialized_criteria,
            checkpointer=checkpointer,
            model=model,
            env=env,
            scope_boundaries=objective.scope_boundaries,
            time_expectation_minutes=objective.time_expectation_minutes,
            challenge_prompts=objective.challenge_prompts,
            extension_policy=objective.extension_policy.value,
        ):
            full_message += token
            yield {"event": "token", "data": json.dumps({"content": token})}

        # Store transcript segment
        with session_factory() as tx_session:
            transcript_params: TranscriptSegmentCreateParams = {
                "attempt_id": attempt_id,
                "utterance_type": UtteranceType.Interviewer,
                "content": full_message,
                "start_time": datetime.datetime.now(datetime.UTC),
            }
            transcript_storage.create(transcript_params, session=tx_session)
            tx_session.commit()

        # Send completion event with metadata
        yield {
            "event": "done",
            "data": json.dumps({
                "attempt_id": str(attempt_id),
                "assignment_id": str(aid),
                "objective_id": str(objective.objective_id),
                "objective_title": objective.title,
            }),
        }

    return EventSourceResponse(event_generator())


@router.post("/{attempt_id}/message", operation_id="send_assessment_message")
@di.inject
async def send_message_route(
    attempt_id: str,
    request: SendMessageRequest,
    auth: AuthContext = Depends(require_learner),
    session: Session = di.Provide["storage.persistent.session"],
    model: BaseChatModel = di.Provide["llm.dialogue_model"],
    env: jinja2.Environment = di.Provide["template.llm"],
    session_factory: Callable[[], Session] = di.Provide["storage.persistent.session_factory"],
) -> EventSourceResponse:
    """Send a learner message and receive AI response via SSE stream."""
    aid = AttemptID(attempt_id)

    # Validate attempt exists and belongs to the learner
    attempt = attempt_storage.get(aid, session=session)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment attempt not found",
        )

    if attempt.learner_id != auth.user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This assessment is not yours",
        )

    if attempt.status != AttemptStatus.InProgress:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment is not in progress",
        )

    checkpointer = _get_checkpointer(session_factory)

    # Store learner message in transcript
    with session_factory() as tx_session:
        learner_params: TranscriptSegmentCreateParams = {
            "attempt_id": aid,
            "utterance_type": UtteranceType.Learner,
            "content": request.content,
            "start_time": datetime.datetime.now(datetime.UTC),
        }
        transcript_storage.create(learner_params, session=tx_session)
        tx_session.commit()

    async def event_generator() -> AsyncIterator[dict[str, t.Any]]:
        """Generate SSE events for the AI response."""
        full_response = ""
        async for token in run_assessment_turn(
            attempt_id=aid,
            learner_message=request.content,
            checkpointer=checkpointer,
            model=model,
            env=env,
        ):
            full_response += token
            yield {"event": "token", "data": json.dumps({"content": token})}

        # Store AI response in transcript
        with session_factory() as tx_session:
            ai_params: TranscriptSegmentCreateParams = {
                "attempt_id": aid,
                "utterance_type": UtteranceType.Interviewer,
                "content": full_response,
                "start_time": datetime.datetime.now(datetime.UTC),
            }
            transcript_storage.create(ai_params, session=tx_session)
            tx_session.commit()

        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())


@router.get("/{attempt_id}/status", operation_id="get_assessment_status")
@di.inject
def get_status_route(
    attempt_id: str,
    auth: AuthContext = Depends(require_learner),
    session: Session = di.Provide["storage.persistent.session"],
    session_factory: Callable[[], Session] = di.Provide["storage.persistent.session_factory"],
) -> AssessmentStatusResponse:
    """Get the current status of an assessment attempt."""
    aid = AttemptID(attempt_id)

    # Validate attempt exists and belongs to the learner
    attempt = attempt_storage.get(aid, session=session)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment attempt not found",
        )

    if attempt.learner_id != auth.user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This assessment is not yours",
        )

    checkpointer = _get_checkpointer(session_factory)
    status_data = get_assessment_status(aid, checkpointer)

    if "error" in status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=status_data["error"],
        )

    return AssessmentStatusResponse(
        attempt_id=aid,
        phase=status_data["phase"],
        message_count=status_data["message_count"],
        prompts_completed=status_data["prompts_completed"],
        total_prompts=status_data["total_prompts"],
        consent_confirmed=status_data["consent_confirmed"],
    )


@router.post("/{attempt_id}/complete", operation_id="complete_assessment")
@di.inject
def complete_assessment_route(
    attempt_id: str,
    request: CompleteAssessmentRequest,
    auth: AuthContext = Depends(require_learner),
    session: Session = di.Provide["storage.persistent.session"],
) -> CompleteAssessmentResponse:
    """Complete an assessment attempt."""
    aid = AttemptID(attempt_id)

    # Validate attempt exists and belongs to the learner
    attempt = attempt_storage.get(aid, session=session)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment attempt not found",
        )

    if attempt.learner_id != auth.user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This assessment is not yours",
        )

    if attempt.status != AttemptStatus.InProgress:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment is not in progress",
        )

    # Update attempt status to completed
    now = datetime.datetime.now(datetime.UTC)
    update_params: AttemptUpdateParams = {
        "status": AttemptStatus.Completed,
        "completed_at": now,
    }
    attempt_storage.update(aid, update_params, session=session)
    session.commit()

    return CompleteAssessmentResponse(
        attempt_id=aid,
        status=AttemptStatus.Completed.value,
        completed_at=now,
    )


@router.get("/{attempt_id}/transcript", operation_id="get_assessment_transcript")
@di.inject
def get_transcript_route(
    attempt_id: str,
    auth: AuthContext = Depends(require_learner),
    session: Session = di.Provide["storage.persistent.session"],
) -> TranscriptResponse:
    """Get the full transcript of an assessment attempt."""
    aid = AttemptID(attempt_id)

    # Validate attempt exists and belongs to the learner
    attempt = attempt_storage.get(aid, session=session)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment attempt not found",
        )

    if attempt.learner_id != auth.user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This assessment is not yours",
        )

    # Get objective title
    assignment = assignment_storage.get(attempt.assignment_id, session=session)
    objective_title = "Assessment"
    if assignment:
        objective = obj_storage.get(assignment.objective_id, session=session)
        if objective:
            objective_title = objective.title

    # Get transcript segments
    segments = transcript_storage.find(attempt_id=aid, session=session)
    messages = [
        TranscriptMessageResponse(
            segment_id=seg.segment_id,
            utterance_type=seg.utterance_type,
            content=seg.content,
            start_time=seg.start_time,
        )
        for seg in sorted(segments, key=lambda s: s.start_time)
    ]

    return TranscriptResponse(
        attempt_id=aid,
        objective_title=objective_title,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        messages=messages,
    )
