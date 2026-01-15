"""Assessment chat API routes for conducting Socratic dialogues."""

from __future__ import annotations

import datetime
import json
import typing as t

import jinja2
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from socratic.auth import AuthContext, require_educator, require_learner
from socratic.core import di
from socratic.llm.assessment import get_assessment_status, PostgresCheckpointer, run_assessment_turn, start_assessment
from socratic.llm.evaluation import EvaluationPipeline
from socratic.llm.factory import ModelFactory
from socratic.model import AssignmentID, AttemptID, AttemptStatus, UtteranceType
from socratic.storage import assignment as assignment_storage
from socratic.storage import attempt as attempt_storage
from socratic.storage import evaluation as eval_storage
from socratic.storage import objective as obj_storage
from socratic.storage import rubric as rubric_storage
from socratic.storage import transcript as transcript_storage
from socratic.storage.streaming import AssessmentStreamBroker, StreamEvent

from ..view.assessment import AssessmentStatusResponse, CompleteAssessmentOkResponse, CompleteAssessmentRequest, \
    MessageAcceptedResponse, SendMessageRequest, StartAssessmentOkResponse, TranscriptMessageResponse, \
    TranscriptResponse

if t.TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter(prefix="/api/assessments", tags=["assessments"])


@di.inject
async def run_orientation_task(
    attempt_id: AttemptID,
    objective_id: str,
    objective_title: str,
    objective_description: str,
    initial_prompts: list[str],
    rubric_criteria: list[dict[str, t.Any]],
    scope_boundaries: str | None,
    time_expectation_minutes: int | None,
    challenge_prompts: list[str] | None,
    extension_policy: str,
    broker: AssessmentStreamBroker,
    model: BaseChatModel,
    env: jinja2.Environment,
    session: Session = di.Manage["storage.persistent.session"],
) -> None:
    """Background task to generate and stream the orientation message."""
    checkpointer = PostgresCheckpointer()
    full_message = ""

    try:
        async for token in start_assessment(
            attempt_id=attempt_id,
            objective_id=objective_id,
            objective_title=objective_title,
            objective_description=objective_description,
            initial_prompts=initial_prompts,
            rubric_criteria=rubric_criteria,
            checkpointer=checkpointer,
            model=model,
            env=env,
            scope_boundaries=scope_boundaries,
            time_expectation_minutes=time_expectation_minutes,
            challenge_prompts=challenge_prompts,
            extension_policy=extension_policy,
        ):
            full_message += token
            await broker.publish(
                attempt_id,
                StreamEvent(event_type="token", data={"content": token}),
            )

        # Store transcript segment
        transcript_storage.create(
            attempt_id=attempt_id,
            utterance_type=UtteranceType.Interviewer,
            content=full_message,
            start_time=datetime.datetime.now(datetime.UTC),
            session=session,
        )
        session.commit()

        # Send message done event
        await broker.publish(
            attempt_id,
            StreamEvent(event_type="message_done", data={}),
        )

    except Exception as e:
        await broker.publish(
            attempt_id,
            StreamEvent(
                event_type="error",
                data={"message": str(e), "recoverable": False},
            ),
        )


@di.inject
async def run_response_task(
    attempt_id: AttemptID,
    learner_message: str,
    broker: AssessmentStreamBroker,
    model: BaseChatModel,
    env: jinja2.Environment,
    session: Session = di.Manage["storage.persistent.session"],
) -> None:
    """Background task to generate and stream the AI response."""
    checkpointer = PostgresCheckpointer()
    full_response = ""

    try:
        async for token in run_assessment_turn(
            attempt_id=attempt_id,
            learner_message=learner_message,
            checkpointer=checkpointer,
            model=model,
            env=env,
        ):
            full_response += token
            await broker.publish(
                attempt_id,
                StreamEvent(event_type="token", data={"content": token}),
            )

        # Store AI response in transcript
        transcript_storage.create(
            attempt_id=attempt_id,
            utterance_type=UtteranceType.Interviewer,
            content=full_response,
            start_time=datetime.datetime.now(datetime.UTC),
            session=session,
        )
        session.commit()

        # Send message done event
        await broker.publish(
            attempt_id,
            StreamEvent(event_type="message_done", data={}),
        )

    except Exception as e:
        await broker.publish(
            attempt_id,
            StreamEvent(
                event_type="error",
                data={"message": str(e), "recoverable": True},
            ),
        )


