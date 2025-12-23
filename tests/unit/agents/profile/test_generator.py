from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from egregora.agents.profile.generator import (
    _generate_profile_content,
    generate_profile_posts,
)


@pytest.mark.asyncio
async def test_generate_profile_content_handles_oserror_on_get_author_profile():
    """
    Verify that _generate_profile_content handles OSError gracefully
    when get_author_profile fails.
    """
    ctx = MagicMock()
    ctx.output_format.get_author_profile.side_effect = OSError("File not found")
    ctx.config.profile.history_window_size = 0

    # Mock the LLM call to return a non-significant result
    with patch(
        "egregora.agents.profile.generator._call_llm_decision",
        new_callable=AsyncMock,
    ) as mock_llm:
        mock_llm.return_value = MagicMock(significant=False)
        result = await _generate_profile_content(ctx, [{"text": "message"}], "author_name", "author_uuid")
        assert result is None
        ctx.output_format.get_author_profile.assert_called_once_with("author_uuid")


@pytest.mark.asyncio
async def test_generate_profile_content_handles_yamlerror_on_get_author_profile():
    """
    Verify that _generate_profile_content handles YAMLError gracefully
    when get_author_profile fails to parse a profile.
    """
    ctx = MagicMock()
    ctx.output_format.get_author_profile.side_effect = yaml.YAMLError("YAML parse error")
    ctx.config.profile.history_window_size = 0

    # Mock the LLM call to return a non-significant result
    with patch(
        "egregora.agents.profile.generator._call_llm_decision",
        new_callable=AsyncMock,
    ) as mock_llm:
        mock_llm.return_value = MagicMock(significant=False)
        result = await _generate_profile_content(ctx, [{"text": "message"}], "author_name", "author_uuid")
        assert result is None
        ctx.output_format.get_author_profile.assert_called_once_with("author_uuid")


@pytest.mark.asyncio
async def test_generate_profile_content_handles_importerror_on_history():
    """
    Verify that _generate_profile_content handles ImportError gracefully
    when get_profile_history_for_context is not available.
    """
    ctx = MagicMock()
    ctx.output_format.get_author_profile.return_value = None
    ctx.config.profile.history_window_size = 5

    with (
        patch(
            "egregora.agents.profile.generator.get_profile_history_for_context",
            side_effect=ImportError("Module not found"),
        ),
        patch(
            "egregora.agents.profile.generator._call_llm_decision",
            new_callable=AsyncMock,
        ) as mock_llm,
    ):
        mock_llm.return_value = MagicMock(significant=False)
        result = await _generate_profile_content(ctx, [{"text": "message"}], "author_name", "author_uuid")
        assert result is None


@pytest.mark.asyncio
async def test_generate_profile_posts_continues_on_exception():
    """
    Verify that generate_profile_posts continues processing other authors
    if one author fails.
    """
    ctx = MagicMock()
    messages = [
        {"author_uuid": "uuid1", "author_name": "author1", "text": "msg1"},
        {"author_uuid": "uuid2", "author_name": "author2", "text": "msg2"},
    ]

    with patch(
        "egregora.agents.profile.generator._generate_profile_content",
        new_callable=AsyncMock,
    ) as mock_generate:
        # First author fails, second succeeds
        mock_generate.side_effect = [ValueError("Unexpected error"), "# Profile Update"]
        results = await generate_profile_posts(ctx, messages, "2024-01-01")

        # Assert that we have one successful profile and the error was handled.
        assert len(results) == 1
        assert mock_generate.call_count == 2
