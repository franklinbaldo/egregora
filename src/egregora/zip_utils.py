"""Security helpers for validating WhatsApp ZIP exports."""

from __future__ import annotations

import zipfile
from pathlib import Path

__all__ = [
    "ZipValidationError",
    "validate_zip_contents",
    "ensure_safe_member_size",
]


class ZipValidationError(ValueError):
    """Raised when a ZIP archive fails validation checks."""


_MAX_TOTAL_SIZE = 500 * 1024 * 1024  # 500MB - increased for media-heavy groups
_MAX_MEMBER_SIZE = 50 * 1024 * 1024  # 50MB per file - for videos/images
_MAX_MEMBER_COUNT = 2000  # Increased for WhatsApp groups with lots of media


def validate_zip_contents(
    zf: zipfile.ZipFile,
    *,
    max_total_size: int = _MAX_TOTAL_SIZE,
    max_member_size: int = _MAX_MEMBER_SIZE,
    max_member_count: int = _MAX_MEMBER_COUNT,
) -> None:
    """Validate members of a ZIP archive.

    Guards against zip bombs, resource exhaustion and path traversal by
    inspecting the metadata of each member before extraction.
    """

    total_size = 0
    members = zf.infolist()

    if len(members) > max_member_count:
        raise ZipValidationError(
            f"ZIP archive contains too many files ({len(members)} > {max_member_count})"
        )

    for info in members:
        _ensure_safe_path(info.filename)

        if info.file_size > max_member_size:
            raise ZipValidationError(
                f"ZIP member '{info.filename}' exceeds maximum size of {max_member_size} bytes"
            )

        total_size += info.file_size
        if total_size > max_total_size:
            raise ZipValidationError(
                f"ZIP archive uncompressed size exceeds {max_total_size} bytes"
            )


def ensure_safe_member_size(
    zf: zipfile.ZipFile,
    member_name: str,
    *,
    max_member_size: int = _MAX_MEMBER_SIZE,
) -> None:
    """Ensure an individual member stays within safe boundaries before reading."""

    info = zf.getinfo(member_name)
    if info.file_size > max_member_size:
        raise ZipValidationError(
            f"ZIP member '{member_name}' exceeds maximum size of {max_member_size} bytes"
        )


def _ensure_safe_path(member_name: str) -> None:
    path = Path(member_name)

    if path.is_absolute():
        raise ZipValidationError(f"ZIP member uses absolute path: {member_name}")

    if any(part == ".." for part in path.parts):
        raise ZipValidationError(f"ZIP member attempts path traversal: {member_name}")

    # Reject Windows drive prefixes such as C:\foo
    if path.drive:
        raise ZipValidationError(f"ZIP member uses unsupported drive prefix: {member_name}")
