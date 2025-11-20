"""Deterministic Pydantic-AI test models for hermetic tests.

These helpers replace VCR-based recordings with explicit, code-defined
responses. They avoid network calls and make it easy to express expected
LLM/tool behavior directly in tests.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from pydantic_ai.models.test import TestModel


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

    def _stub_agent_setup(prompt, config, context, test_model=None):
        # This mocks write_posts_with_pydantic_agent but we need to patch deeper or higher
        # Actually, write_posts_with_pydantic_agent creates the agent.
        # We can pass a test model via the `test_model` argument if we control the caller.
        # But since we are patching, let's patch write_posts_with_pydantic_agent to use our TestModel?
        # No, better to rely on `write_posts_with_pydantic_agent` accepting `test_model`.
        # But we need to inject it.
        pass

    # The original patching target `_setup_agent_and_state` is gone.
    # `write_posts_with_pydantic_agent` takes `test_model`.
    # Consumers call `write_posts_for_window`, which calls `write_posts_with_pydantic_agent`.
    # We should patch `write_posts_with_pydantic_agent` to force a TestModel?
    # Or better, we just mock the call to agent.run_sync inside it?
    # The simplest is to monkeypatch `write_posts_with_pydantic_agent` to inject the model.

    original_func = None
    try:
        from egregora.agents.writer import write_posts_with_pydantic_agent as original

        original_func = original
    except ImportError:
        pass

    def _wrapper(*, prompt, config, context, test_model=None):
        if captured_windows is not None:
            captured_windows.append(context.window_label)

        # Use our deterministic TestModel
        test_model = WriterTestModel(window_label=context.window_label)

        return original_func(prompt=prompt, config=config, context=context, test_model=test_model)

    if original_func:
        monkeypatch.setattr("egregora.agents.writer.write_posts_with_pydantic_agent", _wrapper)
