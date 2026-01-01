"""Tests for writer agent decoupling logic."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest  # type: ignore
from jinja2.exceptions import TemplateNotFound  # type: ignore

from egregora.agents.exceptions import AgentError as JournalFileSystemError  # type: ignore[import-not-found, unused-ignore]
from egregora.agents.exceptions import AgentError as JournalTemplateError  # type: ignore[import-not-found, unused-ignore]
import egregora.agents.writer as writer_module  # type: ignore[import-not-found, unused-ignore]


class TestWriterDecoupling:
    def test_process_tool_result_ignores_path_structure(self) -> None:
        """Test that tool result processing relies on tool_name, not path string structure."""
        saved_posts: list[str] = []
        saved_profiles: list[str] = []

        # Scenario: Tool name is missing, but path looks like a post.
        # In decoupled world, this should NOT be blindly added as a post
        # because we shouldn't rely on string matching file paths.

        content = {"status": "success", "path": "/posts/legacy-path.md"}
        writer_module._process_single_tool_result(content, None, saved_posts, saved_profiles)

        assert len(saved_posts) == 0, "Should not infer type from path string"

    def test_process_tool_result_uses_tool_name(self) -> None:
        """Test that tool result processing uses tool_name correctly."""
        saved_posts: list[str] = []
        saved_profiles: list[str] = []

        content = {"status": "success", "path": "some-id"}
        writer_module._process_single_tool_result(content, "write_post_tool", saved_posts, saved_profiles)

        assert "some-id" in saved_posts

    @patch("egregora.agents.writer.Environment")
    def test_journal_saves_agnostic_content(self, mock_env_cls: MagicMock) -> None:
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
        entry = writer_module.JournalEntry(entry_type="journal", content="test", timestamp=datetime.now())

        params = writer_module.JournalEntryParams(
            intercalated_log=[entry],
            window_label="test-window",
            output_format=mock_output,
            posts_published=0,
            profiles_updated=0,
            window_start=datetime.now(),
            window_end=datetime.now(),
        )

        # Act
        writer_module._save_journal_to_file(params)

        # Assert
        # Check what was persisted
        mock_output.persist.assert_called_once()
        doc = mock_output.persist.call_args[0][0]

        # The content should PRESERVE "../media/" and NOT replace it with "/media/"
        assert "../media/image.jpg" in doc.content
        assert "/media/image.jpg" not in doc.content.replace("../media/", "")

    @patch("egregora.agents.writer.Environment")
    def test_save_journal_raises_template_error(self, mock_env_cls: MagicMock) -> None:
        """Test that _save_journal_to_file raises JournalTemplateError on template issues."""
        # Arrange
        mock_env = MagicMock()
        mock_env.get_template.side_effect = TemplateNotFound("journal.md.jinja")
        mock_env_cls.return_value = mock_env

        params = writer_module.JournalEntryParams(
            intercalated_log=[writer_module.JournalEntry("journal", "test", datetime.now())],
            window_label="test-window",
            output_format=MagicMock(),
            posts_published=0,
            profiles_updated=0,
            window_start=datetime.now(),
            window_end=datetime.now(),
        )

        # Act & Assert
        with pytest.raises(JournalTemplateError) as exc_info:
            writer_module._save_journal_to_file(params)

        assert "journal.md.jinja" in str(exc_info.value)

    @patch("egregora.agents.writer.Environment")
    def test_save_journal_raises_filesystem_error(self, mock_env_cls: MagicMock) -> None:
        """Test that _save_journal_to_file raises JournalFileSystemError on file system issues."""
        # Arrange
        mock_env = MagicMock()
        mock_template = MagicMock()
        mock_template.render.return_value = "Some content"
        mock_env.get_template.return_value = mock_template
        mock_env_cls.return_value = mock_env

        mock_output = MagicMock()
        mock_output.persist.side_effect = OSError("Disk full")

        params = writer_module.JournalEntryParams(
            intercalated_log=[writer_module.JournalEntry("journal", "test", datetime.now())],
            window_label="test-window",
            output_format=mock_output,
            posts_published=0,
            profiles_updated=0,
            window_start=datetime.now(),
            window_end=datetime.now(),
        )

        # Act & Assert
        with pytest.raises(JournalFileSystemError) as exc_info:
            writer_module._save_journal_to_file(params)

        assert "Disk full" in str(exc_info.value)


@pytest.mark.asyncio
@patch("egregora.agents.writer.write_posts_with_pydantic_agent")
async def test_execute_writer_raises_specific_exception(
    mock_pydantic_writer: MagicMock, test_config: MagicMock
) -> None:
    """Test that _execute_writer_with_error_handling raises RuntimeError on agent failure."""
    # Arrange
    mock_pydantic_writer.side_effect = Exception("LLM provider outage")
    mock_deps = MagicMock()
    mock_deps.window_label = "test-window"

    # Act & Assert
    with pytest.raises(RuntimeError) as exc_info:
        await writer_module._execute_writer_with_error_handling(
            prompt="test prompt",
            config=test_config,
            deps=mock_deps,
        )

    assert "LLM provider outage" in str(exc_info.value.__cause__)
    assert "test-window" in str(exc_info.value)


@pytest.mark.asyncio
@patch("egregora.agents.writer.build_context_and_signature")
@patch("egregora.agents.writer.check_writer_cache")
@patch("egregora.agents.writer.prepare_writer_dependencies")
@patch("egregora.agents.writer._render_writer_prompt")
@patch("egregora.agents.writer._execute_writer_with_error_handling")
@patch("egregora.agents.writer._finalize_writer_results")
async def test_write_posts_for_window_smoke_test(
    mock_finalize: MagicMock,
    mock_execute: MagicMock,
    mock_render: MagicMock,
    mock_prepare_deps: MagicMock,
    mock_check_cache: MagicMock,
    mock_build_context: MagicMock,
    test_config: MagicMock,
) -> None:
    """Smoke test to ensure write_posts_for_window can be called without error."""
    mock_table = MagicMock()
    mock_table.count.return_value.execute.return_value = 1
    mock_check_cache.return_value = None
    mock_build_context.return_value = (MagicMock(), "signature")
    mock_execute.return_value = ([], [])
    mock_finalize.return_value = {"posts": [], "profiles": []}

    params = writer_module.WindowProcessingParams(
        table=mock_table,
        window_start=datetime.now(),
        window_end=datetime.now(),
        resources=MagicMock(),
        config=test_config,
        cache=MagicMock(),
    )

    result = await writer_module.write_posts_for_window(params)
    assert result == {"posts": [], "profiles": []}
    mock_execute.assert_called_once()
    mock_finalize.assert_called_once()
    mock_render.assert_called_once()
    mock_prepare_deps.assert_called_once()


@pytest.mark.asyncio
@patch("egregora.agents.writer.write_posts_with_pydantic_agent")
async def test_execute_writer_raises_specific_error(
    mock_writer_agent: MagicMock, test_config: MagicMock
) -> None:
    """Test that _execute_writer_with_error_handling raises RuntimeError on agent failure."""
    # Arrange
    original_error = ValueError("Underlying agent error")
    mock_writer_agent.side_effect = original_error

    mock_deps = MagicMock()
    mock_deps.window_label = "test-window-123"

    # Act & Assert
    with pytest.raises(RuntimeError) as exc_info:
        await writer_module._execute_writer_with_error_handling(
            prompt="test prompt",
            config=test_config,
            deps=mock_deps,
        )

    # Verify the exception has the correct context
    assert "test-window-123" in str(exc_info.value)
    assert exc_info.value.__cause__ is original_error


@pytest.mark.asyncio
@patch("egregora.agents.writer.build_context_and_signature")
@patch("egregora.agents.writer.check_writer_cache")
@patch("egregora.agents.writer.prepare_writer_dependencies")
@patch("egregora.agents.writer._render_writer_prompt")
@patch("egregora.agents.writer._execute_writer_with_error_handling")
@patch("egregora.agents.writer._finalize_writer_results")
async def test_write_posts_for_window_cache_hit_valid(
    mock_finalize: MagicMock,
    mock_execute: MagicMock,
    mock_render: MagicMock,
    mock_prepare_deps: MagicMock,
    mock_check_cache: MagicMock,
    mock_build_context: MagicMock,
    test_config: MagicMock,
) -> None:
    """Test cache hit logic when files exist on disk."""
    mock_table = MagicMock()
    mock_table.count.return_value.execute.return_value = 1
    mock_build_context.return_value = (MagicMock(), "signature")

    # Cache HIT
    cached_result = {"posts": ["some-slug"], "profiles": []}
    mock_check_cache.return_value = cached_result

    # Mock resources
    mock_resources = MagicMock()
    # Mock posts_dir existence
    mock_resources.output.posts_dir.glob.return_value = [Path("found.md")]

    params = writer_module.WindowProcessingParams(
        table=mock_table,
        window_start=datetime.now(),
        window_end=datetime.now(),
        resources=mock_resources,
        config=test_config,
        cache=MagicMock(),
    )

    result = await writer_module.write_posts_for_window(params)

    assert result == cached_result
    mock_execute.assert_not_called()


def test_regenerate_site_indices_skips_if_no_site_root() -> None:
    """Test that site generation is skipped if site_root is None."""
    adapter = MagicMock()
    adapter.site_root = None

    with patch("egregora.agents.writer.SiteGenerator") as mock_gen:
        writer_module._regenerate_site_indices(adapter)
        mock_gen.assert_not_called()
