from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from egregora.orchestration.context import PipelineConfig, PipelineContext, PipelineState


def _build_config() -> PipelineConfig:
    config = MagicMock()
    config.enrichment.enabled = False
    config.rag.enabled = False
    config.rag.mode = "standard"
    config.rag.nprobe = 0
    config.rag.overfetch = 0
    config.models.writer = "writer"
    config.models.enricher = "enricher"
    config.models.embedding = "embedding"

    site_root = Path("/tmp/site")

    return PipelineConfig(
        config=config,
        output_dir=site_root / "output",
        site_root=site_root,
        docs_dir=site_root / "docs",
        posts_dir=site_root / "docs" / "posts",
        profiles_dir=site_root / "docs" / "profiles",
        media_dir=site_root / "docs" / "media",
    )


def test_with_output_format_updates_annotation_sink() -> None:
    annotations_store = MagicMock()
    annotations_store.output_sink = None

    state = PipelineState(
        run_id=uuid4(),
        start_time=datetime.now(timezone.utc),
        source_type="test",
        input_path=Path("/tmp/input.txt"),
        client=MagicMock(),
        storage=MagicMock(),
        cache=MagicMock(),
        annotations_store=annotations_store,
        task_store=None,
        library=None,
        output_format=None,
        adapter=None,
        usage_tracker=None,
        output_registry=None,
        embedding_router=None,
    )

    ctx = PipelineContext(_build_config(), state)
    output_format = MagicMock()

    ctx = ctx.with_output_format(output_format)

    assert ctx.output_format is output_format
    assert annotations_store.output_sink is output_format
