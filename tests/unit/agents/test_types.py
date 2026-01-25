from unittest.mock import MagicMock

import pytest

from egregora.agents.types import WriterResources
from egregora.orchestration.context import PipelineContext


def test_writer_resources_from_context(tmp_path):
    """Test creating WriterResources from PipelineContext."""
    mock_ctx = MagicMock(spec=PipelineContext)
    mock_ctx.output_sink = MagicMock()
    # Mocking attributes that are accessed via getattr default or directly
    # The code: getattr(output, "profiles_dir", ctx.profiles_dir)
    # Let's ensure output sink has profiles_dir
    mock_ctx.output_sink.profiles_dir = tmp_path / "profiles"
    mock_ctx.output_sink.journal_dir = tmp_path / "journal"

    mock_ctx.docs_dir = tmp_path / "docs"
    mock_ctx.site_root = tmp_path

    mock_ctx.output_registry = MagicMock()
    mock_ctx.annotations_store = MagicMock()
    mock_ctx.storage = MagicMock()
    mock_ctx.embedding_model = "test-embed"
    mock_ctx.config = MagicMock()
    mock_ctx.config.rag = MagicMock()
    mock_ctx.client = MagicMock()
    mock_ctx.usage_tracker = MagicMock()

    resources = WriterResources.from_pipeline_context(mock_ctx)

    assert resources.output is mock_ctx.output_sink
    assert resources.embedding_model == "test-embed"
    assert resources.retrieval_config is mock_ctx.config.rag
    assert resources.prompts_dir == tmp_path / ".egregora" / "prompts"
    assert resources.prompts_dir.exists()
    assert (tmp_path / "profiles").exists()
    assert (tmp_path / "journal").exists()


def test_writer_resources_raises_if_no_output_sink():
    mock_ctx = MagicMock(spec=PipelineContext)
    mock_ctx.output_sink = None

    with pytest.raises(RuntimeError, match="Output adapter must be initialized"):
        WriterResources.from_pipeline_context(mock_ctx)


def test_writer_resources_creation_without_site_root(tmp_path):
    """Test fallback when site_root is None."""
    mock_ctx = MagicMock(spec=PipelineContext)
    mock_ctx.output_sink = MagicMock()
    mock_ctx.output_sink.profiles_dir = tmp_path / "profiles"
    # journal_dir not on sink, fallback to ctx.docs_dir / journal
    del mock_ctx.output_sink.journal_dir
    mock_ctx.docs_dir = tmp_path / "docs"
    mock_ctx.site_root = None  # No site root

    # Other required mocks
    mock_ctx.output_registry = MagicMock()
    mock_ctx.annotations_store = MagicMock()
    mock_ctx.storage = MagicMock()
    mock_ctx.embedding_model = "test-embed"
    mock_ctx.config = MagicMock()
    mock_ctx.config.rag = MagicMock()
    mock_ctx.client = MagicMock()
    mock_ctx.usage_tracker = MagicMock()

    resources = WriterResources.from_pipeline_context(mock_ctx)

    assert resources.prompts_dir is None
    assert resources.journal_dir == tmp_path / "docs" / "journal"
    assert resources.journal_dir.exists()
