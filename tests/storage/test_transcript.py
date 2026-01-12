"""Tests for socratic.storage.transcript module."""

from __future__ import annotations

import datetime
import decimal
import typing as t

import pytest
from sqlalchemy.orm import Session

from socratic.model import AssessmentAttempt, Assignment, Objective, Organization, TranscriptSegment, \
    TranscriptSegmentID, User, UserRole, UtteranceType
from socratic.storage import transcript as transcript_storage


class TestGet(object):
    """Tests for transcript_storage.get()."""

    def test_get_by_segment_id(
        self,
        db_session: Session,
        segment_factory: t.Callable[..., TranscriptSegment],
    ) -> None:
        """get() with segment_id returns the segment."""
        segment = segment_factory()

        with db_session.begin():
            result = transcript_storage.get(segment.segment_id, session=db_session)

        assert result is not None
        assert result.segment_id == segment.segment_id

    def test_get_positional_pk(
        self,
        db_session: Session,
        segment_factory: t.Callable[..., TranscriptSegment],
    ) -> None:
        """get() accepts segment_id as positional argument."""
        segment = segment_factory(content="Positional Test")

        with db_session.begin():
            result = transcript_storage.get(segment.segment_id, session=db_session)

        assert result is not None
        assert result.content == "Positional Test"

    def test_get_nonexistent_returns_none(self, db_session: Session) -> None:
        """get() returns None for nonexistent segment ID."""
        with db_session.begin():
            result = transcript_storage.get(TranscriptSegmentID(), session=db_session)

        assert result is None


