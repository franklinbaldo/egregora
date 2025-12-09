"""Tests for writer capability registration logic."""

from __future__ import annotations

from unittest.mock import MagicMock

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

    register_writer_tools(agent, capabilities=[])

    assert set(agent.tools.keys()) == CORE_TOOL_NAMES


def test_register_writer_tools_invokes_capabilities_once() -> None:
    agent = FakeAgent()
    capability = MagicMock()
    capability.name = "mock-capability"

    register_writer_tools(agent, capabilities=[capability])

    capability.register.assert_called_once_with(agent)
    assert set(agent.tools.keys()) == CORE_TOOL_NAMES
