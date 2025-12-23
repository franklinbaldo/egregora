"""Tests for writer tool registration logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from egregora.agents.writer_helpers import register_writer_tools
from egregora.config.settings import EgregoraConfig, RAGSettings


class FakeAgent:
    """Minimal stub of ``pydantic_ai.Agent`` for tool registration tests."""

    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self, fn):
        self.tools[fn.__name__] = fn
        return fn


CORE_TOOL_NAMES = {
    "write_post_tool",
    "read_profile_tool",
    "write_profile_tool",
    "annotate_conversation_tool",
}


@patch("egregora.agents.writer_helpers.is_banner_generation_available", return_value=False)
def test_register_writer_tools_registers_core_tools(mock_is_banner_available) -> None:
    agent = FakeAgent()
    config = MagicMock(spec=EgregoraConfig)
    config.rag = MagicMock(spec=RAGSettings)
    config.rag.enabled = False

    register_writer_tools(agent, config)

    assert set(agent.tools.keys()) == CORE_TOOL_NAMES
    mock_is_banner_available.assert_called_once()


@patch("egregora.agents.writer_helpers.is_banner_generation_available", return_value=False)
def test_register_writer_tools_registers_rag_tools_if_enabled(mock_is_banner_available) -> None:
    agent = FakeAgent()
    config = MagicMock(spec=EgregoraConfig)
    config.rag = MagicMock(spec=RAGSettings)
    config.rag.enabled = True

    register_writer_tools(agent, config)

    assert "search_media" in agent.tools
    assert CORE_TOOL_NAMES.issubset(agent.tools)
    mock_is_banner_available.assert_called_once()