class TestFind(object):
    """Tests for transcript_storage.find()."""

    def test_find_all(
        self,
        db_session: Session,
        segment_factory: t.Callable[..., TranscriptSegment],
    ) -> None:
        """find() returns all segments when no filters provided."""
        seg1 = segment_factory(content="Segment 1")
        seg2 = segment_factory(content="Segment 2")

        with db_session.begin():
            result = transcript_storage.find(session=db_session)

        ids = {s.segment_id for s in result}
        assert seg1.segment_id in ids
        assert seg2.segment_id in ids

    def test_find_by_attempt_id(
        self,
        db_session: Session,
        segment_factory: t.Callable[..., TranscriptSegment],
        test_attempt: AssessmentAttempt,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """find() filters by attempt_id."""
        other_attempt = attempt_factory()
        seg1 = segment_factory(content="Attempt 1 Segment")
        seg2 = segment_factory(content="Attempt 2 Segment", attempt_id=other_attempt.attempt_id)

        with db_session.begin():
            result = transcript_storage.find(
                attempt_id=test_attempt.attempt_id,
                session=db_session,
            )

        ids = {s.segment_id for s in result}
        assert seg1.segment_id in ids
        assert seg2.segment_id not in ids

    def test_find_by_utterance_type(
        self,
        db_session: Session,
        segment_factory: t.Callable[..., TranscriptSegment],
    ) -> None:
        """find() filters by utterance_type."""
        seg1 = segment_factory(utterance_type=UtteranceType.Learner)
        seg2 = segment_factory(utterance_type=UtteranceType.Interviewer)

        with db_session.begin():
            result = transcript_storage.find(
                utterance_type=UtteranceType.Learner,
                session=db_session,
            )

        ids = {s.segment_id for s in result}
        assert seg1.segment_id in ids
        assert seg2.segment_id not in ids


class TestCreate(object):
    """Tests for transcript_storage.create()."""

    def test_create_segment(
        self,
        db_session: Session,
        test_attempt: AssessmentAttempt,
    ) -> None:
        """create() creates a segment with required fields."""
        now = datetime.datetime.now(datetime.UTC)

        with db_session.begin():
            segment = transcript_storage.create(
                attempt_id=test_attempt.attempt_id,
                utterance_type=UtteranceType.Learner,
                content="Test content",
                start_time=now,
                session=db_session,
            )

        assert segment.attempt_id == test_attempt.attempt_id
        assert segment.utterance_type == UtteranceType.Learner
        assert segment.content == "Test content"
        assert segment.segment_id is not None

    def test_create_segment_with_optional_fields(
        self,
        db_session: Session,
        test_attempt: AssessmentAttempt,
    ) -> None:
        """create() accepts optional fields."""
        now = datetime.datetime.now(datetime.UTC)
        end_time = now + datetime.timedelta(seconds=30)

        with db_session.begin():
            segment = transcript_storage.create(
                attempt_id=test_attempt.attempt_id,
                utterance_type=UtteranceType.Interviewer,
                content="Full segment",
                start_time=now,
                end_time=end_time,
                confidence=decimal.Decimal("0.95"),
                prompt_index=1,
                session=db_session,
            )

        assert segment.end_time is not None
        assert segment.confidence == decimal.Decimal("0.95")
        assert segment.prompt_index == 1

    def test_create_defaults(
        self,
        db_session: Session,
        test_attempt: AssessmentAttempt,
    ) -> None:
        """create() uses sensible defaults for optional fields."""
        now = datetime.datetime.now(datetime.UTC)

        with db_session.begin():
            segment = transcript_storage.create(
                attempt_id=test_attempt.attempt_id,
                utterance_type=UtteranceType.Learner,
                content="Minimal segment",
                start_time=now,
                session=db_session,
            )

        assert segment.end_time is None
        assert segment.confidence is None
        assert segment.prompt_index is None


@pytest.fixture
def test_educator(
    user_factory: t.Callable[..., User],
    test_org: Organization,
) -> User:
    """Provide a test educator user."""
    return user_factory(
        email="educator@test.com",
        name="Test Educator",
        password="password123",
        organization_id=test_org.organization_id,
        role=UserRole.Educator,
    )


@pytest.fixture
def test_learner(
    user_factory: t.Callable[..., User],
    test_org: Organization,
) -> User:
    """Provide a test learner user."""
    return user_factory(
        email="learner@test.com",
        name="Test Learner",
        password="password123",
        organization_id=test_org.organization_id,
        role=UserRole.Learner,
    )


@pytest.fixture
def test_objective(
    db_session: Session,
    test_org: Organization,
    test_educator: User,
) -> Objective:
    """Provide a test objective."""
    from socratic.storage import objective as obj_storage

    with db_session.begin():
        obj = obj_storage.create(
            organization_id=test_org.organization_id,
            created_by=test_educator.user_id,
            title="Test Objective",
            description="A test objective",
            session=db_session,
        )
        return obj


@pytest.fixture
def test_assignment(
    db_session: Session,
    test_org: Organization,
    test_educator: User,
    test_learner: User,
    test_objective: Objective,
) -> Assignment:
    """Provide a test assignment."""
    from socratic.storage import assignment as assignment_storage

    with db_session.begin():
        assignment = assignment_storage.create(
            organization_id=test_org.organization_id,
            objective_id=test_objective.objective_id,
            assigned_by=test_educator.user_id,
            assigned_to=test_learner.user_id,
            session=db_session,
        )
        return assignment


@pytest.fixture
def test_attempt(
    db_session: Session,
    test_assignment: Assignment,
    test_learner: User,
) -> AssessmentAttempt:
    """Provide a test attempt."""
    from socratic.storage import attempt as attempt_storage

    with db_session.begin():
        attempt = attempt_storage.create(
            assignment_id=test_assignment.assignment_id,
            learner_id=test_learner.user_id,
            session=db_session,
        )
        return attempt


@pytest.fixture
def attempt_factory(
    db_session: Session,
    test_assignment: Assignment,
    test_learner: User,
) -> t.Callable[..., AssessmentAttempt]:
    """Factory fixture for creating test attempts."""
    from socratic.storage import attempt as attempt_storage

    def create_attempt() -> AssessmentAttempt:
        with db_session.begin():
            attempt = attempt_storage.create(
                assignment_id=test_assignment.assignment_id,
                learner_id=test_learner.user_id,
                session=db_session,
            )
            return attempt

    return create_attempt


@pytest.fixture
def segment_factory(
    db_session: Session,
    test_attempt: AssessmentAttempt,
) -> t.Callable[..., TranscriptSegment]:
    """Factory fixture for creating test transcript segments."""

    def create_segment(
        content: str = "Test content",
        utterance_type: UtteranceType = UtteranceType.Learner,
        attempt_id: t.Any = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        confidence: decimal.Decimal | None = None,
        prompt_index: int | None = None,
    ) -> TranscriptSegment:
        with db_session.begin():
            segment = transcript_storage.create(
                attempt_id=attempt_id or test_attempt.attempt_id,
                utterance_type=utterance_type,
                content=content,
                start_time=start_time or datetime.datetime.now(datetime.UTC),
                end_time=end_time,
                confidence=confidence,
                prompt_index=prompt_index,
                session=db_session,
            )
            return segment

    return create_segment
