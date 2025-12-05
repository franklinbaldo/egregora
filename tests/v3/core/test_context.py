from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

from egregora_v3.core.catalog import ContentLibrary
from egregora_v3.core.config import EgregoraConfig
from egregora_v3.core.context import PipelineContext


@pytest.fixture
def mock_library():
    # Mocking ContentLibrary which is a Pydantic model is tricky if strict validation is on.
    # But here we just need an object that passes type check if we are not doing runtime type checking on init.
    # However, PipelineContext is a dataclass, so it doesn't enforce types at runtime unless we use something like typeguard.
    # But for the sake of the test, we'll use a MagicMock.
    return MagicMock(spec=ContentLibrary)


def test_pipeline_context_init(mock_library):
    # It should require library
    ctx = PipelineContext(library=mock_library)
    assert ctx.run_id is not None
    assert ctx.config is None
    assert ctx.library is mock_library
    assert ctx.metadata == {}


def test_pipeline_context_metadata_is_frozen(mock_library):
    ctx = PipelineContext(library=mock_library, metadata={"key": "value"})
    assert ctx.metadata["key"] == "value"

    # Check that reassignment is forbidden
    with pytest.raises(FrozenInstanceError):
        ctx.metadata = {"new": "val"}


def test_pipeline_context_with_config(mock_library):
    cfg = EgregoraConfig()
    ctx = PipelineContext(library=mock_library, config=cfg)
    assert ctx.config is cfg


def test_pipeline_context_immutability(mock_library):
    ctx = PipelineContext(library=mock_library)
    # dataclasses.FrozenInstanceError is raised
    with pytest.raises(FrozenInstanceError):
        ctx.workspace_id = "new"
