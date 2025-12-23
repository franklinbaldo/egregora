"""Tests for writer agent decoupling logic."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from egregora.agents.writer import (
    JournalEntry,
    JournalEntryParams,
    _process_single_tool_result,
    _save_journal_to_file,
    write_posts_for_window,
    WindowProcessingParams,
)
from egregora.config.settings import EgregoraConfig


class TestWriterDecoupling:
    def test_process_tool_result_ignores_path_structure(self):
        """Test that tool result processing relies on tool_name, not path string structure."""
        saved_posts = []
        saved_profiles = []

        # Scenario: Tool name is missing, but path looks like a post.
        # In decoupled world, this should NOT be blindly added as a post
        # because we shouldn't rely on string matching file paths.

        content = {"status": "success", "path": "/posts/legacy-path.md"}
        _process_single_tool_result(content, None, saved_posts, saved_profiles)

        assert len(saved_posts) == 0, "Should not infer type from path string"

    def test_process_tool_result_uses_tool_name(self):
        """Test that tool result processing uses tool_name correctly."""
        saved_posts = []
        saved_profiles = []

        content = {"status": "success", "path": "some-id"}
        _process_single_tool_result(content, "write_post_tool", saved_posts, saved_profiles)

        assert "some-id" in saved_posts

    @patch("egregora.agents.writer.Environment")
    def test_journal_saves_agnostic_content(self, mock_env_cls):
        """Test that journal saving does not apply MkDocs-specific path replacements."""
        # Arrange
        mock_env = MagicMock()
        mock_template = MagicMock()
        # Template renders content with relative path
        mock_template.render.return_value = "Image at ../media/image.jpg"
        mock_env.get_template.return_value = mock_template
        mock_env_cls.return_value = mock_env

        mock_output = MagicMock()

        # We need at least one entry for save to happen
        entry = JournalEntry(entry_type="journal", content="test", timestamp=datetime.now())

        params = JournalEntryParams(
            intercalated_log=[entry],
            window_label="test-window",
            output_format=mock_output,
            posts_published=0,
            profiles_updated=0,
            window_start=datetime.now(),
            window_end=datetime.now(),
        )

        # Act
        _save_journal_to_file(params)

        # Assert
        # Check what was persisted
        mock_output.persist.assert_called_once()
        doc = mock_output.persist.call_args[0][0]

        # The content should PRESERVE "../media/" and NOT replace it with "/media/"
        assert "../media/image.jpg" in doc.content
        assert "/media/image.jpg" not in doc.content.replace("../media/", "")

@pytest.mark.asyncio
@patch("egregora.agents.writer._build_context_and_signature")
@patch("egregora.agents.writer._check_writer_cache")
@patch("egregora.agents.writer._prepare_writer_dependencies")
@patch("egregora.agents.writer._render_writer_prompt")
@patch("egregora.agents.writer._execute_writer_with_error_handling")
@patch("egregora.agents.writer._finalize_writer_results")
async def test_write_posts_for_window_smoke_test(
    mock_finalize,
    mock_execute,
    mock_render,
    mock_prepare_deps,
    mock_check_cache,
    mock_build_context,
):
    """Smoke test to ensure write_posts_for_window can be called without error."""
    mock_table = MagicMock()
    mock_table.count.return_value.execute.return_value = 1
    mock_check_cache.return_value = None
    mock_build_context.return_value = (MagicMock(), "signature")
    mock_execute.return_value = ([], [])
    mock_finalize.return_value = {"posts": [], "profiles": []}

    params = WindowProcessingParams(
        table=mock_table,
        window_start=datetime.now(),
        window_end=datetime.now(),
        resources=MagicMock(),
        config=EgregoraConfig(),
        cache=MagicMock(),
    )

    result = await write_posts_for_window(params)
    assert result == {"posts": [], "profiles": []}
    mock_execute.assert_called_once()
    mock_finalize.assert_called_once()
