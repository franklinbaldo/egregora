"""Unit tests for WhatsApp adapter utilities."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from egregora.input_adapters.whatsapp.exceptions import ChatFileNotFoundError
from egregora.input_adapters.whatsapp.utils import discover_chat_file


def test_discover_chat_file_raises_error_when_no_txt_file_found(tmp_path: Path):
    """It should raise ChatFileNotFoundError if no .txt file is in the zip."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("some_image.jpg", b"dummy content")

    with pytest.raises(ChatFileNotFoundError) as excinfo:
        discover_chat_file(zip_path)

    assert f"No WhatsApp chat file found in {zip_path}" in str(excinfo.value)
