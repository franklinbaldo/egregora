from uuid import UUID

from egregora_v3.core.config import EgregoraConfig
from egregora_v3.core.pipeline import PipelineContext


def test_pipeline_context_defaults():
    """Test PipelineContext initialization with defaults."""
    config = EgregoraConfig()
    ctx = PipelineContext(config=config)

    assert isinstance(ctx.run_id, UUID)
    assert ctx.dry_run is False
    assert ctx.config == config


def test_pipeline_context_overrides():
    """Test PipelineContext with overridden values."""
    config = EgregoraConfig(debug=True)
    custom_uuid = UUID("12345678-1234-5678-1234-567812345678")

    ctx = PipelineContext(config=config, run_id=custom_uuid, dry_run=True)

    assert ctx.run_id == custom_uuid
    assert ctx.dry_run is True
    assert ctx.config.debug is True
