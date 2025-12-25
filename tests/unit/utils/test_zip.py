"""Tests for zip validation utilities."""
from __future__ import annotations

import io
import zipfile
from typing import List

import pytest

from egregora.utils.zip import ZipValidationError, validate_zip_contents


def create_in_memory_zip(filenames: List[str]) -> zipfile.ZipFile:
    """Creates an in-memory zip file with the given filenames."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for filename in filenames:
            zf.writestr(filename, "dummy content")
    # After writing, position the buffer at the beginning for reading
    zip_buffer.seek(0)
    return zipfile.ZipFile(zip_buffer, "r")


@pytest.mark.parametrize(
    "malicious_filename",
    [
        "/etc/passwd",  # Absolute path
        "../../etc/passwd",  # Path traversal
        "../..",  # Path traversal
        "C:\\Users\\admin\\secrets.txt",  # Drive prefix
        "//server/share/file.txt",  # UNC Path, which is absolute
    ],
)
def test_validate_zip_contents_raises_on_unsafe_paths(malicious_filename):
    """Verify that validate_zip_contents rejects unsafe member paths."""
    zf = create_in_memory_zip([malicious_filename])
    with pytest.raises(ZipValidationError):
        validate_zip_contents(zf)


def test_validate_zip_contents_accepts_safe_paths():
    """Verify that validate_zip_contents accepts safe, relative member paths."""
    safe_filenames = [
        "chat.txt",
        "media/image.jpg",
        "data/archive/file.zip",
        "another-safe-file.bin",
    ]
    zf = create_in_memory_zip(safe_filenames)
    # No exception is expected. Pytest will fail the test if any is raised.
    validate_zip_contents(zf)
