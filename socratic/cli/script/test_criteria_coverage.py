"""Manual test for criteria coverage, pacing, and completion detection in assessments.

Tests that criteria coverage is properly tracked and updated during
assessment conversations, pacing information is communicated in prompts,
and completion detection works correctly with structured output. The
script can run in two modes:
- Manual: Displays state and prompts tester to verify correctness
- Automated: Programmatically verifies state changes

Usage:
    socratic-cli script test-criteria-coverage                    # manual mode
    socratic-cli script test-criteria-coverage --automated        # automated mode
    socratic-cli script test-criteria-coverage -a <assignment_id> # specific assignment
    socratic-cli script test-criteria-coverage --test-pacing      # simulate time passage
    socratic-cli script test-criteria-coverage --test-completion  # test AI completion detection

Prerequisites:
    - LANGSMITH_API_KEY and LANGSMITH_TRACING=true in environment
    - Dev services running (postgres, redis, socratic-dev)
    - At least one assignment with rubric criteria in database
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import typing as t
from datetime import datetime

import jinja2
import pydantic as p
from langchain_core.language_models import BaseChatModel
from langsmith import Client as LangSmithClient
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from sqlalchemy.orm import Session

import socratic.lib.cli as click
from socratic.core import di
from socratic.llm.assessment import calculate_pacing_status, PostgresCheckpointer, run_assessment_turn, start_assessment
from socratic.model import Assignment, AssignmentID, AttemptID, AttemptStatus, ExtensionPolicy, Objective, \
    ObjectiveStatus, RubricCriterion, UserRole
from socratic.storage import assignment as assignment_storage
from socratic.storage import attempt as attempt_storage
from socratic.storage import objective as obj_storage
from socratic.storage import organization as org_storage
from socratic.storage import rubric as rubric_storage
from socratic.storage import user as user_storage
from socratic.storage.rubric import ProficiencyLevelCreateParams
from socratic.storage.user import MembershipCreateParams

# Rich console for formatted output
console = Console()

# Fixture slug for test data - used to find or create test fixture
TEST_FIXTURE_SLUG = "test-criteria-coverage-fixture"


def create_test_fixture(
    session: Session,
) -> tuple[Assignment, Objective, tuple[RubricCriterion, ...]]:
    """Create or find test fixture data for criteria coverage testing.

    Creates a complete test fixture with:
    - Organization: "Test Organization"
    - Users: instructor and learner
    - Objective: "Understanding Ratios and Proportions" with 3 initial prompts
    - Rubric criteria: 3 criteria with proficiency levels
    - Assignment: linking learner to objective

    Returns the assignment, objective, and rubric criteria.
    """
    # Check if fixture already exists
    existing_org = org_storage.get(slug=TEST_FIXTURE_SLUG, session=session)
    if existing_org:
        # Find existing assignment for this org
        assignments = assignment_storage.find(organization_id=existing_org.organization_id, session=session)
        if assignments:
            assignment = assignments[0]
            objective = obj_storage.get(assignment.objective_id, session=session)
            assert objective is not None
            criteria = rubric_storage.find(objective_id=objective.objective_id, session=session)
            click.echo(click.style(f"Using existing test fixture (org: {TEST_FIXTURE_SLUG})", fg="cyan"))
            return assignment, objective, criteria

    click.echo(click.style("Creating new test fixture...", fg="cyan"))

    # Create organization
    org = org_storage.create(
        name="Test Organization for Criteria Coverage",
        slug=TEST_FIXTURE_SLUG,
        session=session,
    )

    # Create instructor user
    instructor = user_storage.create(
        email=f"instructor+{TEST_FIXTURE_SLUG}@example.com",
        name="Test Instructor",
        password=p.Secret[str]("test-password-123"),
        session=session,
    )
    user_storage.update(
        instructor.user_id,
        add_memberships={MembershipCreateParams(organization_id=org.organization_id, role=UserRole.Educator)},
        session=session,
    )

    # Create learner user
    learner = user_storage.create(
        email=f"learner+{TEST_FIXTURE_SLUG}@example.com",
        name="Test Learner",
        password=p.Secret[str]("test-password-123"),
        session=session,
    )
    user_storage.update(
        learner.user_id,
        add_memberships={MembershipCreateParams(organization_id=org.organization_id, role=UserRole.Learner)},
        session=session,
    )

    # Create objective with math ratios content
    objective = obj_storage.create(
        organization_id=org.organization_id,
        created_by=instructor.user_id,
        title="Understanding Ratios and Proportions",
        description=(
            "Assess the student's understanding of ratios and proportional relationships, "
            "including their ability to identify equivalent ratios, solve proportion problems, "
            "and apply proportional reasoning to real-world situations."
        ),
        scope_boundaries=(
            "Focus on 6th-7th grade level ratio and proportion concepts. "
            "Do not assess advanced algebra, statistics, or topics beyond basic proportional reasoning."
        ),
        time_expectation_minutes=15,
        initial_prompts=[
            "Can you explain what a ratio is and give me an example from everyday life?",
            (
                "If a recipe calls for 2 cups of flour for every 3 cups of sugar, "
                "how much flour would you need for 9 cups of sugar? Walk me through your thinking."
            ),
            (
                "A map has a scale of 1 inch = 50 miles. If two cities are 3.5 inches apart on the map, "
                "how far apart are they in real life? Explain your reasoning."
            ),
        ],
        challenge_prompts=[
            (
                "Can you think of a situation where proportional reasoning wouldn't apply, "
                "even though it might seem like it should?"
            ),
            ("How would you explain the difference between a ratio and a fraction to someone who is confused?"),
        ],
        extension_policy=ExtensionPolicy.Conditional,
        status=ObjectiveStatus.Published,
        session=session,
    )

    # Create rubric criteria with proficiency levels
    criteria_list: list[RubricCriterion] = []

    # Criterion 1: Conceptual Understanding
    c1 = rubric_storage.create(
        objective_id=objective.objective_id,
        name="Conceptual Understanding of Ratios",
        description=(
            "Demonstrates understanding of what ratios represent "
            "and how they describe relationships between quantities."
        ),
        proficiency_levels=[
            ProficiencyLevelCreateParams(
                grade="Exemplary",
                description=(
                    "Clearly explains ratios as comparisons between quantities, "
                    "provides multiple relevant examples, and connects to broader mathematical concepts."
                ),
            ),
            ProficiencyLevelCreateParams(
                grade="Proficient",
                description="Accurately explains what a ratio is and provides at least one appropriate example.",
            ),
            ProficiencyLevelCreateParams(
                grade="Developing",
                description=(
                    "Shows partial understanding of ratios but may have "
                    "minor misconceptions or incomplete explanations."
                ),
            ),
            ProficiencyLevelCreateParams(
                grade="Beginning",
                description=(
                    "Shows significant misconceptions about what ratios represent "
                    "or cannot provide a clear explanation."
                ),
            ),
        ],
        session=session,
    )
    criteria_list.append(c1)

    # Criterion 2: Problem Solving
    c2 = rubric_storage.create(
        objective_id=objective.objective_id,
        name="Proportional Problem Solving",
        description=(
            "Ability to set up and solve proportion problems correctly, showing clear mathematical reasoning."
        ),
        proficiency_levels=[
            ProficiencyLevelCreateParams(
                grade="Exemplary",
                description=(
                    "Solves proportion problems efficiently using multiple methods, "
                    "clearly explains reasoning, and checks work."
                ),
            ),
            ProficiencyLevelCreateParams(
                grade="Proficient",
                description=(
                    "Correctly solves proportion problems and shows logical reasoning in the solution process."
                ),
            ),
            ProficiencyLevelCreateParams(
                grade="Developing",
                description=(
                    "Attempts proportion problems but may make computational errors or have gaps in reasoning."
                ),
            ),
            ProficiencyLevelCreateParams(
                grade="Beginning",
                description="Struggles to set up or solve proportion problems correctly.",
            ),
        ],
        session=session,
    )
    criteria_list.append(c2)

    # Criterion 3: Real-World Application
    c3 = rubric_storage.create(
        objective_id=objective.objective_id,
        name="Real-World Application",
        description=("Ability to apply proportional reasoning to real-world contexts like maps, recipes, and scaling."),
        proficiency_levels=[
            ProficiencyLevelCreateParams(
                grade="Exemplary",
                description=(
                    "Expertly applies proportional reasoning to real-world problems, "
                    "explains context clearly, and recognizes limitations."
                ),
            ),
            ProficiencyLevelCreateParams(
                grade="Proficient",
                description=(
                    "Successfully applies proportional reasoning to real-world scenarios with clear explanations."
                ),
            ),
            ProficiencyLevelCreateParams(
                grade="Developing",
                description=(
                    "Can apply proportional reasoning but may struggle "
                    "with interpreting context or explaining connections."
                ),
            ),
            ProficiencyLevelCreateParams(
                grade="Beginning",
                description="Difficulty connecting proportional reasoning to real-world applications.",
            ),
        ],
        session=session,
    )
    criteria_list.append(c3)

    # Create assignment
    assignment = assignment_storage.create(
        organization_id=org.organization_id,
        objective_id=objective.objective_id,
        assigned_by=instructor.user_id,
        assigned_to=learner.user_id,
        max_attempts=10,
        session=session,
    )

    click.echo(click.style(f"  Created organization: {org.name} ({org.slug})", fg="green"))
    click.echo(click.style(f"  Created objective: {objective.title}", fg="green"))
    click.echo(click.style(f"  Created {len(criteria_list)} rubric criteria", fg="green"))
    click.echo(click.style(f"  Created assignment: {assignment.assignment_id}", fg="green"))

    return assignment, objective, tuple(criteria_list)


class TestResult(object):
    """Tracks test results."""

    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []  # (name, reason)

    def record(self, name: str, passed: bool, reason: str = "") -> None:
        if passed:
            self.passed.append(name)
            click.echo(click.style(f"  ✓ {name}", fg="green"))
        else:
            self.failed.append((name, reason))
            click.echo(click.style(f"  ✗ {name}", fg="red"))
            if reason:
                click.echo(click.style(f"    Reason: {reason}", fg="yellow"))

    def summary(self) -> bool:
        click.echo("\n" + "=" * 60)
        click.echo("TEST RESULTS")
        click.echo("=" * 60)
        click.echo(f"Passed: {len(self.passed)}")
        click.echo(f"Failed: {len(self.failed)}")

        if self.failed:
            click.echo(click.style("\nFailed tests:", fg="red"))
            for name, reason in self.failed:
                click.echo(f"  - {name}")
                if reason:
                    click.echo(f"    {reason}")
            return False
        else:
            click.echo(click.style("\nAll tests passed!", fg="green"))
            return True


class LangSmithVerifier(object):
    """Verifies traces in LangSmith programmatically."""

    def __init__(self, project_name: str = "default") -> None:
        self.client = LangSmithClient()
        self.project_name = project_name

    def wait_for_traces(self, trace_id: str, timeout: float = 30.0, min_runs: int = 1) -> list[t.Any]:
        """Wait for traces to appear in LangSmith."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                runs = list(self.client.list_runs(trace_id=trace_id, limit=100))
                if len(runs) >= min_runs:
                    return runs
            except Exception:
                pass
            time.sleep(1.0)
        return []

    def find_runs_by_name(self, runs: list[t.Any], name: str) -> list[t.Any]:
        """Find runs with a specific name."""
        return [r for r in runs if r.name == name]

    def get_run_state(self, run: t.Any) -> dict[str, t.Any] | None:
        """Extract state from a run's inputs/outputs."""
        # State might be in inputs, outputs, or extra
        if run.outputs and isinstance(run.outputs, dict):
            outputs = t.cast(dict[str, t.Any], run.outputs)
            # Check for state in outputs
            if "criteria_coverage" in outputs:
                return outputs
            # LangGraph often puts state in a nested structure
            for key in ["state", "output", "__end__"]:
                if key in outputs and isinstance(outputs[key], dict):
                    nested = t.cast(dict[str, t.Any], outputs[key])
                    if "criteria_coverage" in nested:
                        return nested
        if run.inputs and isinstance(run.inputs, dict):
            inputs = t.cast(dict[str, t.Any], run.inputs)
            if "criteria_coverage" in inputs:
                return inputs
        return None

    def verify_initial_coverage(self, runs: list[t.Any], criteria_ids: list[str]) -> tuple[bool, str]:
        """Verify all criteria start at 'not_started'."""
        # Look for the initial state in orientation or create_initial_state
        for run in runs:
            state = self.get_run_state(run)
            if state and "criteria_coverage" in state:
                coverage = state["criteria_coverage"]
                if not coverage:
                    continue

                # Check all criteria are present and not_started
                for cid in criteria_ids:
                    if cid not in coverage:
                        return False, f"Criterion {cid} not found in coverage"
                    if coverage[cid].get("coverage_level") != "not_started":
                        return (
                            False,
                            f"Criterion {cid} is {coverage[cid].get('coverage_level')}, expected 'not_started'",
                        )
                return True, ""

        return False, "Could not find criteria_coverage in any run state"

    def verify_coverage_changed(self, runs: list[t.Any]) -> tuple[bool, str]:
        """Verify that at least one criterion's coverage level changed."""
        coverage_states: list[dict[str, t.Any]] = []

        for run in runs:
            state = self.get_run_state(run)
            if state and "criteria_coverage" in state:
                coverage_states.append(state["criteria_coverage"])

        if len(coverage_states) < 2:
            return False, f"Found only {len(coverage_states)} coverage states, need at least 2 to compare"

        # Compare first and last coverage states
        first = coverage_states[0]
        last = coverage_states[-1]

        for cid in first:
            if cid in last:
                if first[cid].get("coverage_level") != last[cid].get("coverage_level"):
                    from_level = first[cid].get("coverage_level")
                    to_level = last[cid].get("coverage_level")
                    return True, f"Criterion {cid} changed from {from_level} to {to_level}"
                if first[cid].get("evidence_found", []) != last[cid].get("evidence_found", []):
                    return True, f"Criterion {cid} accumulated evidence"

        return False, "No coverage changes detected between first and last states"

    def verify_analyze_coverage_called(self, runs: list[t.Any]) -> tuple[bool, str]:
        """Verify that analyze_coverage template was used."""
        # Look for runs that indicate coverage analysis
        for run in runs:
            name_lower = run.name.lower()
            if "analyze" in name_lower and "coverage" in name_lower:
                return True, f"Found run: {run.name}"
            if "analyze_response" in name_lower:
                # Check if it has coverage in outputs
                if run.outputs and "criteria_coverage" in str(run.outputs):
                    return True, "Found coverage in analyze_response outputs"
        return False, "No analyze_coverage run found"

    def verify_evidence_captured(self, runs: list[t.Any]) -> tuple[bool, str]:
        """Verify that evidence was captured in coverage."""
        for run in reversed(runs):  # Check most recent first
            state = self.get_run_state(run)
            if state and "criteria_coverage" in state:
                for cid, coverage in state["criteria_coverage"].items():
                    evidence = coverage.get("evidence_found", [])
                    if evidence and len(evidence) > 0:
                        return True, f"Found evidence for {cid}: {evidence[0][:50]}..."
        return False, "No evidence captured in any criterion"

    def verify_turn_tracking(self, runs: list[t.Any]) -> tuple[bool, str]:
        """Verify that turn numbers are being tracked."""
        turns_seen: set[int] = set()
        for run in runs:
            state = self.get_run_state(run)
            if state and "current_turn" in state:
                turns_seen.add(state["current_turn"])
            if state and "criteria_coverage" in state:
                for coverage in state["criteria_coverage"].values():
                    if "last_touched_turn" in coverage:
                        turns_seen.add(coverage["last_touched_turn"])

        if len(turns_seen) > 1:
            return True, f"Turn numbers seen: {sorted(turns_seen)}"
        elif len(turns_seen) == 1:
            return True, f"Turn tracking present (turn {list(turns_seen)[0]})"
        return False, "No turn tracking found in state"


