"""Behavioral tests for the writer agent."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)

from egregora.agents.types import PromptTooLargeError, WriterDeps
from egregora.agents.writer import (
    JOURNAL_TYPE_TEXT,
    JOURNAL_TYPE_THINKING,
    JOURNAL_TYPE_TOOL_CALL,
    _execute_writer_with_error_handling,
    _extract_intercalated_log,
    _extract_tool_results,
)


class TestWriterBehavior:
    """Behavioral tests for the writer agent logic."""

    def test_extract_intercalated_log_mixed_parts(self):
        """Test extraction of journal entries from mixed message parts."""
        # Given
        timestamp = datetime.now(tz=UTC)
        response = ModelResponse(
            parts=[
                ThinkingPart(content="I need to think about this."),
                TextPart(content="Here is the plan."),
                ToolCallPart(tool_name="write_post", args={"title": "Test Post"}),
            ],
            timestamp=timestamp,
        )

        # When
        entries = _extract_intercalated_log([response])

        # Then
        assert len(entries) == 3

        assert entries[0].entry_type == JOURNAL_TYPE_THINKING
        assert entries[0].content == "I need to think about this."
        assert entries[0].timestamp == timestamp

        assert entries[1].entry_type == JOURNAL_TYPE_TEXT
        assert entries[1].content == "Here is the plan."

        assert entries[2].entry_type == JOURNAL_TYPE_TOOL_CALL
        assert entries[2].tool_name == "write_post"
        assert "Test Post" in entries[2].content

    def test_extract_tool_results_success(self):
        """Test extraction of successful tool results."""
        # Given
        request = ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="write_post_tool",
                    content={"status": "success", "path": "posts/2024-01-01-test.md"},
                ),
                ToolReturnPart(
                    tool_name="write_profile_tool",
                    content={"status": "success", "path": "profiles/author.md"},
                ),
                ToolReturnPart(
                    tool_name="other_tool",
                    content={"status": "success", "path": "ignored.md"},
                ),
            ]
        )

        # When
        posts, profiles = _extract_tool_results([request])

        # Then
        assert posts == ["posts/2024-01-01-test.md"]
        assert profiles == ["profiles/author.md"]

    def test_extract_tool_results_failures_ignored(self):
        """Test that failed tool results are ignored."""
        # Given
        request = ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="write_post_tool",
                    content={"status": "error", "error": "Failed to write"},
                )
            ]
        )

        # When
        posts, profiles = _extract_tool_results([request])

        # Then
        assert posts == []
        assert profiles == []

    @patch("egregora.agents.writer._iter_writer_models")
    @patch("egregora.agents.writer._iter_provider_keys")
    @patch("egregora.agents.writer.write_posts_with_pydantic_agent")
    def test_rotation_on_429_error(self, mock_write, mock_keys, mock_models, test_config):
        """Test that execution rotates keys on 429 Too Many Requests."""
        # Given
        mock_models.return_value = ["google-gla:gemini-flash"]
        mock_keys.return_value = ["key1", "key2"]

        # First call raises 429, second succeeds
        error_429 = ModelHTTPError(status_code=429, model_name="modelA", body="Rate limit")
        mock_write.side_effect = [error_429, (["post1"], [])]

        # Use real config to avoid Mock attribute issues
        config = test_config

        deps = MagicMock(spec=WriterDeps)
        deps.window_label = "test-window"

        # When
        result = _execute_writer_with_error_handling("prompt", config, deps)

        # Then
        assert result == (["post1"], [])
        assert mock_write.call_count == 2

        # Verify calls used different keys
        calls = mock_write.call_args_list
        assert calls[0].kwargs["api_key_override"] == "key1"
        assert calls[1].kwargs["api_key_override"] == "key2"

    @patch("egregora.agents.writer._iter_writer_models")
    @patch("egregora.agents.writer._iter_provider_keys")
    @patch("egregora.agents.writer.write_posts_with_pydantic_agent")
    @patch("egregora.agents.writer._override_text_models")
    def test_model_cycling_on_server_error(
        self, mock_override, mock_write, mock_keys, mock_models, test_config
    ):
        """Test that execution cycles models on 500 Server Error."""
        # Given
        mock_models.return_value = ["modelA", "modelB"]
        mock_keys.return_value = [None]  # No specific keys for these models

        # First model fails with 500, second succeeds
        error_500 = ModelHTTPError(status_code=500, model_name="modelA", body="Server Error")
        mock_write.side_effect = [error_500, (["post1"], [])]

        # Mock config override to return a new config for the new model
        config = test_config.model_copy(deep=True)
        config.models.writer = "modelA"

        new_config = test_config.model_copy(deep=True)
        new_config.models.writer = "modelB"
        mock_override.return_value = new_config

        deps = MagicMock(spec=WriterDeps)
        deps.window_label = "test-window"

        # When
        result = _execute_writer_with_error_handling("prompt", config, deps)

        # Then
        assert result == (["post1"], [])
        assert mock_write.call_count == 2

        # Verify _override_text_models was called to switch models
        assert mock_override.call_count >= 1
        # The second call to write_posts_with_pydantic_agent should use the new config
        assert mock_write.call_args_list[1].kwargs["config"] == new_config

    @patch("egregora.agents.writer._iter_writer_models")
    @patch("egregora.agents.writer._iter_provider_keys")
    @patch("egregora.agents.writer.write_posts_with_pydantic_agent")
    def test_exhaustion_raises_runtime_error(self, mock_write, mock_keys, mock_models, test_config):
        """Test that exhaustion of all keys/models raises RuntimeError."""
        # Given
        mock_models.return_value = ["modelA"]
        mock_keys.return_value = ["key1"]

        # Fails with cyclable error (500) so it exhausts retries
        error = ModelHTTPError(status_code=500, model_name="modelA", body="Server Error")
        mock_write.side_effect = error

        config = test_config
        deps = MagicMock(spec=WriterDeps)
        deps.window_label = "test-window"

        # When/Then
        with pytest.raises(RuntimeError, match="Writer agent exhausted ALL models"):
            _execute_writer_with_error_handling("prompt", config, deps)

    @patch("egregora.agents.writer._iter_writer_models")
    @patch("egregora.agents.writer._iter_provider_keys")
    @patch("egregora.agents.writer.write_posts_with_pydantic_agent")
    def test_prompt_too_large_aborts_rotation(self, mock_write, mock_keys, mock_models, test_config):
        """Test that PromptTooLargeError aborts rotation immediately."""
        # Given
        mock_models.return_value = ["modelA", "modelB"]
        mock_keys.return_value = ["key1"]

        # Fails with PromptTooLargeError
        error = PromptTooLargeError(token_count=1000, limit=500)
        mock_write.side_effect = error

        config = test_config
        deps = MagicMock(spec=WriterDeps)
        deps.window_label = "test-window"

        # When/Then
        # Should raise PromptTooLargeError, NOT RuntimeError
        with pytest.raises(PromptTooLargeError):
            _execute_writer_with_error_handling("prompt", config, deps)

        # Should only try once
        assert mock_write.call_count == 1
