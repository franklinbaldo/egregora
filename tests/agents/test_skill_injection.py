"""Tests for skill injection system.

This module tests the dynamic skill loading and sub-agent spawning functionality.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from egregora.agents.tools.skill_injection import (
    _SKILL_COMPLETION_MARKER,
    SkillCompletionResult,
    _extract_summary_from_result,
    end_skill_use,
)
from egregora.agents.tools.skill_loader import SkillLoader


class TestSkillLoader:
    """Test skill loader functionality."""

    def test_find_skills_dir_in_current_dir(self, tmp_path):
        """Test finding .egregora/skills in current directory."""
        skills_dir = tmp_path / ".egregora" / "skills"
        skills_dir.mkdir(parents=True)

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            loader = SkillLoader()
            assert loader.skills_dir == skills_dir

    def test_find_skills_dir_in_parent(self, tmp_path):
        """Test finding .egregora/skills in parent directory."""
        skills_dir = tmp_path / ".egregora" / "skills"
        skills_dir.mkdir(parents=True)
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        with patch("pathlib.Path.cwd", return_value=subdir):
            loader = SkillLoader()
            assert loader.skills_dir == skills_dir

    def test_load_skill_markdown(self, tmp_path):
        """Test loading a .md skill file."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_file = skills_dir / "test-skill.md"
        skill_content = "# Test Skill\n\nThis is a test skill."
        skill_file.write_text(skill_content)

        loader = SkillLoader(skills_dir)
        skill = loader.load_skill("test-skill")

        assert skill.name == "test-skill"
        assert skill.content == skill_content
        assert skill.source_path == skill_file
        assert "test skill" in skill.description.lower()

    def test_load_skill_not_found(self, tmp_path):
        """Test loading non-existent skill raises FileNotFoundError."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        loader = SkillLoader(skills_dir)
        with pytest.raises(FileNotFoundError, match="not found"):
            loader.load_skill("nonexistent")

    def test_load_skill_empty_file(self, tmp_path):
        """Test loading empty skill file raises ValueError."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_file = skills_dir / "empty.md"
        skill_file.write_text("")

        loader = SkillLoader(skills_dir)
        with pytest.raises(ValueError, match="empty"):
            loader.load_skill("empty")

    def test_list_available_skills(self, tmp_path):
        """Test listing all available skills."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "skill1.md").write_text("Skill 1")
        (skills_dir / "skill2.txt").write_text("Skill 2")
        (skills_dir / "skill3.skill").write_text("Skill 3")

        loader = SkillLoader(skills_dir)
        skills = loader.list_available_skills()

        assert sorted(skills) == ["skill1", "skill2", "skill3"]

    def test_extract_description_from_paragraph(self, tmp_path):
        """Test extracting description from first paragraph."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill_file = skills_dir / "desc-test.md"
        skill_file.write_text("# Heading\n\nThis is a description of the skill.\n\nMore content.")

        loader = SkillLoader(skills_dir)
        skill = loader.load_skill("desc-test")

        assert "description of the skill" in skill.description.lower()


class TestEndSkillUse:
    """Test end_skill_use tool."""

    def test_end_skill_use_returns_result(self):
        """Test end_skill_use returns SkillCompletionResult."""
        summary = "Task completed successfully."
        result = end_skill_use(summary)

        assert isinstance(result, SkillCompletionResult)
        assert result.summary == summary
        assert result.marker == _SKILL_COMPLETION_MARKER

    def test_end_skill_use_with_multiline_summary(self):
        """Test end_skill_use with multiline summary."""
        summary = """Task completed.

        Key findings:
        1. Finding one
        2. Finding two
        """
        result = end_skill_use(summary)

        assert result.summary == summary
        assert "\n" in result.summary


class TestExtractSummaryFromResult:
    """Test summary extraction from agent results."""

    def test_extract_from_skill_completion_result(self):
        """Test extracting summary from SkillCompletionResult."""
        completion = SkillCompletionResult(summary="Test summary")
        mock_result = Mock(data=completion)

        summary = _extract_summary_from_result(mock_result)

        assert _SKILL_COMPLETION_MARKER in summary
        assert "Test summary" in summary

    def test_extract_from_dict_with_summary(self):
        """Test extracting from dict with summary key."""
        mock_result = Mock(data={"summary": "Dict summary"})

        summary = _extract_summary_from_result(mock_result)

        assert summary == "Dict summary"

    def test_extract_from_string_data(self):
        """Test extracting from plain string data."""
        mock_result = Mock(data="Plain string result")

        summary = _extract_summary_from_result(mock_result)

        assert summary == "Plain string result"

    def test_extract_from_result_without_data(self):
        """Test extracting from result without data attribute."""
        mock_result = "Just a string"

        summary = _extract_summary_from_result(mock_result)

        assert summary == "Just a string"


# Note: Integration tests for use_skill are skipped for now due to complexity
# of async testing with pydantic-ai agents. The core functionality is tested
# through unit tests above. End-to-end testing should be done manually or
# through the actual agent integration.
