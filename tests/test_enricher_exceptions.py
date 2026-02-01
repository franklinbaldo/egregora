"""Test for file staging exceptions in the EnrichmentWorker."""

import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from egregora.agents.enricher import EnrichmentWorker
from egregora.agents.exceptions import MediaStagingError


class MockPipelineContext:
    """Mock context for testing."""

    def __init__(self, input_path=None):
        self.config = Mock()
        self.config.enrichment.rotation_models = ["gemini-pro"]
        self.config.enrichment.strategy = "individual"
        self.task_store = Mock()
        self.storage = Mock()
        self.input_path = input_path
        self.output_dir = Path("/tmp/test")
        self.site_root = Path("/tmp/test-site")


def test_stage_file_raises_error_if_no_filename():
    """Verify MediaStagingError is raised if the task payload is missing a filename."""
    ctx = MockPipelineContext()
    worker = EnrichmentWorker(ctx)
    task = {"task_id": "test_task"}
    payload = {"original_filename": None, "filename": None}
    with pytest.raises(MediaStagingError, match="No filename in task payload"):
        worker._stage_file(task, payload)


def test_stage_file_raises_error_if_zip_not_found():
    """Verify MediaStagingError is raised if the input_path (zip file) is not available."""
    ctx = MockPipelineContext(input_path=Path("/non/existent/file.zip"))
    worker = EnrichmentWorker(ctx)
    task = {"task_id": "test_task"}
    payload = {"original_filename": "test.jpg", "filename": "test.jpg"}
    with pytest.raises(MediaStagingError, match="Input path not available"):
        worker._stage_file(task, payload)


def test_stage_file_raises_error_if_media_not_in_zip():
    """Verify MediaStagingError is raised if the media file is not found in the zip archive."""
    # Create a dummy zip file for testing
    zip_path = Path("/tmp/test.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("info.txt", "this is a test zip file")

    ctx = MockPipelineContext(input_path=zip_path)
    worker = EnrichmentWorker(ctx)
    task = {"task_id": "test_task"}
    payload = {"original_filename": "non_existent.jpg", "filename": "non_existent.jpg"}

    with pytest.raises(MediaStagingError, match="not found in ZIP"):
        worker._stage_file(task, payload)

    # Clean up the dummy zip file
    zip_path.unlink()
