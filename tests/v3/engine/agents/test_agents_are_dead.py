"""Tests to confirm the status of potentially dead agents."""
import pytest


def test_agents_are_deleted():
    """
    This test is designed to pass if the agents are not importable.
    """
    with pytest.raises(ImportError):
        from egregora_v3.engine.agents.enricher import EnricherAgent  # noqa: F401
        from egregora_v3.engine.agents.writer import WriterAgent  # noqa: F401
