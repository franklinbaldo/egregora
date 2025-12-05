"""Tests for PipelineContext (Phase 1.4)."""
import pytest
from pathlib import Path

import pytest

from egregora_v3.core.context import PipelineContext
from egregora_v3.core.config import EgregoraConfig

def test_pipeline_context_creation():
    """Test basic PipelineContext creation."""
    ctx = PipelineContext(
        run_id="test-run-123",
        config=None,  # Optional
        workspace_id=None
    )

    assert ctx.run_id == "test-run-123"
    assert ctx.config is None
    assert ctx.workspace_id is None


def test_pipeline_context_with_config():
    """Test PipelineContext with config."""
    # Create minimal config (won't actually load files in test)
    ctx = PipelineContext(
        run_id="test-run-456",
        config=None,  # Config would be loaded separately
        workspace_id="default"
    )

    assert ctx.run_id == "test-run-456"
    assert ctx.workspace_id == "default"


def test_pipeline_context_auto_run_id():
    """Test PipelineContext generates run_id if not provided."""
    ctx = PipelineContext()

    # Should have auto-generated run_id
    assert ctx.run_id is not None
    assert len(ctx.run_id) > 0
    assert isinstance(ctx.run_id, str)


def test_pipeline_context_immutable():
    """Test PipelineContext is immutable (frozen dataclass)."""
    ctx = PipelineContext(run_id="test-123")

    # Should not be able to modify
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        ctx.run_id = "modified"


def test_pipeline_context_comparison():
    """Test PipelineContext equality."""
    ctx1 = PipelineContext(run_id="same-id")
    ctx2 = PipelineContext(run_id="same-id")
    ctx3 = PipelineContext(run_id="different-id")

    assert ctx1 == ctx2
    assert ctx1 != ctx3


def test_pipeline_context_metadata_is_immutable():
    """Metadata should be immutable after creation."""
    ctx = PipelineContext(run_id="with-metadata", metadata={"a": 1})

    with pytest.raises(Exception):
        ctx.metadata["a"] = 2
