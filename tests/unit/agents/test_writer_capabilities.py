"""Tests for writer capability registration logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from egregora.agents.writer_helpers import register_writer_tools


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


def test_register_writer_tools_registers_core_tools() -> None:
    agent = FakeAgent()
    config = MagicMock()
    config.rag.enabled = False

    with patch("egregora.agents.writer_helpers.is_banner_generation_available", return_value=False):
        register_writer_tools(agent, config)

    assert set(agent.tools.keys()) == CORE_TOOL_NAMES


def test_register_writer_tools_registers_conditional_tools() -> None:
    agent = FakeAgent()
    config = MagicMock()
    config.rag.enabled = True

    with patch("egregora.agents.writer_helpers.is_banner_generation_available", return_value=True):
        register_writer_tools(agent, config)

    expected_tools = CORE_TOOL_NAMES | {"search_media", "generate_banner"}
    assert set(agent.tools.keys()) == expected_tools
