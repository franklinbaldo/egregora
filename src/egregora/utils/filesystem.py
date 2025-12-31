"""Filesystem utilities for writing structured content.

This module consolidates file writing logic previously scattered across adapters.
It provides standard helpers for:
- Writing markdown posts with frontmatter
- Handling safe filenames and collision resolution
- Managing directory structures
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

ISO_DATE_LENGTH = 10  # Length of ISO date format (YYYY-MM-DD)
_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


class FilesystemError(Exception):
    """Base exception for filesystem-related errors."""


class FilesystemOperationError(FilesystemError):
    """Base exception for file I/O errors."""

    def __init__(self, path: str, original_exception: Exception, message: str | None = None) -> None:
        self.path = path
        self.original_exception = original_exception
        if message is None:
            message = f"An error occurred at path: {self.path}. Original error: {original_exception}"
        super().__init__(message)


class DirectoryCreationError(FilesystemOperationError):
    """Raised when creating a directory fails."""

    def __init__(self, path: str, original_exception: Exception) -> None:
        message = f"Failed to create directory at: {path}. Original error: {original_exception}"
        super().__init__(path, original_exception, message=message)


class FileWriteError(FilesystemOperationError):
    """Raised when writing a file fails."""

    def __init__(self, path: str, original_exception: Exception) -> None:
        message = f"Failed to write file to: {path}. Original error: {original_exception}"
        super().__init__(path, original_exception, message=message)
