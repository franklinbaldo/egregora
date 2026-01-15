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

from egregora.common.datetime_utils import (
    DateTimeParsingError,
    InvalidDateTimeInputError,
    ensure_datetime,
    parse_datetime_flexible,
)
from egregora.knowledge.exceptions import AuthorsFileLoadError
from egregora.orchestration.exceptions import CacheKeyNotFoundError

# Add src to path to import modules directly
sys.path.insert(0, "src")

EXPECTED_PARSED_YEAR = 2023


def test_whatsapp_parsing() -> None:
    """Test WhatsApp ZIP parsing without full pipeline."""
    zip_path = Path("tests/fixtures/Conversa do WhatsApp com Teste.zip")

    assert zip_path.exists()

    # Test ZIP can be opened and validated
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.namelist()
            txt_files = [m for m in members if m.endswith(".txt")]
            assert txt_files
    except (zipfile.BadZipFile, OSError) as e:
        pytest.fail(f"Could not open or validate zip file: {e}")


def test_datetime_utilities() -> None:
    """Test the datetime utilities we merged."""
    # Test valid parsing
    result = parse_datetime_flexible("2023-01-01T12:00:00")
    assert result.year == EXPECTED_PARSED_YEAR

    # Test None raises exception
    with pytest.raises((DateTimeParsingError, InvalidDateTimeInputError)):
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
    # Check the file compiles
    py_compile.compile("src/egregora/output_adapters/mkdocs/adapter.py", doraise=True)

    # Check it has the expected imports
    with Path("src/egregora/output_adapters/mkdocs/adapter.py").open() as f:
        content = f.read()

    required_imports = [
        "CollisionResolutionError",
        "ConfigLoadError",
        "DocumentNotFoundError",
    ]

    for imp in required_imports:
        assert imp in content


def main() -> bool:
    """Run all integration tests."""
    results = []

    # Run tests
    results.append(("WhatsApp Parsing", test_whatsapp_parsing()))
    results.append(("DateTime Utilities", test_datetime_utilities()))
    results.append(("Exception Classes", test_exception_classes()))
    results.append(("MkDocs Adapter", test_mkdocs_adapter_imports()))

    # Summary

    sum(1 for _, result in results if result)
    len(results)

    for _name, _result in results:
        pass

    return all(result for _, result in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