def display_state(state: dict[str, t.Any] | None, title: str = "Assessment State") -> None:
    """Display the assessment state using rich formatting."""
    if state is None:
        console.print(Panel("[red]State is None[/red]", title=title))
        return

    # Build a tree structure for the state
    tree = Tree(f"[bold blue]{title}[/bold blue]")

    # Phase info
    phase = state.get("phase")
    if phase is None:
        phase_str = "None"
    elif hasattr(phase, "value"):
        phase_str = phase.value
    else:
        phase_str = str(phase)
    tree.add(f"[cyan]Phase:[/cyan] {phase_str}")

    # Turn tracking
    tree.add(f"[cyan]Current Turn:[/cyan] {state.get('current_turn', 0)}")
    tree.add(f"[cyan]Prompt Index:[/cyan] {state.get('current_prompt_index', 0)}")
    tree.add(f"[cyan]Consent Confirmed:[/cyan] {state.get('learner_consent_confirmed', False)}")

    # Messages count
    messages = state.get("messages", [])
    tree.add(f"[cyan]Message Count:[/cyan] {len(messages)}")

    # Pacing information
    start_time = parse_start_time(state.get("start_time"))
    time_expectation = state.get("time_expectation_minutes")
    pacing = calculate_pacing_status(start_time, time_expectation)

    if pacing:
        pacing_branch = tree.add("[bold yellow]Pacing Status[/bold yellow]")
        pacing_branch.add(f"[cyan]Elapsed:[/cyan] {pacing['elapsed_minutes']} min")
        pacing_branch.add(f"[cyan]Remaining:[/cyan] {pacing['remaining_minutes']} min")
        pacing_branch.add(f"[cyan]Estimated Total:[/cyan] {pacing['estimated_total_minutes']} min")
        pacing_branch.add(f"[cyan]Percent Elapsed:[/cyan] {pacing['percent_elapsed']}%")

        # Color code pace status
        pace = pacing["pace"]
        if pace == "ahead":
            pace_styled = f"[green]{pace}[/green]"
        elif pace == "on_track":
            pace_styled = f"[blue]{pace}[/blue]"
        elif pace == "behind":
            pace_styled = f"[yellow]{pace}[/yellow]"
        else:  # overtime
            pace_styled = f"[red]{pace}[/red]"
        pacing_branch.add(f"[cyan]Pace:[/cyan] {pace_styled}")
    elif start_time:
        tree.add("[yellow]Pacing:[/yellow] start_time set but pacing not calculated")
    else:
        tree.add("[dim]Pacing:[/dim] start_time not set")

    # Criteria Coverage - the main focus
    coverage = state.get("criteria_coverage", {})
    if coverage:
        coverage_branch = tree.add("[bold green]Criteria Coverage[/bold green]")

        # Create a table for criteria
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("Criterion", style="cyan", width=40)
        table.add_column("Level", style="yellow", width=20)
        table.add_column("Last Turn", style="blue", width=10)
        table.add_column("Evidence", style="green", width=50)

        for cid, entry in coverage.items():
            level = entry.get("coverage_level", "unknown")
            # Color code the level
            if level == "not_started":
                level_styled = f"[dim]{level}[/dim]"
            elif level == "partially_explored":
                level_styled = f"[yellow]{level}[/yellow]"
            elif level == "fully_explored":
                level_styled = f"[green]{level}[/green]"
            else:
                level_styled = level

            last_turn = entry.get("last_touched_turn", 0)
            evidence_list = entry.get("evidence_found", [])

            # Truncate evidence for display
            if evidence_list:
                evidence_preview = evidence_list[0][:60] + "..." if len(evidence_list[0]) > 60 else evidence_list[0]
                if len(evidence_list) > 1:
                    evidence_preview += f" (+{len(evidence_list) - 1} more)"
            else:
                evidence_preview = "[dim]none[/dim]"

            criterion_name = entry.get("criterion_name", cid[:20])
            table.add_row(criterion_name, level_styled, str(last_turn), evidence_preview)

        # Add table to tree via panel
        coverage_branch.add(table)

        # Show full evidence if any exists
        for cid, entry in coverage.items():
            evidence_list = entry.get("evidence_found", [])
            if evidence_list:
                evidence_branch = coverage_branch.add(
                    f"[bold]Evidence for {entry.get('criterion_name', cid[:15])}[/bold]"
                )
                for i, evidence in enumerate(evidence_list, 1):
                    evidence_branch.add(f'[dim]{i}.[/dim] [italic]"{evidence}"[/italic]')

    console.print(tree)
    console.print()


