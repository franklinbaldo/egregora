"""Unit tests for the enrichment agent."""

import os
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from egregora.agents.enricher import EnrichmentWorker
from egregora.agents.exceptions import MediaStagingError


@pytest.fixture
def mock_context():
    """Provides a mock PipelineContext."""
    ctx = MagicMock()
    ctx.input_path = Path("/mock/archive.zip")
    ctx.site_root = Path("/mock/site")
    ctx.config.enrichment.max_concurrent_enrichments = 1
    ctx.config.quota.concurrency = 1
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
    with (
        patch("zipfile.ZipFile", return_value=mock_zip_file),
        patch.dict(os.environ, {"GOOGLE_API_KEY": "dummy"}),
    ):
        worker = EnrichmentWorker(ctx=mock_context)
        worker.zip_handle = mock_zip_file
        worker.media_index = {}  # Ensure media index is empty

        task = {"task_id": "task-123"}
        payload = {"filename": "non_existent_file.jpg", "original_filename": "non_existent_file.jpg"}

        with pytest.raises(MediaStagingError, match=r"Media file non_existent_file.jpg not found in ZIP"):
            worker.media_handler._stage_file(task, payload)
