"""Unit tests for egregora.utils.zip."""

import io
import zipfile
from unittest.mock import MagicMock

import pytest

from egregora.utils.zip import (
    ZipCompressionBombError,
    ZipMemberCountError,
    ZipMemberSizeError,
    ZipPathTraversalError,
    ZipTotalSizeError,
    ZipValidationError,
    ZipValidationSettings,
    configure_default_limits,
    ensure_safe_member_size,
    get_zip_info,
    validate_zip_contents,
)

# A small 1x1 transparent PNG for testing
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def create_test_zip(files: dict[str, bytes]) -> zipfile.ZipFile:
    """Creates an in-memory zip file for testing."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    # Re-open the zip file for reading
    zip_buffer.seek(0)
    return zipfile.ZipFile(zip_buffer, "r")


def test_validate_zip_contents_valid():
    """Test that a valid zip file passes validation."""
    zf = create_test_zip({"file1.txt": b"hello", "file2.png": TINY_PNG})
    try:
        validate_zip_contents(zf)
    except ZipValidationError:
        pytest.fail("validate_zip_contents raised ZipValidationError unexpectedly")


def test_validate_zip_member_count_exceeded():
    """Test that validation fails when member count is exceeded."""
    limits = ZipValidationSettings(max_member_count=2)
    files = {"file1.txt": b"1", "file2.txt": b"2", "file3.txt": b"3"}
    zf = create_test_zip(files)
    with pytest.raises(ZipMemberCountError) as excinfo:
        validate_zip_contents(zf, limits=limits)
    assert excinfo.value.member_count == 3
    assert excinfo.value.max_member_count == 2


def test_validate_zip_member_size_exceeded():
    """Test that validation fails when a member's size is exceeded."""
    limits = ZipValidationSettings(max_member_size=10)
    files = {"large_file.txt": b"This file is too large."}
    zf = create_test_zip(files)
    with pytest.raises(ZipMemberSizeError) as excinfo:
        validate_zip_contents(zf, limits=limits)
    assert excinfo.value.member_name == "large_file.txt"
    assert excinfo.value.member_size == 23
    assert excinfo.value.max_member_size == 10


def test_validate_zip_total_size_exceeded():
    """Test that validation fails when the total uncompressed size is exceeded."""
    limits = ZipValidationSettings(max_total_size=10)
    files = {"file1.txt": b"content1", "file2.txt": b"content2"}
    zf = create_test_zip(files)
    with pytest.raises(ZipTotalSizeError) as excinfo:
        validate_zip_contents(zf, limits=limits)
    assert excinfo.value.total_size == 16
    assert excinfo.value.max_total_size == 10


def test_validate_zip_compression_bomb():
    """Test that a potential zip bomb is detected."""
    limits = ZipValidationSettings(max_compression_ratio=5.0)
    mock_info = zipfile.ZipInfo("bomb.txt")
    mock_info.file_size = 1000
    mock_info.compress_size = 10
    mock_zip = MagicMock(spec=zipfile.ZipFile)
    mock_zip.infolist.return_value = [mock_info]
    with pytest.raises(ZipCompressionBombError) as excinfo:
        validate_zip_contents(mock_zip, limits=limits)
    assert excinfo.value.member_name == "bomb.txt"
    assert excinfo.value.ratio == 100.0
    assert excinfo.value.max_ratio == 5.0


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "C:\\Windows\\System32\\kernel32.dll",
        "../etc/hosts",
        "foo/../../bar",
    ],
)
def test_validate_zip_path_traversal(path):
    """Test that path traversal attempts are caught."""
    files = {path: b"evil"}
    zf = create_test_zip(files)
    with pytest.raises(ZipPathTraversalError) as excinfo:
        validate_zip_contents(zf)
    assert excinfo.value.member_name == path


def test_get_zip_info():
    """Test that zip member metadata is retrieved correctly."""
    # Mock zip file with one compressed member and one not
    mock_info1 = zipfile.ZipInfo("file1.txt")
    mock_info1.file_size = 100
    mock_info1.compress_size = 50

    mock_info2 = zipfile.ZipInfo("file2.txt")
    mock_info2.file_size = 200
    mock_info2.compress_size = 0  # Should result in a 1.0 ratio

    mock_zip = MagicMock(spec=zipfile.ZipFile)
    mock_zip.infolist.return_value = [mock_info1, mock_info2]

    info = get_zip_info(mock_zip)
    assert "file1.txt" in info
    assert info["file1.txt"]["file_size"] == 100
    assert info["file1.txt"]["compress_size"] == 50
    assert info["file1.txt"]["compression_ratio"] == 2.0

    assert "file2.txt" in info
    assert info["file2.txt"]["file_size"] == 200
    assert info["file2.txt"]["compress_size"] == 0
    assert info["file2.txt"]["compression_ratio"] == 1.0


def test_ensure_safe_member_size_valid():
    """Test that a member with a valid size passes the check."""
    limits = ZipValidationSettings(max_member_size=100)
    mock_info = zipfile.ZipInfo("safe_file.txt")
    mock_info.file_size = 50

    mock_zip = MagicMock(spec=zipfile.ZipFile)
    mock_zip.getinfo.return_value = mock_info

    try:
        ensure_safe_member_size(mock_zip, "safe_file.txt", limits=limits)
    except ZipMemberSizeError:
        pytest.fail("ensure_safe_member_size raised ZipMemberSizeError unexpectedly")


def test_ensure_safe_member_size_exceeded():
    """Test that a member exceeding the size limit raises an exception."""
    limits = ZipValidationSettings(max_member_size=100)
    mock_info = zipfile.ZipInfo("large_file.txt")
    mock_info.file_size = 200

    mock_zip = MagicMock(spec=zipfile.ZipFile)
    mock_zip.getinfo.return_value = mock_info

    with pytest.raises(ZipMemberSizeError) as excinfo:
        ensure_safe_member_size(mock_zip, "large_file.txt", limits=limits)

    assert excinfo.value.member_name == "large_file.txt"
    assert excinfo.value.member_size == 200
    assert excinfo.value.max_member_size == 100


def test_configure_default_limits():
    """Test that default validation limits can be reconfigured."""
    # Create new default limits
    new_defaults = ZipValidationSettings(max_member_count=1)
    configure_default_limits(new_defaults)

    # Create a zip with 2 members, which should fail with the new defaults
    files = {"file1.txt": b"1", "file2.txt": b"2"}
    zf = create_test_zip(files)

    with pytest.raises(ZipMemberCountError) as excinfo:
        # Call validation without explicit limits to use the new defaults
        validate_zip_contents(zf)

    assert excinfo.value.member_count == 2
    assert excinfo.value.max_member_count == 1

    # Restore original defaults to avoid affecting other tests
    configure_default_limits(ZipValidationSettings())
