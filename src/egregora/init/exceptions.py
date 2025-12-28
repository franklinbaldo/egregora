"""Exceptions for the site initialization and scaffolding process."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class ScaffoldingError(Exception):
    """Base exception for scaffolding errors."""


class ScaffoldingPathError(ScaffoldingError):
    """Raised when site path resolution fails."""

    def __init__(self, site_root: Path, original_exception: Exception) -> None:
        self.site_root = site_root
        super().__init__(
            f"Failed to derive MkDocs paths for site root '{site_root}'. "
            "The directory may be misconfigured or an I/O error occurred."
        )
        self.__cause__ = original_exception


class ScaffoldingExecutionError(ScaffoldingError):
    """Raised when the scaffolding execution fails."""

    def __init__(self, site_root: Path, original_exception: Exception) -> None:
        self.site_root = site_root
        super().__init__(f"Failed to scaffold site at root '{site_root}'.")
        self.__cause__ = original_exception
