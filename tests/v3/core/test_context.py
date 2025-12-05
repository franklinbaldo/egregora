from dataclasses import FrozenInstanceError

import pytest

from egregora_v3.core.config import EgregoraConfig
from egregora_v3.core.context import PipelineContext


def test_pipeline_context_init():
    ctx = PipelineContext()
    assert ctx.run_id is not None
    assert ctx.config is None
    assert ctx.metadata == {}

def test_pipeline_context_metadata_is_frozen():
    ctx = PipelineContext(metadata={"key": "value"})
    assert ctx.metadata["key"] == "value"

    # Check that reassignment is forbidden
    with pytest.raises(FrozenInstanceError):
        ctx.metadata = {"new": "val"}

def test_pipeline_context_with_config():
    cfg = EgregoraConfig()
    ctx = PipelineContext(config=cfg)
    assert ctx.config is cfg

def test_pipeline_context_immutability():
    ctx = PipelineContext()
    # dataclasses.FrozenInstanceError is raised
    with pytest.raises(FrozenInstanceError):
        ctx.workspace_id = "new"
