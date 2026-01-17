import io
import zipfile
import pytest
from egregora.security.zip import (
    ZipValidationError,
    ZipMemberCountError,
    ZipMemberSizeError,
    ZipTotalSizeError,
    ZipCompressionBombError,
    ZipPathTraversalError,
    ZipValidationSettings,
    configure_default_limits,
    ensure_safe_member_size,
    get_zip_info,
    validate_zip_contents,
)

@pytest.fixture
def create_zip_bytes():
    def _create(files: dict[str, bytes]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, content in files.items():
                zf.writestr(name, content)
        return buffer.getvalue()
    return _create

class TestZipValidation:

    def test_validate_zip_valid(self, create_zip_bytes):
        """Given a valid zip file, it should pass validation."""
        data = create_zip_bytes({"file1.txt": b"content", "file2.txt": b"more content"})
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            validate_zip_contents(zf)

    def test_validate_zip_too_many_members(self, create_zip_bytes):
        """Given a zip with too many members, it should raise ZipMemberCountError."""
        limits = ZipValidationSettings(max_member_count=1)
        data = create_zip_bytes({"file1.txt": b"a", "file2.txt": b"b"})
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            with pytest.raises(ZipMemberCountError) as exc:
                validate_zip_contents(zf, limits=limits)
            assert "ZIP archive contains too many files" in str(exc.value)

    def test_validate_zip_member_too_large(self, create_zip_bytes):
        """Given a zip with a member exceeding max size, it should raise ZipMemberSizeError."""
        limits = ZipValidationSettings(max_member_size=5)
        data = create_zip_bytes({"large.txt": b"123456"})
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            with pytest.raises(ZipMemberSizeError) as exc:
                validate_zip_contents(zf, limits=limits)
            assert "exceeds maximum size" in str(exc.value)

    def test_validate_zip_total_size_too_large(self, create_zip_bytes):
        """Given a zip with total size exceeding limit, it should raise ZipTotalSizeError."""
        limits = ZipValidationSettings(max_total_size=5)
        data = create_zip_bytes({"f1.txt": b"123", "f2.txt": b"456"})
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            with pytest.raises(ZipTotalSizeError) as exc:
                validate_zip_contents(zf, limits=limits)
            assert "exceeds" in str(exc.value)

    def test_validate_zip_compression_bomb(self, create_zip_bytes):
        """Given a zip with high compression ratio, it should raise ZipCompressionBombError."""
        # Create a highly compressible content
        content = b"a" * 1000
        data = create_zip_bytes({"bomb.txt": content})

        # Set a very low ratio limit
        limits = ZipValidationSettings(max_compression_ratio=1.1)

        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            with pytest.raises(ZipCompressionBombError) as exc:
                validate_zip_contents(zf, limits=limits)
            assert "suspicious compression ratio" in str(exc.value)

    @pytest.mark.parametrize("unsafe_path", [
        "../secret.txt",
        "subdir/../../etc/passwd",
        "/absolute/path",
        "C:\\Windows\\System32",
    ])
    def test_validate_zip_path_traversal(self, unsafe_path):
        """Given a zip with unsafe paths, it should raise ZipPathTraversalError."""
        # We need to manually construct zip with unsafe paths as writestr might sanitize or warn
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
             # writestr allows any name
            zf.writestr(unsafe_path, b"content")

        data = buffer.getvalue()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            with pytest.raises(ZipPathTraversalError) as exc:
                validate_zip_contents(zf)
            assert "unsafe" in str(exc.value)

    def test_ensure_safe_member_size(self, create_zip_bytes):
        """Given a specific member to check, it should validate its size."""
        limits = ZipValidationSettings(max_member_size=10)
        data = create_zip_bytes({"ok.txt": b"small", "big.txt": b"too big content"})

        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            ensure_safe_member_size(zf, "ok.txt", limits=limits)

            with pytest.raises(ZipMemberSizeError):
                ensure_safe_member_size(zf, "big.txt", limits=limits)

    def test_get_zip_info(self, create_zip_bytes):
        """Given a zip file, it should return correct metadata."""
        content = b"a" * 100
        data = create_zip_bytes({"test.txt": content})

        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            info = get_zip_info(zf)
            assert "test.txt" in info
            assert info["test.txt"]["file_size"] == 100
            assert info["test.txt"]["compress_size"] < 100
            assert info["test.txt"]["compression_ratio"] > 1.0

    def test_configure_default_limits(self):
        """Given a new default configuration, it should be applied."""
        new_limits = ZipValidationSettings(max_member_count=1)
        configure_default_limits(new_limits)

        # Now validate with default limits should use new limits
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("f1.txt", b"a")
            zf.writestr("f2.txt", b"b")

        with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as zf:
             with pytest.raises(ZipMemberCountError):
                 validate_zip_contents(zf) # Uses configured defaults

        # Reset defaults to avoid side effects
        configure_default_limits(ZipValidationSettings())