def display_completion_analysis(state: dict[str, t.Any] | None, title: str = "Completion Analysis") -> None:
    """Display the completion analysis result using rich formatting."""
    if state is None:
        console.print(Panel("[red]State is None[/red]", title=title))
        return

    analysis = state.get("completion_analysis")
    if analysis is None:
        console.print(Panel("[yellow]No completion analysis in state[/yellow]", title=title))
        return

    tree = Tree(f"[bold blue]{title}[/bold blue]")

    # Completion decision
    completion_ready = analysis.get("completion_ready", False)
    if completion_ready:
        ready_styled = "[green]YES - Assessment Ready to Conclude[/green]"
    else:
        ready_styled = "[yellow]NO - Assessment Should Continue[/yellow]"
    tree.add(f"[cyan]Completion Ready:[/cyan] {ready_styled}")

    # Confidence level
    confidence = analysis.get("confidence", "UNKNOWN")
    if confidence == "HIGH":
        conf_styled = f"[green]{confidence}[/green]"
    elif confidence == "MEDIUM":
        conf_styled = f"[yellow]{confidence}[/yellow]"
    else:
        conf_styled = f"[red]{confidence}[/red]"
    tree.add(f"[cyan]Confidence:[/cyan] {conf_styled}")

    # Criteria status
    criteria_status = analysis.get("criteria_status", {})
    if criteria_status:
        criteria_branch = tree.add("[bold green]Criteria Status[/bold green]")

        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("Criterion", style="cyan", width=40)
        table.add_column("Status", style="yellow", width=25)

        for criterion_name, status in criteria_status.items():
            if status == "FULLY_EXPLORED":
                status_styled = f"[green]{status}[/green]"
            elif status == "PARTIALLY_EXPLORED":
                status_styled = f"[yellow]{status}[/yellow]"
            else:
                status_styled = f"[red]{status}[/red]"
            table.add_row(criterion_name, status_styled)

        criteria_branch.add(table)

    # Reasoning
    reasoning = analysis.get("reasoning", "")
    if reasoning:
        reasoning_branch = tree.add("[bold yellow]Reasoning[/bold yellow]")
        # Word wrap the reasoning
        for i in range(0, len(reasoning), 80):
            reasoning_branch.add(f"[dim]{reasoning[i : i + 80]}[/dim]")

    # Summary (if completing)
    summary = analysis.get("summary")
    if summary:
        summary_branch = tree.add("[bold green]Summary[/bold green]")
        for i in range(0, len(summary), 80):
            summary_branch.add(f"[italic]{summary[i : i + 80]}[/italic]")

    console.print(tree)
    console.print()


