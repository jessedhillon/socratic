"""Tests for AI-driven completion detection.

Unit tests for completion analysis node and routing edge functions.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import jinja2

from socratic.llm.assessment.edges import check_completion
from socratic.llm.assessment.nodes import analyze_completion_node
from socratic.llm.assessment.state import AgentState, CompletionAnalysis


class TestAnalyzeCompletionNodeTiming(object):
    """Tests for when completion analysis runs."""

    def test_returns_not_ready_when_prompts_remaining(self) -> None:
        """Completion analysis returns early when prompts remain."""
        mock_model = MagicMock()
        mock_env = MagicMock(spec=jinja2.Environment)

        state: AgentState = {
            "messages": [],
            "initial_prompts": ["q1", "q2", "q3"],
            "current_prompt_index": 1,  # Only 1 of 3 complete
        }

        # Run async function synchronously
        result = asyncio.run(analyze_completion_node(state, mock_model, mock_env))

        assert result == {"completion_ready": False}
        # Model should NOT be called
        mock_model.with_structured_output.assert_not_called()

    def test_returns_not_ready_when_no_prompts_complete(self) -> None:
        """Completion analysis returns early at start of assessment."""
        mock_model = MagicMock()
        mock_env = MagicMock(spec=jinja2.Environment)

        state: AgentState = {
            "messages": [],
            "initial_prompts": ["q1", "q2"],
            "current_prompt_index": 0,  # No prompts complete
        }

        result = asyncio.run(analyze_completion_node(state, mock_model, mock_env))

        assert result == {"completion_ready": False}
        mock_model.with_structured_output.assert_not_called()

    def test_returns_not_ready_when_index_equals_length_minus_one(self) -> None:
        """Completion analysis returns early when on last prompt but not done."""
        mock_model = MagicMock()
        mock_env = MagicMock(spec=jinja2.Environment)

        state: AgentState = {
            "messages": [],
            "initial_prompts": ["q1", "q2"],
            "current_prompt_index": 1,  # On second of two, not yet complete
        }

        result = asyncio.run(analyze_completion_node(state, mock_model, mock_env))

        assert result == {"completion_ready": False}
        mock_model.with_structured_output.assert_not_called()

    def test_calls_model_when_all_prompts_complete(self) -> None:
        """Completion analysis calls model when all prompts are done."""
        # Create mock completion analysis response
        mock_analysis = CompletionAnalysis(
            completion_ready=True,
            confidence="HIGH",
            criteria_status={"Criterion A": "FULLY_EXPLORED"},
            reasoning="All criteria covered",
            summary="Assessment complete",
        )

        # Setup mock chain
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_analysis)

        mock_model = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured

        # Setup mock environment
        mock_env = MagicMock(spec=jinja2.Environment)
        mock_template = MagicMock()
        mock_template.render.return_value = "test prompt"
        mock_env.get_template.return_value = mock_template

        state: AgentState = {
            "messages": [],
            "initial_prompts": ["q1", "q2"],
            "current_prompt_index": 2,  # All prompts complete (index == len)
            "objective_title": "Test Objective",
            "objective_description": "Test description",
            "scope_boundaries": None,
            "rubric_criteria": [{"name": "Criterion A", "description": "Test"}],
            "probing_depth": 0,
        }

        result = asyncio.run(analyze_completion_node(state, mock_model, mock_env))

        # Model should be called with structured output
        mock_model.with_structured_output.assert_called_once_with(CompletionAnalysis)
        mock_structured.ainvoke.assert_called_once()

        # Result should include analysis
        assert result["completion_ready"] is True
        assert "completion_analysis" in result
        assert result["completion_analysis"]["confidence"] == "HIGH"


class TestCheckCompletionRouting(object):
    """Tests for check_completion edge routing."""

    def test_routes_to_closure_when_completion_ready_true(self) -> None:
        """Routes to closure when AI says assessment is complete."""
        state: AgentState = {
            "completion_ready": True,
            "extension_policy": "allowed",  # Even with extension allowed
        }

        result = check_completion(state)

        assert result == "closure"

    def test_routes_to_extension_when_not_ready_and_extension_allowed(self) -> None:
        """Routes to extension when not ready but extension policy allows."""
        state: AgentState = {
            "completion_ready": False,
            "extension_policy": "allowed",
        }

        result = check_completion(state)

        assert result == "extension"

    def test_routes_to_closure_when_not_ready_and_extension_disallowed(self) -> None:
        """Routes to closure when not ready and extension disallowed."""
        state: AgentState = {
            "completion_ready": False,
            "extension_policy": "disallowed",
        }

        result = check_completion(state)

        assert result == "closure"

    def test_routes_to_closure_when_extension_policy_missing(self) -> None:
        """Routes to closure when extension_policy is not set (defaults to disallowed)."""
        state: AgentState = {
            "completion_ready": False,
        }

        result = check_completion(state)

        assert result == "closure"

    def test_conditional_extension_allowed_when_all_criteria_touched(self) -> None:
        """Conditional extension routes to extension when all criteria touched."""
        state: AgentState = {
            "completion_ready": False,
            "extension_policy": "conditional",
            "completion_analysis": {
                "criteria_status": {
                    "Criterion A": "FULLY_EXPLORED",
                    "Criterion B": "PARTIALLY_EXPLORED",
                }
            },
        }

        result = check_completion(state)

        assert result == "extension"

    def test_conditional_extension_denied_when_criteria_not_touched(self) -> None:
        """Conditional extension routes to closure when some criteria not touched."""
        state: AgentState = {
            "completion_ready": False,
            "extension_policy": "conditional",
            "completion_analysis": {
                "criteria_status": {
                    "Criterion A": "FULLY_EXPLORED",
                    "Criterion B": "NOT_TOUCHED",  # This one not touched
                }
            },
        }

        result = check_completion(state)

        assert result == "closure"

    def test_conditional_extension_denied_when_no_analysis(self) -> None:
        """Conditional extension routes to closure when no analysis available."""
        state: AgentState = {
            "completion_ready": False,
            "extension_policy": "conditional",
            "completion_analysis": None,
        }

        result = check_completion(state)

        assert result == "closure"

    def test_defaults_completion_ready_to_false(self) -> None:
        """Defaults completion_ready to False when not in state."""
        state: AgentState = {
            "extension_policy": "allowed",
        }

        result = check_completion(state)

        # Should act as if completion_ready=False
        assert result == "extension"
