import asyncio
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google import genai

from egregora.cli import EgregoraCLI
from egregora.pipeline import process_whatsapp_export


@pytest.fixture
def mock_genai_client():
    """Fixture to mock the genai.Client and its methods."""
    with patch("google.genai.Client", autospec=True) as mock_client_constructor:
        mock_client_instance = MagicMock()
        mock_client_instance.close = MagicMock()
        mock_client_constructor.return_value = mock_client_instance
        yield mock_client_constructor


@pytest.fixture
def empty_zip_path(tmp_path: Path) -> Path:
    """Create a valid, empty zip file."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("dummy.txt", "dummy content")
    return zip_path


@pytest.mark.asyncio
async def test_process_whatsapp_export_with_api_key(mock_genai_client, empty_zip_path, tmp_path):
    """Verify client is initialized with API key when provided."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with patch("egregora.pipeline.discover_chat_file", return_value=("TestGroup", "chat.txt")):
        # Mock the rest of the pipeline to isolate the client initialization
        with patch("egregora.pipeline.parse_export", return_value=MagicMock()), \
             patch("egregora.pipeline.extract_commands", return_value=[]), \
             patch("egregora.pipeline.filter_egregora_messages", return_value=(MagicMock(), 0)), \
             patch("egregora.pipeline.filter_opted_out_authors", return_value=(MagicMock(), 0)), \
             patch("egregora.pipeline.group_by_period", return_value={}):
            await process_whatsapp_export(empty_zip_path, output_dir, gemini_api_key="test_key")
            mock_genai_client.assert_called_once_with(api_key="test_key")


@pytest.mark.asyncio
async def test_process_whatsapp_export_without_api_key(mock_genai_client, empty_zip_path, tmp_path):
    """Verify client is initialized without api_key to allow ADC fallback."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with patch("egregora.pipeline.discover_chat_file", return_value=("TestGroup", "chat.txt")):
        # Mock the rest of the pipeline
        with patch("egregora.pipeline.parse_export", return_value=MagicMock()), \
             patch("egregora.pipeline.extract_commands", return_value=[]), \
             patch("egregora.pipeline.filter_egregora_messages", return_value=(MagicMock(), 0)), \
             patch("egregora.pipeline.filter_opted_out_authors", return_value=(MagicMock(), 0)), \
             patch("egregora.pipeline.group_by_period", return_value={}):
            await process_whatsapp_export(empty_zip_path, output_dir, gemini_api_key=None)
            mock_genai_client.assert_called_once_with()


def test_edit_post_with_api_key(mock_genai_client, tmp_path, monkeypatch):
    """Verify client is initialized with API key for edit_post."""
    post_file = tmp_path / "post.md"
    post_file.write_text("test content")
    site_dir = tmp_path
    (site_dir / "docs").mkdir()

    monkeypatch.setenv("GEMINI_API_KEY", "test_key_env")

    cli = EgregoraCLI()

    mock_result = MagicMock()
    mock_result.final_content = "edited content"

    with patch("egregora.cli.run_editor_session", new_callable=AsyncMock) as mock_editor:
        mock_editor.return_value = mock_result
        cli.edit_post(str(post_file), str(site_dir))
        mock_genai_client.assert_called_once_with(api_key="test_key_env")


def test_edit_post_without_api_key(mock_genai_client, tmp_path, monkeypatch):
    """Verify client is initialized without api_key for edit_post."""
    post_file = tmp_path / "post.md"
    post_file.write_text("test content")
    site_dir = tmp_path
    (site_dir / "docs").mkdir()

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    cli = EgregoraCLI()

    mock_result = MagicMock()
    mock_result.final_content = "edited content"

    with patch("egregora.cli.run_editor_session", new_callable=AsyncMock) as mock_editor:
        with patch("egregora.cli.os.getenv", return_value=None):
            mock_editor.return_value = mock_result
            cli.edit_post(str(post_file), str(site_dir))
            mock_genai_client.assert_called_once_with()