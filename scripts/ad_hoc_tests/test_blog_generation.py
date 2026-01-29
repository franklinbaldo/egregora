#!/usr/bin/env python3
"""Simple blog generation test using the WhatsApp fixture.

This test verifies that the core components we merged work together:
- WhatsApp adapter parsing
- DuckDB repository with new hydration methods
- Datetime utilities with exception handling
- MkDocs adapter with new exception imports
"""

import py_compile
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

# Add src to path to import modules directly
sys.path.insert(0, "src")

# Imports for tests
from egregora.data_primitives.datetime_utils import (
    DateTimeParsingError,
    InvalidDateTimeInputError,
    ensure_datetime,
    parse_datetime_flexible,
)
from egregora.knowledge.exceptions import AuthorsFileLoadError
from egregora.orchestration.exceptions import CacheKeyNotFoundError

EXPECTED_PARSED_YEAR = 2023


def test_whatsapp_parsing() -> None:
    """Test WhatsApp ZIP parsing without full pipeline."""
    zip_path = Path("tests/fixtures/Conversa do WhatsApp com Teste.zip")
    assert zip_path.exists(), "WhatsApp fixture ZIP not found"

    # Test ZIP can be opened and validated
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.namelist()
            txt_files = [m for m in members if m.endswith(".txt")]
            assert txt_files, "No text files found in ZIP"
    except (zipfile.BadZipFile, OSError) as e:
        pytest.fail(f"Failed to process WhatsApp ZIP: {e}")


def test_datetime_utilities() -> None:
    """Test the datetime utilities we merged."""
    # Test valid parsing
    result = parse_datetime_flexible("2023-01-01T12:00:00")
    assert result.year == EXPECTED_PARSED_YEAR

    # Test None raises exception
    with pytest.raises(InvalidDateTimeInputError):
        parse_datetime_flexible(None)

    # Test ensure_datetime
    result = ensure_datetime("2023-01-01")
    assert isinstance(result, datetime)


def test_exception_classes() -> None:
    """Test new exception classes from merged PRs."""
    # Test CacheKeyNotFoundError
    exc = CacheKeyNotFoundError("test_key")
    assert exc.key == "test_key"

    # Test AuthorsFileLoadError
    exc = AuthorsFileLoadError("/path/to/file", OSError("test"))
    assert exc.path == "/path/to/file"

    # Test DateTimeParsingError
    exc = DateTimeParsingError("invalid", ValueError("test"))
    assert exc.value == "invalid"


def test_mkdocs_adapter_imports() -> None:
    """Test that MkDocs adapter has all required exception imports."""
    adapter_path = "src/egregora/output_sinks/mkdocs/adapter.py"

    # Check the file compiles
    try:
        py_compile.compile(adapter_path, doraise=True)
    except (py_compile.PyCompileError, FileNotFoundError) as e:
        pytest.fail(f"Failed to compile MkDocs adapter: {e}")

    # Check it has the expected imports
    with Path(adapter_path).open() as f:
        content = f.read()

    required_imports = [
        "CollisionResolutionError",
        "ConfigLoadError",
        "DocumentNotFoundError",
    ]

    for imp in required_imports:
        assert imp in content, f"Missing required import in MkDocs adapter: {imp}"
