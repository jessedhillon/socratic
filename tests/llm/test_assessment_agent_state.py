"""Tests for assessment agent state schema and status rendering."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jinja2
from langchain_core.messages import AIMessage, HumanMessage

from socratic.llm.agent.assessment.state import AssessmentState, CoverageLevel, CriterionCoverage
from socratic.llm.agent.assessment.status import render_status
from socratic.model.id import ObjectiveID, RubricCriterionID
from socratic.model.rubric import ProficiencyLevel, RubricCriterion


def _make_criterion(name: str = "Criterion A") -> RubricCriterion:
    return RubricCriterion(
        criterion_id=RubricCriterionID(),
        objective_id=ObjectiveID(),
        name=name,
        description=f"Description of {name}",
        proficiency_levels=[
            ProficiencyLevel(grade="Proficient", description="Meets expectations"),
            ProficiencyLevel(grade="Developing", description="Partially meets expectations"),
        ],
    )


class TestAssessmentStateInstantiation(object):
    """State schema instantiates correctly with assessment data."""

    def test_minimal_instantiation(self) -> None:
        state = AssessmentState(
            attempt_id="attempt_1",
            objective_title="Test Objective",
            objective_description="Test description",
        )
        assert state.attempt_id == "attempt_1"
        assert state.rubric_criteria == []
        assert state.initial_prompts == []
        assert state.criteria_coverage == {}
        assert state.assessment_complete is False
        assert state.messages == []

    def test_full_instantiation(self) -> None:
        criteria = [_make_criterion("Criterion A"), _make_criterion("Criterion B")]
        start = datetime.now(timezone.utc)

        state = AssessmentState(
            attempt_id="attempt_2",
            objective_title="Full Objective",
            objective_description="Full description",
            rubric_criteria=criteria,
            initial_prompts=["Explain X", "Describe Y"],
            time_budget_minutes=15,
            start_time=start,
        )
        assert len(state.rubric_criteria) == 2
        assert state.rubric_criteria[0].name == "Criterion A"
        assert state.rubric_criteria[0].proficiency_levels[0].grade == "Proficient"
        assert state.initial_prompts == ["Explain X", "Describe Y"]
        assert state.time_budget_minutes == 15
        assert state.start_time == start

    def test_completed_reflects_assessment_complete(self) -> None:
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
            assessment_complete=True,
        )
        assert state.completed is True

    def test_turn_count_counts_human_messages(self) -> None:
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
            messages=[
                HumanMessage(content="hello"),
                AIMessage(content="hi"),
                HumanMessage(content="question"),
            ],
        )
        assert state.turn_count == 2

    def test_elapsed_minutes_none_without_start_time(self) -> None:
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
        )
        assert state.elapsed_minutes is None

    def test_elapsed_minutes_calculated_from_start_time(self) -> None:
        start = datetime.now(timezone.utc) - timedelta(minutes=5)
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
            start_time=start,
        )
        assert state.elapsed_minutes is not None
        assert 4.9 <= state.elapsed_minutes <= 5.2


class TestStatusRendering(object):
    """Status template renders with coverage, prompts, and progress."""

    def test_renders_no_coverage_message(self, llm_env: jinja2.Environment) -> None:
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
        )
        output = render_status(state, llm_env)
        assert "No coverage recorded yet." in output

    def test_renders_coverage_entries(self, llm_env: jinja2.Environment) -> None:
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
            criteria_coverage={
                "c1": CriterionCoverage(
                    criterion_id="c1",
                    criterion_name="Variables",
                    coverage=CoverageLevel.Partial,
                    evidence=["defined a variable"],
                ),
            },
        )
        output = render_status(state, llm_env)
        assert "**Variables**: partial" in output
        assert "defined a variable" in output

    def test_renders_available_prompts(self, llm_env: jinja2.Environment) -> None:
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
            initial_prompts=["Explain recursion", "What is a loop?"],
        )
        output = render_status(state, llm_env)
        assert "Explain recursion" in output
        assert "What is a loop?" in output

    def test_renders_all_prompts_used(self, llm_env: jinja2.Environment) -> None:
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
            initial_prompts=[],
        )
        output = render_status(state, llm_env)
        assert "All prompts have been used." in output

    def test_renders_turn_count(self, llm_env: jinja2.Environment) -> None:
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
            messages=[HumanMessage(content="hello"), AIMessage(content="hi")],
        )
        output = render_status(state, llm_env)
        assert "Turn: 1" in output

    def test_renders_elapsed_time_with_budget(self, llm_env: jinja2.Environment) -> None:
        start = datetime.now(timezone.utc) - timedelta(minutes=3)
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
            start_time=start,
            time_budget_minutes=15,
        )
        output = render_status(state, llm_env)
        assert "Elapsed:" in output
        assert "/ 15 min" in output

    def test_omits_elapsed_without_start_time(self, llm_env: jinja2.Environment) -> None:
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
        )
        output = render_status(state, llm_env)
        assert "Elapsed:" not in output


class TestCoverageSorting(object):
    """Coverage sorting puts not-started criteria first."""

    def test_not_started_before_partial(self, llm_env: jinja2.Environment) -> None:
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
            criteria_coverage={
                "c1": CriterionCoverage(
                    criterion_id="c1",
                    criterion_name="Already Partial",
                    coverage=CoverageLevel.Partial,
                ),
                "c2": CriterionCoverage(
                    criterion_id="c2",
                    criterion_name="Not Started",
                    coverage=CoverageLevel.NotStarted,
                ),
            },
        )
        output = render_status(state, llm_env)
        assert output.index("Not Started") < output.index("Already Partial")

    def test_partial_before_full(self, llm_env: jinja2.Environment) -> None:
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
            criteria_coverage={
                "c1": CriterionCoverage(
                    criterion_id="c1",
                    criterion_name="Full Coverage",
                    coverage=CoverageLevel.Full,
                ),
                "c2": CriterionCoverage(
                    criterion_id="c2",
                    criterion_name="Partial Coverage",
                    coverage=CoverageLevel.Partial,
                ),
            },
        )
        output = render_status(state, llm_env)
        assert output.index("Partial Coverage") < output.index("Full Coverage")

    def test_alphabetical_within_same_level(self, llm_env: jinja2.Environment) -> None:
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
            criteria_coverage={
                "c1": CriterionCoverage(
                    criterion_id="c1",
                    criterion_name="Zebra",
                    coverage=CoverageLevel.NotStarted,
                ),
                "c2": CriterionCoverage(
                    criterion_id="c2",
                    criterion_name="Alpha",
                    coverage=CoverageLevel.NotStarted,
                ),
            },
        )
        output = render_status(state, llm_env)
        assert output.index("Alpha") < output.index("Zebra")

    def test_full_ordering(self, llm_env: jinja2.Environment) -> None:
        state = AssessmentState(
            attempt_id="a",
            objective_title="t",
            objective_description="d",
            criteria_coverage={
                "c1": CriterionCoverage(
                    criterion_id="c1",
                    criterion_name="Full B",
                    coverage=CoverageLevel.Full,
                ),
                "c2": CriterionCoverage(
                    criterion_id="c2",
                    criterion_name="Not Started A",
                    coverage=CoverageLevel.NotStarted,
                ),
                "c3": CriterionCoverage(
                    criterion_id="c3",
                    criterion_name="Partial C",
                    coverage=CoverageLevel.Partial,
                ),
                "c4": CriterionCoverage(
                    criterion_id="c4",
                    criterion_name="Full A",
                    coverage=CoverageLevel.Full,
                ),
            },
        )
        output = render_status(state, llm_env)
        positions = [output.index(n) for n in ["Not Started A", "Partial C", "Full A", "Full B"]]
        assert positions == sorted(positions)
