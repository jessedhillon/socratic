"""Tests for socratic.storage.agent_state module."""

from __future__ import annotations

import typing as t

import pytest
from sqlalchemy.orm import Session

from socratic.model import AssessmentAttempt, Assignment, AttemptID, AttemptStatus, Objective, Organization, User, \
    UserRole
from socratic.storage import agent_state as agent_state_storage
from socratic.storage.agent_state import AgentStateRecord


class TestGet(object):
    """Tests for agent_state_storage.get()."""

    def test_get_by_attempt_id(
        self,
        db_session: Session,
        agent_state_factory: t.Callable[..., AgentStateRecord],
        test_attempt: AssessmentAttempt,
    ) -> None:
        """get() with attempt_id returns the agent state."""
        agent_state_factory()

        with db_session.begin():
            result = agent_state_storage.get(test_attempt.attempt_id, session=db_session)

        assert result is not None
        assert result.attempt_id == test_attempt.attempt_id

    def test_get_positional_pk(
        self,
        db_session: Session,
        agent_state_factory: t.Callable[..., AgentStateRecord],
        test_attempt: AssessmentAttempt,
    ) -> None:
        """get() accepts attempt_id as positional argument."""
        agent_state_factory(thread_id="positional-test-thread")

        with db_session.begin():
            result = agent_state_storage.get(test_attempt.attempt_id, session=db_session)

        assert result is not None
        assert result.thread_id == "positional-test-thread"

    def test_get_nonexistent_returns_none(self, db_session: Session) -> None:
        """get() returns None for nonexistent attempt ID."""
        with db_session.begin():
            result = agent_state_storage.get(AttemptID(), session=db_session)

        assert result is None


class TestUpsert(object):
    """Tests for agent_state_storage.upsert()."""

    def test_upsert_creates_new(
        self,
        db_session: Session,
        test_attempt: AssessmentAttempt,
    ) -> None:
        """upsert() creates a new agent state when none exists."""
        checkpoint_data = {"phase": "exploration", "prompts_completed": 0}

        with db_session.begin():
            result = agent_state_storage.upsert(
                test_attempt.attempt_id,
                checkpoint_data=checkpoint_data,
                thread_id="new-thread-id",
                session=db_session,
            )

        assert result.attempt_id == test_attempt.attempt_id
        assert result.checkpoint_data == checkpoint_data
        assert result.thread_id == "new-thread-id"

    def test_upsert_updates_existing(
        self,
        db_session: Session,
        agent_state_factory: t.Callable[..., AgentStateRecord],
        test_attempt: AssessmentAttempt,
    ) -> None:
        """upsert() updates existing agent state."""
        agent_state_factory(
            checkpoint_data={"phase": "exploration", "prompts_completed": 0},
            thread_id="original-thread",
        )

        updated_data = {"phase": "challenge", "prompts_completed": 3}

        with db_session.begin():
            result = agent_state_storage.upsert(
                test_attempt.attempt_id,
                checkpoint_data=updated_data,
                thread_id="updated-thread",
                session=db_session,
            )

        assert result.attempt_id == test_attempt.attempt_id
        assert result.checkpoint_data == updated_data
        assert result.thread_id == "updated-thread"

    def test_upsert_preserves_attempt_id(
        self,
        db_session: Session,
        agent_state_factory: t.Callable[..., AgentStateRecord],
        test_attempt: AssessmentAttempt,
    ) -> None:
        """upsert() preserves the attempt_id across updates."""
        agent_state_factory()

        # First update
        with db_session.begin():
            result1 = agent_state_storage.upsert(
                test_attempt.attempt_id,
                checkpoint_data={"update": 1},
                thread_id="thread-1",
                session=db_session,
            )

        # Second update
        with db_session.begin():
            result2 = agent_state_storage.upsert(
                test_attempt.attempt_id,
                checkpoint_data={"update": 2},
                thread_id="thread-2",
                session=db_session,
            )

        assert result1.attempt_id == result2.attempt_id == test_attempt.attempt_id


class TestDelete(object):
    """Tests for agent_state_storage.delete()."""

    def test_delete_existing(
        self,
        db_session: Session,
        agent_state_factory: t.Callable[..., AgentStateRecord],
        test_attempt: AssessmentAttempt,
    ) -> None:
        """delete() removes an existing agent state and returns True."""
        agent_state_factory()

        with db_session.begin():
            result = agent_state_storage.delete(test_attempt.attempt_id, session=db_session)

        assert result is True

        # Verify it's gone
        with db_session.begin():
            state = agent_state_storage.get(test_attempt.attempt_id, session=db_session)

        assert state is None

    def test_delete_nonexistent(
        self,
        db_session: Session,
    ) -> None:
        """delete() returns False for nonexistent agent state."""
        with db_session.begin():
            result = agent_state_storage.delete(AttemptID(), session=db_session)

        assert result is False


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
            status=AttemptStatus.InProgress,
            session=db_session,
        )
        return attempt


@pytest.fixture
def agent_state_factory(
    db_session: Session,
    test_attempt: AssessmentAttempt,
) -> t.Callable[..., AgentStateRecord]:
    """Factory fixture for creating test agent states."""

    def create_agent_state(
        checkpoint_data: dict[str, t.Any] | None = None,
        thread_id: str = "test-thread-id",
    ) -> AgentStateRecord:
        if checkpoint_data is None:
            checkpoint_data = {"phase": "orientation", "prompts_completed": 0}

        with db_session.begin():
            state = agent_state_storage.upsert(
                test_attempt.attempt_id,
                checkpoint_data=checkpoint_data,
                thread_id=thread_id,
                session=db_session,
            )
            return state

    return create_agent_state
