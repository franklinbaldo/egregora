import zipfile
from unittest.mock import MagicMock

import pytest

from egregora.security.zip import (
    ZipCompressionBombError,
    ZipMemberCountError,
    ZipMemberSizeError,
    ZipPathTraversalError,
    ZipTotalSizeError,
    ZipValidationSettings,
    configure_default_limits,
    ensure_safe_member_size,
    get_zip_info,
    validate_zip_contents,
)


class TestZipSecurity:
    @pytest.fixture
    def mock_zip_file(self):
        return MagicMock(spec=zipfile.ZipFile)

    @pytest.fixture
    def default_limits(self):
        return ZipValidationSettings()

    def create_mock_info(self, filename="test.txt", file_size=100, compress_size=50):
        info = MagicMock(spec=zipfile.ZipInfo)
        info.filename = filename
        info.file_size = file_size
        info.compress_size = compress_size
        return info

    def test_validate_zip_contents_valid(self, mock_zip_file, default_limits):
        """Test validation passes for a normal safe zip file."""
        mock_zip_file.infolist.return_value = [
            self.create_mock_info("file1.txt", 1000, 500),
            self.create_mock_info("dir/file2.txt", 2000, 1000),
        ]

        # Should not raise
        validate_zip_contents(mock_zip_file, limits=default_limits)

    def test_validate_zip_contents_too_many_members(self, mock_zip_file):
        """Test error when zip has too many members."""
        limits = ZipValidationSettings(max_member_count=2)
        mock_zip_file.infolist.return_value = [self.create_mock_info(f"file{i}.txt") for i in range(3)]

        with pytest.raises(ZipMemberCountError) as excinfo:
            validate_zip_contents(mock_zip_file, limits=limits)
        assert "contains too many files" in str(excinfo.value)
        assert excinfo.value.member_count == 3
        assert excinfo.value.max_member_count == 2

    def test_validate_zip_contents_member_too_large(self, mock_zip_file):
        """Test error when a single member is too large."""
        limits = ZipValidationSettings(max_member_size=100)
        mock_zip_file.infolist.return_value = [self.create_mock_info("huge.txt", file_size=150)]

        with pytest.raises(ZipMemberSizeError) as excinfo:
            validate_zip_contents(mock_zip_file, limits=limits)
        assert "exceeds maximum size" in str(excinfo.value)
        assert excinfo.value.member_size == 150

    def test_validate_zip_contents_total_too_large(self, mock_zip_file):
        """Test error when total uncompressed size is too large."""
        limits = ZipValidationSettings(max_total_size=200)
        mock_zip_file.infolist.return_value = [
            self.create_mock_info("file1.txt", 150),
            self.create_mock_info("file2.txt", 100),  # Total 250 > 200
        ]

        with pytest.raises(ZipTotalSizeError) as excinfo:
            validate_zip_contents(mock_zip_file, limits=limits)
        assert "uncompressed size" in str(excinfo.value)
        assert excinfo.value.total_size == 250

    def test_validate_zip_contents_compression_bomb(self, mock_zip_file):
        """Test error when compression ratio is too high."""
        limits = ZipValidationSettings(max_compression_ratio=10.0)
        # 1000 bytes uncompressed, 10 bytes compressed = 100:1 ratio
        mock_zip_file.infolist.return_value = [
            self.create_mock_info("bomb.txt", file_size=1000, compress_size=10)
        ]

        with pytest.raises(ZipCompressionBombError) as excinfo:
            validate_zip_contents(mock_zip_file, limits=limits)
        assert "suspicious compression ratio" in str(excinfo.value)
        assert excinfo.value.ratio == 100.0

    @pytest.mark.parametrize(
        "unsafe_path",
        [
            "/etc/passwd",
            "../secret.txt",
            "folder/../../outside.txt",
            "C:\\Windows",
            "\\\\Server\\Share",
            "D:file.txt",
        ],
    )
    def test_validate_zip_contents_path_traversal(self, mock_zip_file, unsafe_path, default_limits):
        """Test error for various unsafe paths."""
        mock_zip_file.infolist.return_value = [self.create_mock_info(unsafe_path)]

        with pytest.raises(ZipPathTraversalError) as excinfo:
            validate_zip_contents(mock_zip_file, limits=default_limits)
        assert "path is unsafe" in str(excinfo.value)
        assert excinfo.value.member_name == unsafe_path

    def test_ensure_safe_member_size(self, mock_zip_file):
        """Test single member size check."""
        limits = ZipValidationSettings(max_member_size=100)

        # Setup getinfo return value
        mock_zip_file.getinfo.return_value = self.create_mock_info("test.txt", file_size=50)

        # Should pass
        ensure_safe_member_size(mock_zip_file, "test.txt", limits=limits)

        # Should fail
        mock_zip_file.getinfo.return_value = self.create_mock_info("huge.txt", file_size=150)
        with pytest.raises(ZipMemberSizeError):
            ensure_safe_member_size(mock_zip_file, "huge.txt", limits=limits)

    def test_get_zip_info(self, mock_zip_file):
        """Test metadata extraction."""
        mock_zip_file.infolist.return_value = [
            self.create_mock_info("file1.txt", 100, 50),  # Ratio 2.0
            self.create_mock_info("empty.txt", 0, 0),  # Ratio 1.0 (default)
        ]

        info = get_zip_info(mock_zip_file)

        assert len(info) == 2
        assert info["file1.txt"]["file_size"] == 100
        assert info["file1.txt"]["compress_size"] == 50
        assert info["file1.txt"]["compression_ratio"] == 2.0

        assert info["empty.txt"]["file_size"] == 0
        assert info["empty.txt"]["compress_size"] == 0
        assert info["empty.txt"]["compression_ratio"] == 1.0

    def test_configure_default_limits(self, mock_zip_file):
        """Test updating global default limits."""
        # Save original defaults (implicit, but good practice if we could access them easily)
        # Here we rely on the fact that tests run sequentially or we mock where defaults are used.
        # But validate_zip_contents uses _ZipConfig.defaults.

        new_limits = ZipValidationSettings(max_member_count=5)
        configure_default_limits(new_limits)

        # Verify validate_zip_contents uses new defaults
        mock_zip_file.infolist.return_value = [self.create_mock_info(f"f{i}") for i in range(6)]

        try:
            with pytest.raises(ZipMemberCountError) as excinfo:
                # passing limits=None forces use of defaults
                validate_zip_contents(mock_zip_file, limits=None)
            assert excinfo.value.max_member_count == 5
        finally:
            # Cleanup: Restore sensible defaults or original
            configure_default_limits(ZipValidationSettings())

    def test_validate_zip_contents_zero_compression_size(self, mock_zip_file, default_limits):
        """Test valid file with zero compressed size (e.g. stored or empty) doesn't div by zero."""
        mock_zip_file.infolist.return_value = [
            # file_size > 0 but compress_size = 0 is technically weird for standard zip unless stored?
            # If method=STORED, compress_size usually == file_size.
            # If file is empty, both are 0.
            self.create_mock_info("empty.txt", file_size=0, compress_size=0)
        ]
        validate_zip_contents(mock_zip_file, limits=default_limits)

        # Case where file_size > 0 and compress_size = 0 (should not happen in valid zip usually, but check logic)
        # Logic: if info.compress_size > 0 and info.file_size > 0: check ratio
        mock_zip_file.infolist.return_value = [
            self.create_mock_info("odd.txt", file_size=100, compress_size=0)
        ]
        validate_zip_contents(mock_zip_file, limits=default_limits)
