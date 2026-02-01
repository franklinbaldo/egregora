import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from egregora.agents.enricher import EnrichmentOutput, EnrichmentRuntimeContext, EnrichmentWorker
from egregora.data_primitives.document import DocumentType


@pytest.fixture
def mock_context():
    # EnrichmentWorker.__init__ expects self.ctx.input_path
    ctx = MagicMock(spec=EnrichmentRuntimeContext)
    ctx.output_sink = MagicMock()
    ctx.cache = MagicMock()
    ctx.library = None
    ctx.input_path = None  # Set to None to skip ZIP initialization in __init__
    return ctx


@pytest.fixture
def worker(mock_context):
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "dummy"}):
        return EnrichmentWorker(ctx=mock_context)


def test_persist_media_results_uses_slug_for_filename(worker, mock_context, mocker):
    """
    Test that _persist_media_results correctly uses the slug
    provided by the LLM to construct the final filename and suggested_path.
    """
    # Setup test data
    payload = {
        "filename": "original_image.jpg",
        "original_filename": "original_image.jpg",
        "media_type": "image",
        "message_metadata": {"id": "msg-1"},
    }
    slug_value = "cool-new-slug"
    markdown = "# Enriched Content"

    # Mock _parse_media_result to return our test data
    output = EnrichmentOutput(slug=slug_value, markdown=markdown)
    mocker.patch.object(worker, "_parse_media_result", return_value=(payload, output))
    # Mock _stage_file to avoid real IO
    mocker.patch.object(worker, "_stage_file", return_value=Path("/tmp/fake.jpg"))
    # Mock task_store
    mock_context.task_store = MagicMock()
    # Mock storage for SQL update
    mock_context.storage = MagicMock()

    # Result object with 'tag' attribute
    res = SimpleNamespace(tag="tag-1", error=None)

    # Task metadata for persistence tracking
    task = {
        "task_id": "task-123",
        "payload": payload,
        "_staged_path": "/tmp/fake.jpg",
    }
    task_map = {"tag-1": task}

    # We call the internal method
    worker._persist_media_results([res], task_map)

    # Verify persistence call
    assert mock_context.output_sink.persist.called

    # Inspect the document passed to persist
    publish_calls = mock_context.output_sink.persist.call_args_list

    # We expect two calls: one for the media file itself, one for the enrichment description
    assert len(publish_calls) >= 2

    # Find the media document (type MEDIA)
    media_doc = next(call.args[0] for call in publish_calls if call.args[0].type == DocumentType.MEDIA)

    # ASSERTIONS (This should fail initially on suggested_path and subdirectory logic)
    # 1. Filename in metadata should be slug-based
    assert media_doc.metadata["filename"] == "cool-new-slug.jpg"

    # 2. suggested_path should include the subfolder and slug-based name
    # DESIRED: media/images/cool-new-slug.jpg
    # CURRENT: None (or some default if not set)
    assert media_doc.suggested_path == "media/images/cool-new-slug.jpg"

    # 3. Verify enrichment doc also has correct references
    enrich_doc = next(
        call.args[0] for call in publish_calls if call.args[0].type == DocumentType.ENRICHMENT_IMAGE
    )
    assert enrich_doc.metadata["filename"] == "cool-new-slug.jpg"

    # DESIRED: parent_path should point to the media file's suggested path
    assert enrich_doc.metadata.get("parent_path") == "media/images/cool-new-slug.jpg"

    # 4. Verify subdirectory logic
    assert media_doc.metadata.get("media_subdir") == "images"
