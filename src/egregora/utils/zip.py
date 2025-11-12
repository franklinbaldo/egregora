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


_DEFAULT_LIMITS: ZipValidationSettings = ZipValidationSettings()


def configure_default_limits(
    limits: Annotated[ZipValidationSettings, "The new default validation limits"],
) -> None:
    """Override module-wide validation limits."""
    global _DEFAULT_LIMITS
    _DEFAULT_LIMITS = limits


def validate_zip_contents(
    zf: Annotated[zipfile.ZipFile, "The ZIP file to validate"],
    *,
    limits: Annotated[ZipValidationSettings | None, "Optional validation limits to use"] = None,
) -> None:
    """Validate members of a ZIP archive.

    Guards against zip bombs, resource exhaustion and path traversal by
    inspecting the metadata of each member before extraction.
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
