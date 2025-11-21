"""Security helpers for validating WhatsApp ZIP exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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
    """Raised when a ZIP archive fails validation checks."""


@dataclass(frozen=True, slots=True)
class ZipValidationSettings:
    """Constraints applied when validating WhatsApp ZIP archives."""

    max_total_size: int = 500 * 1024 * 1024
    max_member_size: int = 50 * 1024 * 1024
    max_member_count: int = 2000
    max_compression_ratio: float = 100.0  # Detect zip bombs (100:1 ratio)


_DEFAULT_LIMITS: ZipValidationSettings = ZipValidationSettings()


def configure_default_limits(
    limits: Annotated[ZipValidationSettings, "The new default validation limits"],
) -> None:
    """Override module-wide validation limits."""
    global _DEFAULT_LIMITS  # noqa: PLW0603
    _DEFAULT_LIMITS = limits


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
    limits = limits or _DEFAULT_LIMITS
    total_size = 0
    members = zf.infolist()
    if len(members) > limits.max_member_count:
        msg = f"ZIP archive contains too many files ({len(members)} > {limits.max_member_count})"
        raise ZipValidationError(msg)
    for info in members:
        _ensure_safe_path(info.filename)
        if info.file_size > limits.max_member_size:
            msg = f"ZIP member '{info.filename}' exceeds maximum size of {limits.max_member_size} bytes"
            raise ZipValidationError(msg)

        # Check compression ratio to detect zip bombs
        if info.compress_size > 0 and info.file_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > limits.max_compression_ratio:
                msg = (
                    f"ZIP member '{info.filename}' has suspicious compression ratio "
                    f"({ratio:.1f}:1 > {limits.max_compression_ratio}:1). "
                    f"This may indicate a zip bomb attack."
                )
                raise ZipValidationError(msg)

        total_size += info.file_size
        if total_size > limits.max_total_size:
            msg = f"ZIP archive uncompressed size exceeds {limits.max_total_size} bytes"
            raise ZipValidationError(msg)


def ensure_safe_member_size(
    zf: Annotated[zipfile.ZipFile, "The ZIP file to check"],
    member_name: Annotated[str, "The name of the member to check"],
    *,
    limits: Annotated[ZipValidationSettings | None, "Optional validation limits to use"] = None,
) -> None:
    """Ensure an individual member stays within safe boundaries before reading."""
    limits = limits or _DEFAULT_LIMITS
    info = zf.getinfo(member_name)
    if info.file_size > limits.max_member_size:
        msg = f"ZIP member '{member_name}' exceeds maximum size of {limits.max_member_size} bytes"
        raise ZipValidationError(msg)


def _ensure_safe_path(member_name: str) -> None:
    path = Path(member_name)
    if path.is_absolute():
        msg = f"ZIP member uses absolute path: {member_name}"
        raise ZipValidationError(msg)
    if any(part == ".." for part in path.parts):
        msg = f"ZIP member attempts path traversal: {member_name}"
        raise ZipValidationError(msg)
    if path.drive:
        msg = f"ZIP member uses unsupported drive prefix: {member_name}"
        raise ZipValidationError(msg)