def parse_start_time(start_time: t.Any) -> datetime | None:
    """Parse start_time from state, handling string serialization.

    The checkpointer may serialize datetime to ISO string format.
    """
    from datetime import datetime, timezone

    if start_time is None:
        return None

    if isinstance(start_time, datetime):
        return start_time

    if isinstance(start_time, str):
        try:
            if start_time.endswith("Z"):
                return datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            elif "+" in start_time or start_time.count("-") > 2:
                return datetime.fromisoformat(start_time)
            else:
                # Naive datetime string - assume UTC
                return datetime.fromisoformat(start_time).replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    return None


def simulate_time_passage(
    checkpointer: PostgresCheckpointer,
    attempt_id: AttemptID,
    minutes_elapsed: float,
) -> None:
    """Modify start_time in state to simulate time passage.

    This allows testing different pacing scenarios without waiting.
    """
    from datetime import datetime, timedelta, timezone

    state = checkpointer.get(attempt_id)
    if state is None:
        click.echo(click.style("Error: Cannot simulate time - state is None", fg="red"))
        return

    # Calculate new start_time that would result in the desired elapsed time
    now = datetime.now(timezone.utc)
    new_start_time = now - timedelta(minutes=minutes_elapsed)
    state["start_time"] = new_start_time
    checkpointer.put(attempt_id, state)

    click.echo(f"Simulated {minutes_elapsed} minutes elapsed (start_time adjusted)")


