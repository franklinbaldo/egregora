"""Tests for the media enrichment functionality of the EnrichmentWorker."""

import json
import os
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions as google_exceptions

from egregora.agents.enricher import EnrichmentWorker


class MockPipelineContext:
    """A mock pipeline context for testing the EnrichmentWorker."""

    def __init__(self, strategy="batch_all", site_root_path="/tmp/test-site", input_path=None):
        """Initializes the mock context with a configurable strategy and site root."""
        self.config = MagicMock()
        self.config.enrichment.strategy = strategy
        self.config.enrichment.max_concurrent_enrichments = 5
        self.config.quota.concurrency = 5
        self.config.models.enricher_vision = "gemini-pro-vision"
        self.config.privacy.pii_prevention = None
        self.config.models.enricher = "gemini-pro"

        self.task_store = MagicMock()
        self.storage = MagicMock()
        self.input_path = input_path
        self.output_dir = Path("/tmp/test")
        self.site_root = Path(site_root_path)
        self.library = None


def create_media_tasks(count: int) -> list[dict]:
    """Creates a list of mock media enrichment tasks."""
    return [
        {
            "task_id": f"media-task-{i}",
            "task_type": "enrich_media",
            "payload": json.dumps(
                {
                    "type": "media",
                    "filename": f"image-{i}.jpg",
                    "media_type": "image/jpeg",
                    "original_filename": f"image-{i}.jpg",
                }
            ),
            "status": "pending",
        }
        for i in range(count)
    ]


@pytest.fixture
def mock_context_and_worker():
    """Provides a mocked context and an EnrichmentWorker instance for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        zip_path = temp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for i in range(3):
                zf.writestr(f"image-{i}.jpg", b"dummy image data")

        context = MockPipelineContext(site_root_path=str(temp_path), input_path=zip_path)
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "dummy"}):
            worker = EnrichmentWorker(context)
        yield context, worker
        worker.close()


def test_media_enrichment_fallback_on_api_error(mock_context_and_worker, monkeypatch):
    """
    Tests that the media enrichment process correctly falls back to the standard batch
    when the single-call batch method fails with a specific Google API error.
    """
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    _context, worker = mock_context_and_worker
    tasks = create_media_tasks(3)

    with patch(
        "egregora.agents.enricher.EnrichmentWorker._prepare_media_content",
        return_value={"inlineData": {"mimeType": "image/jpeg", "data": "test"}},
    ):
        requests, task_map = worker._prepare_media_requests(tasks)

    assert requests, "Requests should have been prepared"

    with (
        patch.object(
            worker,
            "_execute_media_single_call",
            side_effect=google_exceptions.GoogleAPICallError("API error"),
        ) as mock_single_call,
        patch("egregora.agents.enricher.GoogleBatchModel.run_batch", return_value=[]) as mock_run_batch,
    ):
        worker._execute_media_batch(requests, task_map)

        mock_single_call.assert_called_once()
        mock_run_batch.assert_called_once()


def test_media_enrichment_propagates_unexpected_errors(mock_context_and_worker, monkeypatch):
    """
    Tests that unexpected errors during single-call batch are not caught
    by the generic fallback and are instead propagated. This test will fail
    before the refactoring and pass after.
    """
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    _context, worker = mock_context_and_worker
    tasks = create_media_tasks(3)

    with patch(
        "egregora.agents.enricher.EnrichmentWorker._prepare_media_content",
        return_value={"inlineData": {"mimeType": "image/jpeg", "data": "test"}},
    ):
        requests, task_map = worker._prepare_media_requests(tasks)

    assert requests

    with patch.object(
        worker, "_execute_media_single_call", side_effect=ValueError("Unexpected error")
    ) as mock_single_call:
        with pytest.raises(ValueError, match="Unexpected error"):
            worker._execute_media_batch(requests, task_map)

        mock_single_call.assert_called_once()
