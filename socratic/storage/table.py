import datetime
import decimal
import enum
import typing as t

from sqlalchemy import ForeignKey, func, MetaData
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, MappedAsDataclass
from sqlalchemy.types import Numeric, String

from socratic.model import AssignmentID, AttemptID, EvaluationResultID, ExampleID, ObjectiveID, OrganizationID, \
    OverrideID, RubricCriterionID, StrandID, TranscriptSegmentID, UserID

from .type import ShortUUIDKeyType, ValueEnumMapper

metadata = MetaData()


class base(MappedAsDataclass, DeclarativeBase):
    type_annotation_map = {
        ExampleID: ShortUUIDKeyType(ExampleID),
        OrganizationID: ShortUUIDKeyType(OrganizationID),
        UserID: ShortUUIDKeyType(UserID),
        ObjectiveID: ShortUUIDKeyType(ObjectiveID),
        StrandID: ShortUUIDKeyType(StrandID),
        RubricCriterionID: ShortUUIDKeyType(RubricCriterionID),
        AssignmentID: ShortUUIDKeyType(AssignmentID),
        AttemptID: ShortUUIDKeyType(AttemptID),
        TranscriptSegmentID: ShortUUIDKeyType(TranscriptSegmentID),
        EvaluationResultID: ShortUUIDKeyType(EvaluationResultID),
        OverrideID: ShortUUIDKeyType(OverrideID),
        list[str]: ARRAY(String),
        enum.Enum: ValueEnumMapper,
    }


class example(base):
    __tablename__ = "example"

    example_id: Mapped[ExampleID] = mapped_column(primary_key=True)


# Organization & User


class organizations(base):
    __tablename__ = "organizations"

    organization_id: Mapped[OrganizationID] = mapped_column(primary_key=True)
    name: Mapped[str]
    slug: Mapped[str] = mapped_column(unique=True)
    create_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now())
    update_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now(), onupdate=func.now())


class users(base):
    __tablename__ = "users"

    user_id: Mapped[UserID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    password_hash: Mapped[str]
    create_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now())
    update_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now(), onupdate=func.now())


class organization_memberships(base):
    __tablename__ = "organization_memberships"

    user_id: Mapped[UserID] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    organization_id: Mapped[OrganizationID] = mapped_column(
        ForeignKey("organizations.organization_id"), primary_key=True
    )
    role: Mapped[str]
    create_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now())
    update_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now(), onupdate=func.now())


# Objectives & Strands


class objectives(base):
    __tablename__ = "objectives"

    objective_id: Mapped[ObjectiveID] = mapped_column(primary_key=True)
    organization_id: Mapped[OrganizationID] = mapped_column(ForeignKey("organizations.organization_id"))
    created_by: Mapped[UserID] = mapped_column(ForeignKey("users.user_id"))

    title: Mapped[str]
    description: Mapped[str]
    scope_boundaries: Mapped[str | None] = mapped_column(default=None)
    time_expectation_minutes: Mapped[int | None] = mapped_column(default=None)

    initial_prompts: Mapped[list[str]] = mapped_column(default_factory=list)
    challenge_prompts: Mapped[list[str]] = mapped_column(default_factory=list)

    extension_policy: Mapped[str] = mapped_column(default="disallowed")
    status: Mapped[str] = mapped_column(default="draft")

    create_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now())
    update_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now(), onupdate=func.now())


class strands(base):
    __tablename__ = "strands"

    strand_id: Mapped[StrandID] = mapped_column(primary_key=True)
    organization_id: Mapped[OrganizationID] = mapped_column(ForeignKey("organizations.organization_id"))
    created_by: Mapped[UserID] = mapped_column(ForeignKey("users.user_id"))

    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(default=None)

    create_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now())
    update_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now(), onupdate=func.now())


class objectives_in_strands(base):
    __tablename__ = "objectives_in_strands"

    strand_id: Mapped[StrandID] = mapped_column(ForeignKey("strands.strand_id"), primary_key=True)
    objective_id: Mapped[ObjectiveID] = mapped_column(ForeignKey("objectives.objective_id"), primary_key=True)
    position: Mapped[int]


class objective_dependencies(base):
    __tablename__ = "objective_dependencies"

    objective_id: Mapped[ObjectiveID] = mapped_column(ForeignKey("objectives.objective_id"), primary_key=True)
    depends_on_objective_id: Mapped[ObjectiveID] = mapped_column(
        ForeignKey("objectives.objective_id"), primary_key=True
    )
    dependency_type: Mapped[str] = mapped_column(default="hard")


# Rubrics


