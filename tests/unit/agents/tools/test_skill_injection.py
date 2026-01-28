"""Tests for skill injection tool."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai import RunContext
from pydantic_ai.models import Model

from egregora.agents.tools.skill_injection import (
    _SKILL_COMPLETION_MARKER,
    SkillCompletionResult,
    SkillInjectionSupport,
    end_skill_use,
    use_skill,
)
from egregora.agents.tools.skill_loader import SkillContent


class MockDeps(SkillInjectionSupport):
    """Mock dependencies implementing SkillInjectionSupport."""

    @property
    def agent_model(self) -> Model:
        return MagicMock(spec=Model)

    @property
    def agent_tools(self) -> list[Any]:
        return []

    @property
    def agent_system_prompt(self) -> str:
        return "Parent Prompt"


@pytest.fixture
def mock_deps():
    return MockDeps()


@pytest.fixture
def mock_ctx(mock_deps):
    ctx = MagicMock(spec=RunContext)
    ctx.deps = mock_deps
    return ctx


@pytest.fixture
def mock_skill_loader():
    with patch("egregora.agents.tools.skill_injection.get_skill_loader") as mock:
        loader = MagicMock()
        mock.return_value = loader
        yield loader


@pytest.fixture
def mock_render_prompt():
    with patch("egregora.agents.tools.skill_injection.render_prompt") as mock:
        mock.return_value = "Rendered Prompt"
        yield mock


def test_end_skill_use():
    """Test end_skill_use tool."""
    summary = "Task completed successfully."
    result = end_skill_use(summary)

    assert isinstance(result, SkillCompletionResult)
    assert result.summary == summary
    # Check that marker is not visible in standard repr/dict if excluded
    # But it should be present in the object
    assert result.marker == _SKILL_COMPLETION_MARKER


def test_use_skill_invalid_deps(mock_ctx):
    """Test use_skill fails if deps don't implement protocol."""
    mock_ctx.deps = object()  # Not SkillInjectionSupport

    result = use_skill(mock_ctx, "test-skill", "Do something")

    assert "ERROR" in result
    assert "Parent agent deps must implement SkillInjectionSupport" in result


def test_use_skill_not_found(mock_ctx, mock_skill_loader):
    """Test use_skill fails if skill not found."""
    mock_skill_loader.load_skill.side_effect = FileNotFoundError()
    mock_skill_loader.list_available_skills.return_value = ["other-skill"]

    result = use_skill(mock_ctx, "missing-skill", "Do something")

    assert "ERROR" in result
    assert "Skill 'missing-skill' not found" in result
    assert "other-skill" in result


def test_use_skill_execution_failure(mock_ctx, mock_skill_loader, mock_render_prompt):
    """Test use_skill handles sub-agent execution exceptions."""
    _ = mock_render_prompt
    mock_skill_loader.load_skill.return_value = SkillContent(
        name="test", content="content", description="desc", source_path=Path("/tmp/test")
    )

    # Mock Agent to raise exception during run
    with patch("egregora.agents.tools.skill_injection.Agent") as mock_agent_cls:
        mock_agent_instance = mock_agent_cls.return_value
        mock_agent_instance.run_sync.side_effect = RuntimeError("Agent crash")

        result = use_skill(mock_ctx, "test-skill", "Do something")

        assert "ERROR" in result
        assert "Agent crash" in result


def test_use_skill_success_natural_finish(mock_ctx, mock_skill_loader, mock_render_prompt):
    """Test use_skill success when agent finishes naturally (no tool call)."""
    _ = mock_render_prompt
    mock_skill_loader.load_skill.return_value = SkillContent(
        name="test", content="content", description="desc", source_path=Path("/tmp/test")
    )

    with patch("egregora.agents.tools.skill_injection.Agent") as mock_agent_cls:
        mock_agent_instance = mock_agent_cls.return_value

        # Mock result.output (as expected by _extract_summary_from_result)
        mock_result = MagicMock()
        mock_result.output = "Natural summary"

        mock_agent_instance.run_sync.return_value = mock_result

        result = use_skill(mock_ctx, "test-skill", "Do something")

        assert result == "Natural summary"

        # Verify Agent was initialized with correct tools
        _, kwargs = mock_agent_cls.call_args
        tools = kwargs["tools"]
        assert end_skill_use in tools


def test_use_skill_success_with_end_skill_use(mock_ctx, mock_skill_loader, mock_render_prompt):
    """Test use_skill success when agent calls end_skill_use."""
    _ = mock_render_prompt
    mock_skill_loader.load_skill.return_value = SkillContent(
        name="test", content="content", description="desc", source_path=Path("/tmp/test")
    )

    with patch("egregora.agents.tools.skill_injection.Agent") as mock_agent_cls:
        mock_agent_instance = mock_agent_cls.return_value

        # Mock result containing SkillCompletionResult
        completion = SkillCompletionResult(summary="Explicit summary")

        mock_result = MagicMock()
        mock_result.output = completion

        mock_agent_instance.run_sync.return_value = mock_result

        result = use_skill(mock_ctx, "test-skill", "Do something")

        assert result == "Explicit summary"
