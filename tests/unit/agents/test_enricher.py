"""Unit tests for the enrichment agent."""

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from egregora.agents.enricher import EnrichmentWorker
from egregora.agents.exceptions import MediaStagingError


@pytest.fixture
def mock_context(minimal_config):
    """Provides a mock PipelineContext."""
    ctx = MagicMock()
    ctx.input_path = Path("/mock/archive.zip")
    ctx.site_root = Path("/mock/site")
    ctx.config = minimal_config
    return ctx


@pytest.fixture
def mock_zip_file():
    """Provides a mock zipfile.ZipFile instance."""
    zip_mock = MagicMock(spec=zipfile.ZipFile)
    zip_mock.infolist.return_value = []
    zip_mock.namelist.return_value = []
    return zip_mock


def test_stage_file_raises_error_when_file_not_in_zip(mock_context, mock_zip_file):
    """
    Verify that _stage_file raises MediaStagingError if the file is not in the zip.
    """
    with patch("zipfile.ZipFile", return_value=mock_zip_file):
        worker = EnrichmentWorker(ctx=mock_context)
        worker.zip_handle = mock_zip_file
        worker.media_index = {}  # Ensure media index is empty

        task = {"task_id": "task-123"}
        payload = {"filename": "non_existent_file.jpg", "original_filename": "non_existent_file.jpg"}

        with pytest.raises(MediaStagingError, match=r"Media file non_existent_file.jpg not found in ZIP"):
            worker._stage_file(task, payload)


def test_enrichment_worker_instantiates_and_closes(mock_context: MagicMock) -> None:
    """Ensures the EnrichmentWorker can be created and closed without error."""
    worker = None
    try:
        # We patch zipfile.ZipFile to avoid filesystem access during instantiation
        with patch("zipfile.ZipFile"):
            worker = EnrichmentWorker(ctx=mock_context)
            assert worker is not None, "Worker should be instantiated"
    finally:
        # Ensure cleanup is called regardless of assertion outcomes
        if worker:
            worker.close()
