"""End-to-end tests for the pipeline command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import zipfile

import pytest
from typer.testing import CliRunner

from egregora.__main__ import app

runner = CliRunner()


@pytest.fixture
def dummy_zip(tmp_path: Path) -> Path:
    """Creates a dummy ZIP file with a chat transcript."""
    zip_path = tmp_path / "whatsapp.zip"
    chat_content = """
13/10/2025 10:00 - User 1: Hello world!
13/10/2025 10:01 - User 2: This is a test.
"""
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("WhatsApp Chat with Egregora.txt", chat_content)
    return zip_path


@patch("egregora.embed.embed.get_embedding")
@patch("egregora.generate.core.PostGenerator.generate")
@patch("egregora.archive.main.upload")
def test_pipeline_command(
    mock_upload, mock_generate, mock_get_embedding, dummy_zip: Path
):
    """Tests the full pipeline command."""
    mock_get_embedding.return_value = [0.1] * 768
    mock_generate.return_value = "Generated post content."

    result = runner.invoke(
        app,
        ["pipeline", str(dummy_zip), "--archive"],
    )
    if result.exit_code != 0:
        print(result.output)
    assert result.exit_code == 0

    # Check that the output files were created
    assert Path("ingest.parquet").exists()
    assert Path("embeddings.parquet").exists()
    assert Path("posts").exists()

    # Check that the mocks were called
    mock_get_embedding.assert_called()
    mock_generate.assert_called()
    mock_upload.assert_called()