@click.command()
@click.option(
    "--assignment-id",
    "-a",
    type=str,
    default=None,
    help="Assignment ID to test (uses first available if not specified)",
)
@click.option(
    "--automated",
    is_flag=True,
    default=False,
    help="Use automated verification via LangSmith SDK instead of manual prompts",
)
@click.option(
    "--project",
    "-p",
    type=str,
    default="default",
    help="LangSmith project name to query (default: 'default')",
)
@click.option(
    "--test-pacing",
    is_flag=True,
    default=False,
    help="Include pacing simulation tests (manipulate time to test different pacing scenarios)",
)
@click.option(
    "--test-completion",
    is_flag=True,
    default=False,
    help="Include completion detection tests (runs full assessment to test AI-driven completion)",
)
@di.inject
def execute(
    assignment_id: str | None,
    automated: bool,
    project: str,
    test_pacing: bool,
    test_completion: bool,
    session: Session = di.Manage["storage.persistent.session"],
    model: BaseChatModel = di.Provide["llm.dialogue_model"],
    env: jinja2.Environment = di.Provide["template.llm"],
) -> None:
    """Run manual test for criteria coverage and pacing tracking."""
    results = TestResult()
    verifier = LangSmithVerifier(project_name=project) if automated else None

    click.echo("=" * 60)
    mode_label = "Automated" if automated else "Manual"
    if test_pacing:
        mode_label += " + Pacing"
    if test_completion:
        mode_label += " + Completion"
    click.echo(f"Criteria Coverage Tracking - {mode_label} Test")
    click.echo("=" * 60)

    # Check LangSmith configuration
    langsmith_key = os.environ.get("LANGSMITH_API_KEY")
    langsmith_tracing = os.environ.get("LANGSMITH_TRACING")

    if not langsmith_key:
        click.echo(click.style("ERROR: LANGSMITH_API_KEY not set", fg="red"))
        click.echo("Set this in .envrc.local and reload direnv")
        sys.exit(1)

    if langsmith_tracing != "true":
        click.echo(click.style("WARNING: LANGSMITH_TRACING not set to 'true'", fg="yellow"))

    click.echo(f"LangSmith tracing: {langsmith_tracing or 'not set'}")
    click.echo(f"Mode: {'Automated' if automated else 'Manual'}")
    click.echo("")

    # Get or create assignment
    with session.begin():
        if assignment_id:
            # Use explicitly provided assignment
            aid = AssignmentID(assignment_id)
            assignment = assignment_storage.get(aid, session=session)
            if assignment is None:
                click.echo(f"Error: Assignment {assignment_id} not found", err=True)
                sys.exit(1)

            objective = obj_storage.get(assignment.objective_id, session=session)
            if objective is None:
                click.echo("Error: Objective not found", err=True)
                sys.exit(1)

            rubric_criteria = rubric_storage.find(objective_id=objective.objective_id, session=session)
            if not rubric_criteria:
                click.echo("Error: No rubric criteria found for objective", err=True)
                sys.exit(1)
        else:
            # Create or reuse test fixture
            assignment, objective, rubric_criteria = create_test_fixture(session)

        click.echo(f"Using assignment: {assignment.assignment_id}")
        click.echo(f"Objective: {objective.title}")

        serialized_criteria = [
            {
                "criterion_id": str(c.criterion_id),
                "name": c.name,
                "description": c.description,
                "proficiency_levels": [
                    {"grade": pl.grade, "description": pl.description} for pl in c.proficiency_levels
                ],
            }
            for c in rubric_criteria
        ]
        # Extract criterion IDs directly from the source objects to get proper typing
        criteria_ids: list[str] = [str(c.criterion_id) for c in rubric_criteria]

        click.echo(f"Rubric criteria: {len(serialized_criteria)}")
        for c in serialized_criteria:
            click.echo(f"  - {c['name']} ({c['criterion_id'][:8]}...)")

        # Create attempt
        attempt = attempt_storage.create(
            assignment_id=assignment.assignment_id,
            learner_id=assignment.assigned_to,
            status=AttemptStatus.InProgress,
            session=session,
        )
        attempt_id = attempt.attempt_id

        # Extract values needed after transaction
        objective_id = str(objective.objective_id)
        objective_title = objective.title
        objective_description = objective.description
        initial_prompts = objective.initial_prompts
        scope_boundaries = objective.scope_boundaries
        time_expectation_minutes = objective.time_expectation_minutes
        challenge_prompts = objective.challenge_prompts
        extension_policy = objective.extension_policy.value

    click.echo(f"\nCreated attempt: {attempt_id}")

    # Run the test flow
    asyncio.run(
        _run_test_flow(
            attempt_id=attempt_id,
            objective_id=objective_id,
            objective_title=objective_title,
            objective_description=objective_description,
            initial_prompts=initial_prompts,
            serialized_criteria=serialized_criteria,
            criteria_ids=criteria_ids,
            scope_boundaries=scope_boundaries,
            time_expectation_minutes=time_expectation_minutes,
            challenge_prompts=challenge_prompts,
            extension_policy=extension_policy,
            model=model,
            env=env,
            results=results,
            verifier=verifier,
            automated=automated,
            test_pacing=test_pacing,
            test_completion=test_completion,
        )
    )

    # Final summary
    success = results.summary()
    sys.exit(0 if success else 1)


