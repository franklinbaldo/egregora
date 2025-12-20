"""Unit tests for writer agent execution module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import ToolReturnPart

from egregora.agents.writer.agent import (
    extract_tool_results,
    write_posts_with_pydantic_agent,
    execute_writer_with_error_handling,
)
from egregora.agents.types import PromptTooLargeError


class TestWriterAgent:
    def test_extract_tool_results(self):
        msg = MagicMock()
        msg.parts = [
            ToolReturnPart(
                tool_name="write_post_tool",
                content='{"status": "success", "path": "post1"}',
                tool_call_id="1",
            ),
            ToolReturnPart(
                tool_name="write_profile_tool",
                content='{"status": "success", "path": "prof1"}',
                tool_call_id="2",
            ),
        ]

        posts, profiles = extract_tool_results([msg])
        assert "post1" in posts
        assert "prof1" in profiles

    @patch("egregora.agents.writer.agent.setup_writer_agent")
    @patch("egregora.agents.writer.agent.create_writer_model")
    @patch("egregora.agents.writer.agent.configure_writer_capabilities")
    @patch("egregora.agents.writer.agent.extract_tool_results")
    @patch("egregora.agents.writer.agent.extract_intercalated_log")
    @patch("egregora.agents.writer.agent.save_journal_to_file")
    @pytest.mark.asyncio
    async def test_write_posts_with_pydantic_agent(
        self,
        mock_save,
        mock_log,
        mock_extract,
        mock_caps,
        mock_create,
        mock_setup,
    ):
        # Setup mocks
        from unittest.mock import AsyncMock

        mock_agent = MagicMock()
        mock_setup.return_value = mock_agent

        mock_result = MagicMock()
        mock_result.all_messages.return_value = []
        mock_result.usage.return_value = MagicMock(total_tokens=100)
        mock_agent.run = AsyncMock(return_value=mock_result)

        # Make create_writer_model async
        async def async_create_model(*args, **kwargs):
            return MagicMock()
        mock_create.side_effect = async_create_model

        mock_extract.return_value = (["p1"], ["pr1"])
        mock_log.return_value = ["log"]

        mock_resources = MagicMock()
        mock_resources.usage = MagicMock()
        mock_resources.quota = MagicMock()

        deps = MagicMock()
        deps.resources = mock_resources

        posts, profiles = await write_posts_with_pydantic_agent(
            prompt="system prompt",
            config=MagicMock(),
            context=deps,
        )

        assert posts == ["p1"]
        assert profiles == ["pr1"]
        mock_agent.run.assert_called_once()
        mock_save.assert_called_once()
        mock_resources.usage.record.assert_called()

    @patch("egregora.agents.writer.agent.write_posts_with_pydantic_agent")
    @pytest.mark.asyncio
    async def test_execute_writer_with_error_handling_success(self, mock_write):
        mock_write.return_value = AsyncMock(return_value=(["p1"], []))
        with patch("egregora.agents.writer.agent.write_posts_with_pydantic_agent", AsyncMock(return_value=(["p1"], []))):
            posts, profiles = await execute_writer_with_error_handling("prompt", MagicMock(), MagicMock())
            assert posts == ["p1"]

    @patch("egregora.agents.writer.agent.write_posts_with_pydantic_agent")
    @pytest.mark.asyncio
    async def test_execute_writer_re_raises_context_error(self, mock_write):
        with patch("egregora.agents.writer.agent.write_posts_with_pydantic_agent", AsyncMock(side_effect=PromptTooLargeError("model", "w1"))):
            with pytest.raises(PromptTooLargeError):
                await execute_writer_with_error_handling("prompt", MagicMock(), MagicMock())

    @patch("egregora.agents.writer.agent.write_posts_with_pydantic_agent")
    @pytest.mark.asyncio
    async def test_execute_writer_wraps_general_error(self, mock_write):
        with patch("egregora.agents.writer.agent.write_posts_with_pydantic_agent", AsyncMock(side_effect=ValueError("boom"))):
            with pytest.raises(RuntimeError) as exc:
                await execute_writer_with_error_handling("prompt", MagicMock(), MagicMock())
            assert "Writer agent failed" in str(exc.value)