@router.post("/{assignment_id}/start", operation_id="start_assessment")
@di.inject
async def start_assessment_route(
    assignment_id: str,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(require_learner),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
    model: BaseChatModel = Depends(di.Provide["llm.dialogue_model"]),
    env: jinja2.Environment = Depends(di.Provide["template.llm"]),
    broker: AssessmentStreamBroker = Depends(di.Provide["storage.streaming.broker"]),
) -> StartAssessmentOkResponse:
    """Start a new assessment attempt.

    Returns immediately with attempt metadata. The orientation message
    will be streamed via the GET /stream endpoint.
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
            "proficiency_levels": [{"grade": pl.grade, "description": pl.description} for pl in c.proficiency_levels],
        }
        for c in rubric_criteria
    ]

    # Create new attempt record
    attempt = attempt_storage.create(
        assignment_id=aid,
        learner_id=auth.user.user_id,
        status=AttemptStatus.InProgress,
        session=session,
    )
    session.commit()

    attempt_id = attempt.attempt_id

    # Schedule background task to generate orientation
    background_tasks.add_task(
        run_orientation_task,
        attempt_id=attempt_id,
        objective_id=str(objective.objective_id),
        objective_title=objective.title,
        objective_description=objective.description,
        initial_prompts=objective.initial_prompts,
        rubric_criteria=serialized_criteria,
        scope_boundaries=objective.scope_boundaries,
        time_expectation_minutes=objective.time_expectation_minutes,
        challenge_prompts=objective.challenge_prompts,
        extension_policy=objective.extension_policy.value,
        broker=broker,
        model=model,
        env=env,
    )

    return StartAssessmentOkResponse(
        attempt_id=attempt_id,
        assignment_id=aid,
        objective_id=objective.objective_id,
        objective_title=objective.title,
    )


@router.get("/{attempt_id}/stream", operation_id="stream_assessment")
@di.inject
async def stream_assessment_route(
    attempt_id: str,
    request: Request,
    auth: AuthContext = Depends(require_learner),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
    broker: AssessmentStreamBroker = Depends(di.Provide["storage.streaming.broker"]),
) -> EventSourceResponse:
    """Stream assessment events via Server-Sent Events.

    Supports reconnection via Last-Event-ID header.

    Event types:
    - token: Partial content token {"content": "..."}
    - message_done: AI message complete
    - assessment_complete: Assessment finished {"evaluation_id": "..."}
    - error: Error occurred {"message": "...", "recoverable": bool}
    """
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

    # Get Last-Event-ID for reconnection support
    last_event_id = request.headers.get("Last-Event-ID")

    async def event_generator() -> AsyncIterator[dict[str, t.Any]]:
        """Generate SSE events from the broker."""
        async for event_id, event in broker.subscribe(aid, last_event_id):
            yield {
                "event": event.event_type,
                "data": json.dumps(event.data),
                "id": event_id,
            }

    return EventSourceResponse(event_generator())


@router.post("/{attempt_id}/message", operation_id="send_assessment_message")
@di.inject
async def send_message_route(
    attempt_id: str,
    request_body: SendMessageRequest,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(require_learner),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
    model: BaseChatModel = Depends(di.Provide["llm.dialogue_model"]),
    env: jinja2.Environment = Depends(di.Provide["template.llm"]),
    broker: AssessmentStreamBroker = Depends(di.Provide["storage.streaming.broker"]),
) -> Response:
    """Send a learner message.

    Returns 202 Accepted immediately. The AI response will be
    streamed via the GET /stream endpoint.
    """
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

    # Store learner message in transcript
    segment = transcript_storage.create(
        attempt_id=aid,
        utterance_type=UtteranceType.Learner,
        content=request_body.content,
        start_time=datetime.datetime.now(datetime.UTC),
        session=session,
    )
    session.commit()

    # Schedule background task to generate response
    background_tasks.add_task(
        run_response_task,
        attempt_id=aid,
        learner_message=request_body.content,
        broker=broker,
        model=model,
        env=env,
    )

    response_body = MessageAcceptedResponse(message_id=segment.segment_id)
    return Response(
        content=response_body.model_dump_json(),
        status_code=status.HTTP_202_ACCEPTED,
        media_type="application/json",
    )


@router.get("/{attempt_id}/status", operation_id="get_assessment_status")
@di.inject
def get_status_route(
    attempt_id: str,
    auth: AuthContext = Depends(require_learner),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
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

    checkpointer = PostgresCheckpointer()
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
async def complete_assessment_route(
    attempt_id: str,
    request_body: CompleteAssessmentRequest,
    auth: AuthContext = Depends(require_learner),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
    broker: AssessmentStreamBroker = Depends(di.Provide["storage.streaming.broker"]),
) -> CompleteAssessmentOkResponse:
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
    attempt_storage.update(
        aid,
        status=AttemptStatus.Completed,
        completed_at=now,
        session=session,
    )
    session.commit()

    # Publish assessment complete event
    await broker.publish(
        aid,
        StreamEvent(event_type="assessment_complete", data={}),
    )

    # Close the stream
    await broker.close_stream(aid)

    return CompleteAssessmentOkResponse(
        attempt_id=aid,
        status=AttemptStatus.Completed.value,
        completed_at=now,
    )


@router.get("/{attempt_id}/transcript", operation_id="get_assessment_transcript")
@di.inject
def get_transcript_route(
    attempt_id: str,
    auth: AuthContext = Depends(require_learner),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
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


@router.post("/{attempt_id}/evaluate", operation_id="trigger_evaluation")
@di.inject
async def trigger_evaluation_route(
    attempt_id: str,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
    env: jinja2.Environment = Depends(di.Provide["template.llm"]),
) -> dict[str, t.Any]:
    """Trigger AI evaluation for a completed assessment.

    This endpoint is called by educators or automated systems after
    an assessment is completed. It runs the evaluation pipeline and
    updates the attempt status to Evaluated.
    """
    aid = AttemptID(attempt_id)

    # Validate attempt exists
    attempt = attempt_storage.get(aid, session=session)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment attempt not found",
        )

    # Get assignment and validate org access
    assignment = assignment_storage.get(attempt.assignment_id, session=session)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )

    if assignment.organization_id != auth.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot evaluate attempts from other organizations",
        )

    # Validate status
    if attempt.status != AttemptStatus.Completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot evaluate attempt with status {attempt.status.value}",
        )

    # Get objective and rubric
    objective = obj_storage.get(assignment.objective_id, session=session)
    if objective is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objective not found",
        )

    rubric_criteria = rubric_storage.find(objective_id=objective.objective_id, session=session)

    # Get transcript
    transcript = transcript_storage.find(attempt_id=aid, session=session)

    # Get model factory from DI
    model_factory: ModelFactory = di.Provide["llm.model_factory"]()

    # Run evaluation pipeline
    pipeline = EvaluationPipeline(model_factory=model_factory, env=env)
    result = await pipeline.evaluate(
        attempt_id=aid,
        transcript=list(transcript),
        rubric_criteria=list(rubric_criteria),
        objective=objective,
    )

    # Store evaluation result
    eval_storage.create(
        attempt_id=aid,
        evidence_mappings=result["evidence_mappings"],
        flags=result["flags"],
        strengths=result["strengths"],
        gaps=result["gaps"],
        reasoning_summary=result["reasoning_summary"],
        session=session,
    )

    # Transition attempt to Evaluated status
    attempt_storage.transition_to_evaluated(
        attempt_id=aid,
        grade=result["grade"],
        confidence_score=result["confidence_score"],
        session=session,
    )

    session.commit()

    return {
        "attempt_id": str(aid),
        "status": "evaluated",
        "grade": result["grade"].value,
        "confidence_score": float(result["confidence_score"]),
        "flags": [f.value for f in result["flags"]],
    }
