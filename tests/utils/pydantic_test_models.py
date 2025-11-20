"""Deterministic Pydantic-AI test models for hermetic tests.

These helpers replace VCR-based recordings with explicit, code-defined
responses. They avoid network calls and make it easy to express expected
LLM/tool behavior directly in tests.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from egregora.agents.writer.tools import register_writer_tools
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from egregora.agents.writer.agent import (
    WriterAgentReturn,
    WriterAgentState,
    _create_writer_agent_state,
)


class MockEmbeddingModel:
    """Deterministic embedding stub used for offline tests."""

    def __init__(self, dimensionality: int = 128) -> None:
        self.dimensionality = dimensionality

    def embed(self, text: str) -> list[float]:
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        vector = [rng.uniform(-1, 1) for _ in range(self.dimensionality)]
        magnitude = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / magnitude for v in vector]


class WriterTestModel(TestModel):
    """TestModel that always calls ``write_post_tool`` with predictable args."""

    def __init__(self, *, window_label: str) -> None:
        super().__init__(call_tools=["write_post_tool"])
        self.window_label = window_label

    def gen_tool_args(self, tool_def: Any) -> dict[str, Any]:
        if getattr(tool_def, "name", None) == "write_post_tool":
            safe_label = self.window_label.replace(" ", "-").replace(":", "")
            return {
                "metadata": {
                    "title": f"Stub Post for {self.window_label}",
                    "slug": f"{safe_label}-stub",
                    "date": "2025-10-28",
                    "tags": ["stub"],
                    "authors": ["system"],
                    "summary": "Deterministic stub content",
                },
                "content": "This is a deterministic stub post used during tests.",
            }
        return super().gen_tool_args(tool_def)


def install_writer_test_model(monkeypatch, captured_windows: list[str] | None = None) -> None:
    """Install deterministic writer agent that avoids network calls."""

    def _stub_agent_setup(config, context, test_model=None):
        window_label = f"{context.start_time:%Y-%m-%d %H:%M} to {context.end_time:%H:%M}"
        if captured_windows is not None:
            captured_windows.append(window_label)

        agent = Agent[WriterAgentState, WriterAgentReturn](
            model=WriterTestModel(window_label=window_label), deps_type=WriterAgentState
        )

        register_writer_tools(agent, enable_banner=False, enable_rag=False)
        state = _create_writer_agent_state(context, config)
        return agent, state, window_label

    monkeypatch.setattr("egregora.agents.writer.agent._setup_agent_and_state", _stub_agent_setup)
