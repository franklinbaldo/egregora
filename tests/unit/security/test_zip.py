import pytest
import zipfile
from unittest.mock import Mock, MagicMock, patch
from egregora.security.zip import (
    validate_zip_contents,
    ensure_safe_member_size,
    get_zip_info,
    configure_default_limits,
    ZipValidationSettings,
    ZipMemberCountError,
    ZipMemberSizeError,
    ZipTotalSizeError,
    ZipCompressionBombError,
    ZipPathTraversalError,
)

@pytest.fixture
def mock_zip_file():
    zf = MagicMock(spec=zipfile.ZipFile)
    return zf

@pytest.fixture
def default_limits():
    return ZipValidationSettings()

@pytest.fixture(autouse=True)
def reset_zip_config():
    """Reset global zip config after each test."""
    original = ZipValidationSettings()
    configure_default_limits(original)
    yield
    configure_default_limits(original)

def create_zip_info(filename, file_size, compress_size=None):
    info = zipfile.ZipInfo(filename)
    info.file_size = file_size
    info.compress_size = compress_size if compress_size is not None else file_size
    return info

class TestValidateZipContents:
    def test_valid_zip(self, mock_zip_file, default_limits):
        """Test that a valid zip file passes validation."""
        # Given
        members = [
            create_zip_info("file1.txt", 100),
            create_zip_info("dir/file2.txt", 200),
        ]
        mock_zip_file.infolist.return_value = members

        # When
        validate_zip_contents(mock_zip_file, limits=default_limits)

        # Then (no exception raised)

    def test_member_count_limit(self, mock_zip_file):
        """Test that validation fails if member count exceeds limit."""
        # Given
        limits = ZipValidationSettings(max_member_count=2)
        members = [
            create_zip_info("file1.txt", 100),
            create_zip_info("file2.txt", 100),
            create_zip_info("file3.txt", 100),
        ]
        mock_zip_file.infolist.return_value = members

        # When / Then
        with pytest.raises(ZipMemberCountError) as exc:
            validate_zip_contents(mock_zip_file, limits=limits)
        assert "3 > 2" in str(exc.value)

    def test_member_size_limit(self, mock_zip_file):
        """Test that validation fails if a member exceeds size limit."""
        # Given
        limits = ZipValidationSettings(max_member_size=100)
        members = [
            create_zip_info("file1.txt", 50),
            create_zip_info("huge_file.txt", 150),
        ]
        mock_zip_file.infolist.return_value = members

        # When / Then
        with pytest.raises(ZipMemberSizeError) as exc:
            validate_zip_contents(mock_zip_file, limits=limits)
        assert "huge_file.txt" in str(exc.value)
        assert "150 bytes" in str(exc.value)

    def test_total_size_limit(self, mock_zip_file):
        """Test that validation fails if total uncompressed size exceeds limit."""
        # Given
        limits = ZipValidationSettings(max_total_size=200)
        members = [
            create_zip_info("file1.txt", 100),
            create_zip_info("file2.txt", 101),
        ]
        mock_zip_file.infolist.return_value = members

        # When / Then
        with pytest.raises(ZipTotalSizeError) as exc:
            validate_zip_contents(mock_zip_file, limits=limits)
        assert "201 bytes" in str(exc.value)

    def test_compression_bomb(self, mock_zip_file):
        """Test that validation detects compression bombs."""
        # Given
        limits = ZipValidationSettings(max_compression_ratio=10.0)
        # 1000 bytes compressed to 10 bytes -> ratio 100
        members = [
            create_zip_info("bomb.txt", 1000, compress_size=10),
        ]
        mock_zip_file.infolist.return_value = members

        # When / Then
        with pytest.raises(ZipCompressionBombError) as exc:
            validate_zip_contents(mock_zip_file, limits=limits)
        assert "suspicious compression ratio" in str(exc.value)

    @pytest.mark.parametrize("unsafe_path", [
        "/absolute/path.txt",
        "../traversal.txt",
        "nested/../../traversal.txt",
        "C:\\Windows\\System32.dll",  # Windows absolute path simulation
        "dir\\..\\file.txt",          # Windows traversal simulation
    ])
    def test_path_traversal(self, mock_zip_file, unsafe_path, default_limits):
        """Test that validation rejects unsafe paths."""
        # Given
        members = [
            create_zip_info(unsafe_path, 100),
        ]
        mock_zip_file.infolist.return_value = members

        # When / Then
        with pytest.raises(ZipPathTraversalError) as exc:
            validate_zip_contents(mock_zip_file, limits=default_limits)
        assert f"ZIP member path is unsafe: '{unsafe_path}'" in str(exc.value)

class TestEnsureSafeMemberSize:
    def test_safe_member(self, mock_zip_file, default_limits):
        """Test safe member check passes."""
        # Given
        mock_zip_file.getinfo.return_value = create_zip_info("safe.txt", 100)

        # When
        ensure_safe_member_size(mock_zip_file, "safe.txt", limits=default_limits)

        # Then (no raise)

    def test_unsafe_member(self, mock_zip_file):
        """Test safe member check fails for large file."""
        # Given
        limits = ZipValidationSettings(max_member_size=100)
        mock_zip_file.getinfo.return_value = create_zip_info("huge.txt", 200)

        # When / Then
        with pytest.raises(ZipMemberSizeError):
            ensure_safe_member_size(mock_zip_file, "huge.txt", limits=limits)

class TestZipHelpers:
    def test_get_zip_info(self, mock_zip_file):
        """Test retrieving zip metadata."""
        # Given
        members = [
            create_zip_info("file1.txt", 100, compress_size=50),
            create_zip_info("file2.txt", 200, compress_size=20),
        ]
        mock_zip_file.infolist.return_value = members

        # When
        info = get_zip_info(mock_zip_file)

        # Then
        assert info["file1.txt"]["file_size"] == 100
        assert info["file1.txt"]["compress_size"] == 50
        assert info["file1.txt"]["compression_ratio"] == 2.0

        assert info["file2.txt"]["file_size"] == 200
        assert info["file2.txt"]["compression_ratio"] == 10.0

    def test_configure_default_limits(self):
        """Test configuring default limits."""
        # Given
        new_limits = ZipValidationSettings(max_member_size=999)

        # When
        configure_default_limits(new_limits)

        # Then - verify by checking behavior dependent on defaults
        # Assuming defaults are used by validation if not provided
        # Accessing the private _ZipConfig would be an implementation test
        # So we verify behavior.

        mock_zf = MagicMock(spec=zipfile.ZipFile)
        mock_zf.infolist.return_value = [create_zip_info("file.txt", 1000)]
        mock_zf.getinfo.return_value = create_zip_info("file.txt", 1000)

        # Should fail with new limit (default was ~50MB)
        with pytest.raises(ZipMemberSizeError):
             ensure_safe_member_size(mock_zf, "file.txt")
