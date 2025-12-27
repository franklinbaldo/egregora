"""Security helpers for validating WhatsApp ZIP exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    import zipfile
__all__ = [
    "ZipValidationError",
    "ZipValidationSettings",
    "configure_default_limits",
    "ensure_safe_member_size",
    "get_zip_info",
    "validate_zip_contents",
]


class ZipValidationError(ValueError):
    """Base exception for ZIP archive validation errors."""


class ZipMemberCountError(ZipValidationError):
    """Raised when a ZIP archive exceeds the maximum number of members."""

    def __init__(self, member_count: int, max_member_count: int) -> None:
        self.member_count = member_count
        self.max_member_count = max_member_count
        super().__init__(f"ZIP archive contains too many files ({member_count} > {max_member_count})")


class ZipMemberSizeError(ZipValidationError):
    """Raised when a member in a ZIP archive exceeds the maximum allowed size."""

    def __init__(self, member_name: str, member_size: int, max_member_size: int) -> None:
        self.member_name = member_name
        self.member_size = member_size
        self.max_member_size = max_member_size
        super().__init__(f"ZIP member '{member_name}' ({member_size} bytes) exceeds maximum size of {max_member_size} bytes")


class ZipTotalSizeError(ZipValidationError):
    """Raised when the total uncompressed size of a ZIP archive exceeds the maximum."""

    def __init__(self, total_size: int, max_total_size: int) -> None:
        self.total_size = total_size
        self.max_total_size = max_total_size
        super().__init__(f"ZIP archive uncompressed size ({total_size} bytes) exceeds {max_total_size} bytes")


class ZipCompressionBombError(ZipValidationError):
    """Raised when a ZIP member has a suspiciously high compression ratio."""

    def __init__(self, member_name: str, ratio: float, max_ratio: float) -> None:
        self.member_name = member_name
        self.ratio = ratio
        self.max_ratio = max_ratio
        super().__init__(
            f"ZIP member '{member_name}' has suspicious compression ratio "
            f"({self.ratio:.1f}:1 > {self.max_ratio}:1). This may indicate a zip bomb attack."
        )


class ZipPathTraversalError(ZipValidationError):
    """Raised when a ZIP member's path is unsafe (absolute or traversal)."""

    def __init__(self, member_name: str) -> None:
        self.member_name = member_name
        super().__init__(f"ZIP member path is unsafe: '{member_name}'")


@dataclass(frozen=True, slots=True)
class ZipValidationSettings:
    """Constraints applied when validating WhatsApp ZIP archives."""

    max_total_size: int = 500 * 1024 * 1024
    max_member_size: int = 50 * 1024 * 1024
    max_member_count: int = 2000
    max_compression_ratio: float = 100.0  # Detect zip bombs (100:1 ratio)


# Use a class-based container for configuration to avoid 'global'
class _ZipConfig:
    defaults: ZipValidationSettings = ZipValidationSettings()


def configure_default_limits(
    limits: Annotated[ZipValidationSettings, "The new default validation limits"],
) -> None:
    """Override module-wide validation limits."""
    _ZipConfig.defaults = limits


def get_zip_info(
    zf: Annotated[zipfile.ZipFile, "The ZIP file to inspect"],
) -> dict[str, dict[str, int | float]]:
    """Get detailed metadata for all members in a ZIP archive.

    Returns a dictionary mapping filenames to their metadata:
    - file_size: Uncompressed size in bytes
    - compress_size: Compressed size in bytes
    - compression_ratio: Ratio of uncompressed to compressed size

    This is useful for diagnostics and understanding ZIP structure.
    """
    info_dict = {}
    for info in zf.infolist():
        ratio = info.file_size / info.compress_size if info.compress_size > 0 else 1.0
        info_dict[info.filename] = {
            "file_size": info.file_size,
            "compress_size": info.compress_size,
            "compression_ratio": ratio,
        }
    return info_dict


def validate_zip_contents(
    zf: Annotated[zipfile.ZipFile, "The ZIP file to validate"],
    *,
    limits: Annotated[ZipValidationSettings | None, "Optional validation limits to use"] = None,
) -> None:
    """Validate members of a ZIP archive.

    Guards against zip bombs, resource exhaustion and path traversal by
    inspecting the metadata of each member before extraction.

    Checks performed:
    - Member count limit
    - Individual file size limit
    - Total uncompressed size limit
    - Compression ratio (zip bomb detection)
    - Path traversal prevention
    """
    limits = limits or _ZipConfig.defaults
    total_size = 0
    members = zf.infolist()
    if len(members) > limits.max_member_count:
        raise ZipMemberCountError(len(members), limits.max_member_count)

    for info in members:
        _ensure_safe_path(info.filename)
        if info.file_size > limits.max_member_size:
            raise ZipMemberSizeError(info.filename, info.file_size, limits.max_member_size)

        # Check compression ratio to detect zip bombs
        if info.compress_size > 0 and info.file_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > limits.max_compression_ratio:
                raise ZipCompressionBombError(info.filename, ratio, limits.max_compression_ratio)

        total_size += info.file_size
        if total_size > limits.max_total_size:
            raise ZipTotalSizeError(total_size, limits.max_total_size)


def ensure_safe_member_size(
    zf: Annotated[zipfile.ZipFile, "The ZIP file to check"],
    member_name: Annotated[str, "The name of the member to check"],
    *,
    limits: Annotated[ZipValidationSettings | None, "Optional validation limits to use"] = None,
) -> None:
    """Ensure an individual member stays within safe boundaries before reading."""
    limits = limits or _ZipConfig.defaults
    info = zf.getinfo(member_name)
    if info.file_size > limits.max_member_size:
        raise ZipMemberSizeError(member_name, info.file_size, limits.max_member_size)


def _ensure_safe_path(member_name: str) -> None:
    """Check for unsafe path components in a zip member name."""
    # Check for absolute paths (POSIX, Windows, UNC) and drive prefixes.
    # Using string checks is more reliable for cross-platform validation than pathlib.
    is_abs = member_name.startswith(("/", "\\")) or (len(member_name) > 1 and member_name[1] == ":")
    if is_abs:
        raise ZipPathTraversalError(member_name)

    # Check for path traversal. Normalizing separators and wrapping with slashes
    # handles cases like '../foo', 'foo/..', and 'foo/../bar'.
    normalized_path = member_name.replace("\\", "/")
    if "/../" in f"/{normalized_path}/":
        raise ZipPathTraversalError(member_name)