class rubric_criteria(base):
    __tablename__ = "rubric_criteria"

    criterion_id: Mapped[RubricCriterionID] = mapped_column(primary_key=True)
    objective_id: Mapped[ObjectiveID] = mapped_column(ForeignKey("objectives.objective_id"))

    name: Mapped[str]
    description: Mapped[str]
    evidence_indicators: Mapped[list[str]] = mapped_column(default_factory=list)
    failure_modes: Mapped[list[dict[str, t.Any]]] = mapped_column(JSONB, default_factory=list)
    grade_thresholds: Mapped[list[dict[str, t.Any]]] = mapped_column(JSONB, default_factory=list)
    weight: Mapped[decimal.Decimal] = mapped_column(Numeric(4, 2), default=decimal.Decimal("1.0"))


# Assignments


class assignments(base):
    __tablename__ = "assignments"

    assignment_id: Mapped[AssignmentID] = mapped_column(primary_key=True)
    organization_id: Mapped[OrganizationID] = mapped_column(ForeignKey("organizations.organization_id"))
    objective_id: Mapped[ObjectiveID] = mapped_column(ForeignKey("objectives.objective_id"))
    assigned_by: Mapped[UserID] = mapped_column(ForeignKey("users.user_id"))
    assigned_to: Mapped[UserID] = mapped_column(ForeignKey("users.user_id"))

    available_from: Mapped[datetime.datetime | None] = mapped_column(default=None)
    available_until: Mapped[datetime.datetime | None] = mapped_column(default=None)
    max_attempts: Mapped[int] = mapped_column(default=1)
    retake_policy: Mapped[str] = mapped_column(default="none")
    retake_delay_hours: Mapped[int | None] = mapped_column(default=None)

    create_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now())
    update_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now(), onupdate=func.now())


# Assessment Attempts


class assessment_attempts(base):
    __tablename__ = "assessment_attempts"

    attempt_id: Mapped[AttemptID] = mapped_column(primary_key=True)
    assignment_id: Mapped[AssignmentID] = mapped_column(ForeignKey("assignments.assignment_id"))
    learner_id: Mapped[UserID] = mapped_column(ForeignKey("users.user_id"))

    status: Mapped[str] = mapped_column(default="not_started")
    started_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(default=None)

    grade: Mapped[str | None] = mapped_column(default=None)
    confidence_score: Mapped[decimal.Decimal | None] = mapped_column(Numeric(5, 4), default=None)

    audio_url: Mapped[str | None] = mapped_column(default=None)

    create_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now())


# Transcripts


class transcript_segments(base):
    __tablename__ = "transcript_segments"

    segment_id: Mapped[TranscriptSegmentID] = mapped_column(primary_key=True)
    attempt_id: Mapped[AttemptID] = mapped_column(ForeignKey("assessment_attempts.attempt_id"))

    utterance_type: Mapped[str]
    content: Mapped[str]
    start_time: Mapped[datetime.datetime]
    end_time: Mapped[datetime.datetime | None] = mapped_column(default=None)

    confidence: Mapped[decimal.Decimal | None] = mapped_column(Numeric(5, 4), default=None)
    prompt_index: Mapped[int | None] = mapped_column(default=None)


# Evaluation Results


class evaluation_results(base):
    __tablename__ = "evaluation_results"

    evaluation_id: Mapped[EvaluationResultID] = mapped_column(primary_key=True)
    attempt_id: Mapped[AttemptID] = mapped_column(ForeignKey("assessment_attempts.attempt_id"))

    evidence_mappings: Mapped[list[dict[str, t.Any]]] = mapped_column(JSONB, default_factory=list)
    flags: Mapped[list[str]] = mapped_column(default_factory=list)
    strengths: Mapped[list[str]] = mapped_column(default_factory=list)
    gaps: Mapped[list[str]] = mapped_column(default_factory=list)

    reasoning_summary: Mapped[str | None] = mapped_column(default=None)

    create_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now())


# Educator Overrides


class educator_overrides(base):
    __tablename__ = "educator_overrides"

    override_id: Mapped[OverrideID] = mapped_column(primary_key=True)
    attempt_id: Mapped[AttemptID] = mapped_column(ForeignKey("assessment_attempts.attempt_id"))
    educator_id: Mapped[UserID] = mapped_column(ForeignKey("users.user_id"))

    new_grade: Mapped[str]
    reason: Mapped[str]
    original_grade: Mapped[str | None] = mapped_column(default=None)
    feedback: Mapped[str | None] = mapped_column(default=None)

    create_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now())


# Agent States (LangGraph checkpoints)


class agent_states(base):
    """Stores LangGraph agent state for assessment interviews.

    This table persists the conversation state between HTTP requests,
    allowing the assessment to continue across multiple interactions.
    """

    __tablename__ = "agent_states"

    attempt_id: Mapped[AttemptID] = mapped_column(ForeignKey("assessment_attempts.attempt_id"), primary_key=True)

    checkpoint_data: Mapped[dict[str, t.Any]] = mapped_column(JSONB)
    thread_id: Mapped[str]

    update_time: Mapped[datetime.datetime] = mapped_column(default=None, server_default=func.now(), onupdate=func.now())
