"""Security helpers for validating WhatsApp ZIP exports."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "ZipValidationError",
    "ZipValidationLimits",
    "configure_default_limits",
    "validate_zip_contents",
    "ensure_safe_member_size",
]


class ZipValidationError(ValueError):
    """Raised when a ZIP archive fails validation checks."""


@dataclass(frozen=True, slots=True)
class ZipValidationLimits:
    """Constraints applied when validating WhatsApp ZIP archives."""

    max_total_size: int = 500 * 1024 * 1024  # 500MB
    max_member_size: int = 50 * 1024 * 1024  # 50MB per file
    max_member_count: int = 2000


_DEFAULT_LIMITS: ZipValidationLimits = ZipValidationLimits()


def configure_default_limits(limits: ZipValidationLimits) -> None:
    """Override module-wide validation limits."""

    global _DEFAULT_LIMITS  # noqa: PLW0603
    _DEFAULT_LIMITS = limits


def validate_zip_contents(
    zf: zipfile.ZipFile,
    *,
    limits: ZipValidationLimits | None = None,
) -> None:
    """Validate members of a ZIP archive.

    Guards against zip bombs, resource exhaustion and path traversal by
    inspecting the metadata of each member before extraction.
    """

    limits = limits or _DEFAULT_LIMITS
    total_size = 0
    members = zf.infolist()

    if len(members) > limits.max_member_count:
        raise ZipValidationError(
            f"ZIP archive contains too many files ({len(members)} > {limits.max_member_count})"
        )

    for info in members:
        _ensure_safe_path(info.filename)

        if info.file_size > limits.max_member_size:
            raise ZipValidationError(
                f"ZIP member '{info.filename}' exceeds maximum size of {limits.max_member_size} bytes"
            )

        total_size += info.file_size
        if total_size > limits.max_total_size:
            raise ZipValidationError(
                f"ZIP archive uncompressed size exceeds {limits.max_total_size} bytes"
            )


def ensure_safe_member_size(
    zf: zipfile.ZipFile,
    member_name: str,
    *,
    limits: ZipValidationLimits | None = None,
) -> None:
    """Ensure an individual member stays within safe boundaries before reading."""

    limits = limits or _DEFAULT_LIMITS
    info = zf.getinfo(member_name)
    if info.file_size > limits.max_member_size:
        raise ZipValidationError(
            f"ZIP member '{member_name}' exceeds maximum size of {limits.max_member_size} bytes"
        )


def _ensure_safe_path(member_name: str) -> None:
    path = Path(member_name)

    if path.is_absolute():
        raise ZipValidationError(f"ZIP member uses absolute path: {member_name}")

    if ".." in path.parts:
        raise ZipValidationError(f"ZIP member attempts path traversal: {member_name}")
