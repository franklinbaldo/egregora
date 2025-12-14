"""Tests for writer agent decoupling logic."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from egregora.agents.writer import (
    JournalEntry,
    JournalEntryParams,
    _process_single_tool_result,
    _save_journal_to_file,
)


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