async def _run_test_flow(
    attempt_id: AttemptID,
    objective_id: str,
    objective_title: str,
    objective_description: str,
    initial_prompts: list[str],
    serialized_criteria: list[dict[str, t.Any]],
    criteria_ids: list[str],
    scope_boundaries: str | None,
    time_expectation_minutes: int | None,
    challenge_prompts: list[str] | None,
    extension_policy: str,
    model: BaseChatModel,
    env: jinja2.Environment,
    results: TestResult,
    verifier: LangSmithVerifier | None,
    automated: bool,
    test_pacing: bool = False,
    test_completion: bool = False,
) -> None:
    """Run the async test flow."""
    checkpointer = PostgresCheckpointer()

    # ========== PHASE 1: Start Assessment ==========
    click.echo("\n" + "-" * 60)
    click.echo("PHASE 1: Starting Assessment (Orientation)")
    click.echo("-" * 60 + "\n")

    click.echo("[AI Interviewer]: ", nl=False)

    full_message = ""
    async for token in start_assessment(
        attempt_id=attempt_id,
        objective_id=objective_id,
        objective_title=objective_title,
        objective_description=objective_description,
        initial_prompts=initial_prompts,
        rubric_criteria=serialized_criteria,
        checkpointer=checkpointer,
        model=model,
        env=env,
        scope_boundaries=scope_boundaries,
        time_expectation_minutes=time_expectation_minutes,
        challenge_prompts=challenge_prompts,
        extension_policy=extension_policy,
    ):
        full_message += token
        click.echo(token, nl=False)

    click.echo("\n")

    # Verification checkpoint 1
    click.echo("\n" + "=" * 60)
    click.echo("VERIFICATION CHECKPOINT 1: Initial State")
    click.echo("=" * 60)

    if automated:
        # Get state from checkpointer for verification
        state = checkpointer.get(attempt_id)

        # Test: State exists
        results.record("Assessment state created", state is not None, "")

        if state:
            # Test: criteria_coverage exists with all criteria
            coverage = state.get("criteria_coverage", {})
            has_all_criteria = all(cid in coverage for cid in criteria_ids)
            results.record(
                "Initial criteria_coverage contains all criteria",
                has_all_criteria,
                f"Found {len(coverage)} criteria, expected {len(criteria_ids)}",
            )

            # Test: All criteria are not_started
            if coverage:
                all_not_started = all(c.get("coverage_level") == "not_started" for c in coverage.values())
                results.record(
                    "All criteria start at 'not_started'",
                    all_not_started,
                    ", ".join(f"{cid}={c.get('coverage_level')}" for cid, c in coverage.items()),
                )
    else:
        # Manual mode: display state and ask for verification
        state = checkpointer.get(attempt_id)
        display_state(state, "Initial State After Orientation")

        console.print("[bold]Expected:[/bold]")
        click.echo("  - criteria_coverage should exist with all criteria")
        click.echo("  - All criteria should have coverage_level: 'not_started'")
        click.echo("  - evidence_found should be empty")
        click.echo("")

        v1_state = click.confirm("Does the state look correct?", default=True)
        results.record("Initial criteria_coverage state correct", v1_state)

    # ========== PHASE 2: Consent and First Response ==========
    click.echo("\n" + "-" * 60)
    click.echo("PHASE 2: Learner Consent + First Substantive Response")
    click.echo("-" * 60 + "\n")

    # Simulate consent
    consent_message = "Yes, I'm ready to begin."
    click.echo(f"[Learner]: {consent_message}")
    click.echo("\n[AI Interviewer]: ", nl=False)

    full_response = ""
    async for token in run_assessment_turn(
        attempt_id=attempt_id,
        learner_message=consent_message,
        checkpointer=checkpointer,
        model=model,
        env=env,
    ):
        full_response += token
        click.echo(token, nl=False)

    click.echo("\n")

    # Send a substantive response about ratios
    substantive_response = (
        "A ratio is a comparison between two quantities. For example, if I have "
        "3 apples and 2 oranges, the ratio of apples to oranges is 3:2. "
        "I think the key thing about ratios is that they show a relationship, "
        "not just absolute numbers. If I doubled both to 6 apples and 4 oranges, "
        "the ratio would still be the same - 3:2 or equivalently 6:4."
    )

    click.echo(f"[Learner]: {substantive_response}")
    click.echo("\n[AI Interviewer]: ", nl=False)

    full_response = ""
    async for token in run_assessment_turn(
        attempt_id=attempt_id,
        learner_message=substantive_response,
        checkpointer=checkpointer,
        model=model,
        env=env,
    ):
        full_response += token
        click.echo(token, nl=False)

    click.echo("\n")

    # Verification checkpoint 2
    click.echo("\n" + "=" * 60)
    click.echo("VERIFICATION CHECKPOINT 2: After Substantive Response")
    click.echo("=" * 60)

    if automated:
        # Get updated state from checkpointer
        state = checkpointer.get(attempt_id)

        if state:
            coverage = state.get("criteria_coverage", {})
            current_turn = state.get("current_turn", 0)

            # Test: Turn counter incremented
            results.record(
                "Turn counter incremented",
                current_turn > 0,
                f"current_turn = {current_turn}",
            )

            # Test: At least one criterion has coverage updated
            any_explored = any(
                c.get("coverage_level") in ("partially_explored", "fully_explored") for c in coverage.values()
            )
            results.record(
                "Coverage level updated after response",
                any_explored,
                ", ".join(f"{cid}={c.get('coverage_level')}" for cid, c in coverage.items()),
            )

            # Test: Evidence captured for at least one criterion
            any_evidence = any(len(c.get("evidence_found", [])) > 0 for c in coverage.values())
            evidence_summary = "; ".join(
                f"{cid}: {len(c.get('evidence_found', []))} items" for cid, c in coverage.items()
            )
            results.record(
                "Evidence quotes captured",
                any_evidence,
                evidence_summary,
            )

            # Debug output
            click.echo("\nCoverage state after response:")
            for cid, c in coverage.items():
                click.echo(f"  {cid}: {c.get('coverage_level')}, evidence: {c.get('evidence_found', [])}")
        else:
            results.record("State exists after response", False, "State is None")
    else:
        # Manual mode: display state and ask for verification
        state = checkpointer.get(attempt_id)
        display_state(state, "State After Substantive Response")

        console.print("[bold]Expected changes:[/bold]")
        click.echo("  - At least one criterion should now be 'partially_explored' or 'fully_explored'")
        click.echo("  - evidence_found should contain quotes from the learner's response")
        click.echo("  - current_turn should have incremented")
        click.echo("")

        v2_coverage_updated = click.confirm("Did the coverage level change from 'not_started'?", default=True)
        results.record("Coverage level updated after response", v2_coverage_updated)

        v2_evidence = click.confirm("Does evidence_found contain relevant quotes?", default=True)
        results.record("Evidence quotes captured", v2_evidence)

    # ========== PHASE 3: Follow-up Response ==========
    click.echo("\n" + "-" * 60)
    click.echo("PHASE 3: Follow-up Response with Deeper Explanation")
    click.echo("-" * 60 + "\n")

    followup_response = (
        "When I say the ratio stays the same, I mean that the relationship between "
        "the quantities is invariant under scaling. Like if I have a recipe that calls "
        "for 2 cups of flour to 1 cup of sugar, that's a 2:1 ratio. If I want to make "
        "a bigger batch, I could use 4 cups of flour and 2 cups of sugar - still 2:1. "
        "The actual amounts changed but the proportion didn't. That's different from "
        "just saying '2 cups' which is an absolute quantity."
    )

    click.echo(f"[Learner]: {followup_response}")
    click.echo("\n[AI Interviewer]: ", nl=False)

    full_response = ""
    async for token in run_assessment_turn(
        attempt_id=attempt_id,
        learner_message=followup_response,
        checkpointer=checkpointer,
        model=model,
        env=env,
    ):
        full_response += token
        click.echo(token, nl=False)

    click.echo("\n")

    # Verification checkpoint 3
    click.echo("\n" + "=" * 60)
    click.echo("VERIFICATION CHECKPOINT 3: Coverage Progression")
    click.echo("=" * 60)

    if automated:
        # Get final state from checkpointer
        state = checkpointer.get(attempt_id)

        if state:
            coverage = state.get("criteria_coverage", {})
            current_turn = state.get("current_turn", 0)

            # Test: Turn tracking incremented further
            results.record(
                "Turn tracking incremented",
                current_turn >= 2,
                f"current_turn = {current_turn}",
            )

            # Test: last_touched_turn is updated for criteria with evidence
            criteria_with_turn_tracking = [cid for cid, c in coverage.items() if c.get("last_touched_turn", 0) > 0]
            results.record(
                "last_touched_turn is updated",
                len(criteria_with_turn_tracking) > 0,
                f"Criteria with turn tracking: {criteria_with_turn_tracking}",
            )

            # Debug output
            click.echo("\nFinal coverage state:")
            for cid, c in coverage.items():
                click.echo(
                    f"  {cid}: {c.get('coverage_level')}, "
                    f"turn: {c.get('last_touched_turn')}, "
                    f"evidence: {len(c.get('evidence_found', []))} items"
                )
        else:
            results.record("State exists after follow-up", False, "State is None")
    else:
        # Manual mode: display state and ask for verification
        state = checkpointer.get(attempt_id)
        display_state(state, "Final State After Follow-up")

        console.print("[bold]Expected changes:[/bold]")
        click.echo("  - Coverage level may have progressed (partial -> full)")
        click.echo("  - evidence_found should have accumulated more quotes")
        click.echo("  - last_touched_turn should reflect the current turn")
        click.echo("")

        v3_progression = click.confirm("Has the coverage accumulated evidence?", default=True)
        results.record("Coverage progresses with more responses", v3_progression)

        v3_turn_tracking = click.confirm("Does last_touched_turn reflect the latest turn number?", default=True)
        results.record("Turn tracking is accurate", v3_turn_tracking)

    # ========== PHASE 4: Pacing Tests (optional) ==========
    if test_pacing:
        click.echo("\n" + "-" * 60)
        click.echo("PHASE 4: Pacing Simulation Tests")
        click.echo("-" * 60 + "\n")

        estimated_time = time_expectation_minutes or 15

        # Test pacing at different time points
        pacing_scenarios = [
            (estimated_time * 0.3, "ahead", "30% elapsed - should be ahead"),
            (estimated_time * 0.6, "on_track", "60% elapsed - should be on_track"),
            (estimated_time * 0.9, "behind", "90% elapsed - should be behind"),
            (estimated_time * 1.2, "overtime", "120% elapsed - should be overtime"),
        ]

        for elapsed_minutes, expected_pace, description in pacing_scenarios:
            click.echo(f"\n[Pacing Test] {description}")

            # Simulate time passage
            simulate_time_passage(checkpointer, attempt_id, elapsed_minutes)

            # Get state and verify pacing
            state = checkpointer.get(attempt_id)
            if state:
                pacing = calculate_pacing_status(parse_start_time(state.get("start_time")), estimated_time)
                if pacing:
                    actual_pace = pacing["pace"]
                    if automated:
                        results.record(
                            f"Pacing: {description}",
                            actual_pace == expected_pace,
                            f"expected {expected_pace}, got {actual_pace}",
                        )
                    else:
                        console.print(f"  [cyan]Elapsed:[/cyan] {pacing['elapsed_minutes']} min")
                        console.print(f"  [cyan]Remaining:[/cyan] {pacing['remaining_minutes']} min")
                        console.print(f"  [cyan]Percent:[/cyan] {pacing['percent_elapsed']}%")

                        pace = pacing["pace"]
                        if pace == "ahead":
                            pace_styled = f"[green]{pace}[/green]"
                        elif pace == "on_track":
                            pace_styled = f"[blue]{pace}[/blue]"
                        elif pace == "behind":
                            pace_styled = f"[yellow]{pace}[/yellow]"
                        else:
                            pace_styled = f"[red]{pace}[/red]"

                        console.print(f"  [cyan]Pace:[/cyan] {pace_styled} (expected: {expected_pace})")

                        pace_correct = click.confirm(
                            f"Is the pace '{actual_pace}' correct?", default=actual_pace == expected_pace
                        )
                        results.record(f"Pacing: {description}", pace_correct)
                else:
                    results.record(f"Pacing: {description}", False, "Pacing calculation returned None")
            else:
                results.record(f"Pacing: {description}", False, "State is None")

        # Test that pacing appears in rendered prompts
        click.echo("\n[Pacing Test] Verify pacing appears in prompts")

        # Simulate being "behind" schedule
        simulate_time_passage(checkpointer, attempt_id, estimated_time * 0.85)

        # Send a response to trigger a new prompt with pacing
        pacing_test_response = "I understand that ratios can be simplified like fractions."
        click.echo(f"\n[Learner]: {pacing_test_response}")
        click.echo("\n[AI Interviewer]: ", nl=False)

        full_response = ""
        async for token in run_assessment_turn(
            attempt_id=attempt_id,
            learner_message=pacing_test_response,
            checkpointer=checkpointer,
            model=model,
            env=env,
        ):
            full_response += token
            click.echo(token, nl=False)

        click.echo("\n")

        if automated:
            # In automated mode, we can't easily verify the prompt content
            # but we can verify the state has pacing info
            state = checkpointer.get(attempt_id)
            if state:
                has_start_time = state.get("start_time") is not None
                results.record(
                    "Pacing info available for prompts",
                    has_start_time,
                    "start_time is set in state",
                )
        else:
            console.print("[bold]Expected behavior:[/bold]")
            click.echo("  - The AI should have been more direct/concise due to time pressure")
            click.echo("  - Pacing status was included in the prompt template")
            click.echo("")

            pacing_behavior = click.confirm(
                "Did the AI's response seem appropriately paced (direct, not verbose)?", default=True
            )
            results.record("AI adjusts behavior based on pacing", pacing_behavior)

    # ========== PHASE 5: Completion Detection Tests (optional) ==========
    if test_completion:
        click.echo("\n" + "-" * 60)
        click.echo("PHASE 5: Completion Detection Tests")
        click.echo("-" * 60 + "\n")

        # Get current state to see how many prompts we've covered
        state = checkpointer.get(attempt_id)
        if state:
            prompts_covered = state.get("current_prompt_index", 0)
            total_prompts = len(initial_prompts)

            click.echo(f"Prompts covered so far: {prompts_covered} of {total_prompts}")

            # Note: current_prompt_index tracks prompts DELIVERED, not prompts ANSWERED.
            # After all prompts are delivered (index == total), the learner still needs
            # to respond to trigger completion analysis. So we need to send at least
            # one more response when index >= total.
            remaining_prompts = total_prompts - prompts_covered
            needs_final_response = prompts_covered >= total_prompts

            # Define responses for remaining prompts
            completion_responses = [
                "For the map question, if 1 inch = 50 miles and the cities are 3.5 inches "
                "apart, I would multiply 3.5 by 50 to get 175 miles. The scale is just "
                "a ratio between map distance and real distance.",
                "I think ratios are fundamental in many areas - cooking, maps, finance. "
                "When you say a map has a 1:10000 scale, you're expressing a ratio.",
                "The connection between ratios and fractions is that they both express "
                "part-to-whole or part-to-part relationships. 3/4 is like saying 3:4 "
                "when comparing parts.",
                "In real life, I'd use ratios to figure out how to scale a recipe "
                "or calculate proportional costs. If 3 items cost $15, then 9 items "
                "would cost $45 because the ratio is maintained.",
            ]

            if remaining_prompts > 0 or needs_final_response:
                if needs_final_response:
                    click.echo("\nAll prompts delivered - sending final response to trigger completion analysis...")
                    num_responses = 1
                else:
                    click.echo(f"\nContinuing assessment to complete remaining {remaining_prompts} prompts...")
                    # Need remaining_prompts responses to deliver all prompts, plus 1 more
                    # to respond to the final prompt and trigger completion analysis
                    num_responses = remaining_prompts + 1
                click.echo("(Completion analysis should trigger after learner responds to final prompt)\n")
                for i in range(num_responses):
                    # Use a response from our list, cycling if needed
                    response = completion_responses[i % len(completion_responses)]

                    click.echo(f"\n[Learner]: {response}")
                    click.echo("\n[AI Interviewer]: ", nl=False)

                    full_response = ""
                    async for token in run_assessment_turn(
                        attempt_id=attempt_id,
                        learner_message=response,
                        checkpointer=checkpointer,
                        model=model,
                        env=env,
                    ):
                        full_response += token
                        click.echo(token, nl=False)

                    click.echo("\n")

                    # Check if completion analysis has been triggered
                    state = checkpointer.get(attempt_id)
                    if state and state.get("completion_analysis"):
                        click.echo("[Completion analysis triggered!]")
                        break

            # Now verify completion analysis
            click.echo("\n" + "=" * 60)
            click.echo("VERIFICATION: Completion Analysis")
            click.echo("=" * 60 + "\n")

            state = checkpointer.get(attempt_id)

            if automated:
                if state:
                    # Test: Completion analysis should exist after all prompts
                    analysis = state.get("completion_analysis")

                    results.record(
                        "Completion analysis triggered after all prompts",
                        analysis is not None,
                        f"current_prompt_index={state.get('current_prompt_index')}, "
                        f"total_prompts={len(initial_prompts)}",
                    )

                    if analysis:
                        # Test: completion_ready is a boolean
                        completion_ready = analysis.get("completion_ready")
                        results.record(
                            "completion_ready is boolean",
                            isinstance(completion_ready, bool),
                            f"type={type(completion_ready).__name__}",
                        )

                        # Test: confidence is valid
                        confidence = analysis.get("confidence")
                        results.record(
                            "confidence is valid level",
                            confidence in ("HIGH", "MEDIUM", "LOW"),
                            f"confidence={confidence}",
                        )

                        # Test: criteria_status has entries
                        criteria_status = analysis.get("criteria_status", {})
                        results.record(
                            "criteria_status contains entries",
                            len(criteria_status) > 0,
                            f"Found {len(criteria_status)} criteria",
                        )

                        # Test: All criteria_status values are valid
                        valid_statuses = {"FULLY_EXPLORED", "PARTIALLY_EXPLORED", "NOT_TOUCHED"}
                        all_valid = all(v in valid_statuses for v in criteria_status.values())
                        results.record(
                            "criteria_status values are valid",
                            all_valid,
                            f"statuses: {set(criteria_status.values())}",
                        )

                        # Test: reasoning is non-empty
                        reasoning = analysis.get("reasoning", "")
                        results.record(
                            "reasoning is provided",
                            len(reasoning) > 10,
                            f"length={len(reasoning)}",
                        )

                        # Debug output
                        click.echo("\nCompletion analysis result:")
                        click.echo(f"  completion_ready: {completion_ready}")
                        click.echo(f"  confidence: {confidence}")
                        click.echo(f"  criteria_status: {criteria_status}")
                        click.echo(f"  reasoning: {reasoning[:100]}...")
                else:
                    results.record("State exists for completion check", False, "State is None")
            else:
                # Manual mode: display completion analysis and ask for verification
                display_state(state, "State Before Completion Analysis Check")
                display_completion_analysis(state, "Completion Analysis Result")

                console.print("[bold]Expected behavior:[/bold]")
                click.echo("  - completion_analysis should exist in state after all prompts")
                click.echo("  - completion_ready should be true or false (AI's decision)")
                click.echo("  - confidence should be HIGH, MEDIUM, or LOW")
                click.echo("  - criteria_status should have an entry for each criterion")
                click.echo("  - reasoning should explain the AI's decision")
                click.echo("")

                if state and state.get("completion_analysis"):
                    analysis = state["completion_analysis"]

                    v5_analysis_exists = click.confirm("Does completion_analysis exist?", default=True)
                    results.record("Completion analysis exists", v5_analysis_exists)

                    v5_confidence_valid = click.confirm(
                        f"Is confidence level valid? ({analysis.get('confidence')})", default=True
                    )
                    results.record("Confidence level is valid", v5_confidence_valid)

                    v5_criteria_covered = click.confirm("Does criteria_status cover all rubric criteria?", default=True)
                    results.record("Criteria status covers all criteria", v5_criteria_covered)

                    v5_reasoning_coherent = click.confirm("Is the reasoning coherent and appropriate?", default=True)
                    results.record("Reasoning is coherent", v5_reasoning_coherent)
                else:
                    results.record(
                        "Completion analysis exists",
                        False,
                        "completion_analysis not found in state",
                    )

    # ========== Summary ==========
    click.echo("\n" + "-" * 60)
    click.echo("TEST COMPLETE")
    click.echo("-" * 60 + "\n")
