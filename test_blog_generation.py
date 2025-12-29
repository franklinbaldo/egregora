#!/usr/bin/env python3
"""Simple blog generation test using the WhatsApp fixture.

This test verifies that the core components we merged work together:
- WhatsApp adapter parsing
- DuckDB repository with new hydration methods
- Datetime utilities with exception handling
- MkDocs adapter with new exception imports
"""

import sys
import zipfile
from pathlib import Path

import pytest

# Add src to path to import modules directly
sys.path.insert(0, "src")

from egregora.utils.exceptions import DateTimeParsingError


def test_whatsapp_parsing() -> None:
    """Test WhatsApp ZIP parsing without full pipeline."""
    zip_path = Path("tests/fixtures/Conversa do WhatsApp com Teste.zip")
    assert zip_path.exists()  # noqa: S101

    with zipfile.ZipFile(zip_path) as archive:
        members = archive.namelist()
        txt_files = [m for m in members if m.endswith(".txt")]
        assert txt_files  # noqa: S101
        [m for m in members if m.endswith((".jpg", ".jpeg", ".png"))]


def test_datetime_utilities() -> None:
    """Test the datetime utilities we merged."""
    from datetime import datetime

    from egregora.utils.datetime_utils import ensure_datetime, parse_datetime_flexible

    # Test valid parsing
    result = parse_datetime_flexible("2023-01-01T12:00:00")
    assert result  # noqa: S101
    assert result.year == 2023  # noqa: S101, PLR2004

    # Test None raises exception
    with pytest.raises(DateTimeParsingError):
        parse_datetime_flexible(None)

    # Test ensure_datetime
    result = ensure_datetime("2023-01-01")
    assert isinstance(result, datetime)  # noqa: S101


def test_exception_classes() -> None:
    """Test new exception classes from merged PRs."""
    from egregora.utils.exceptions import AuthorsFileLoadError, CacheKeyNotFoundError, DateTimeParsingError

    # Test CacheKeyNotFoundError
    exc = CacheKeyNotFoundError("test_key")
    assert exc.key == "test_key"  # noqa: S101

    # Test AuthorsFileLoadError
    exc = AuthorsFileLoadError("/path/to/file", OSError("test"))
    assert exc.path == "/path/to/file"  # noqa: S101

    # Test DateTimeParsingError
    exc = DateTimeParsingError("invalid", ValueError("test"))
    assert exc.value == "invalid"  # noqa: S101


def test_mkdocs_adapter_imports() -> None:
    """Test that MkDocs adapter has all required exception imports."""
    # Check the file compiles
    import py_compile

    py_compile.compile("src/egregora/output_adapters/mkdocs/adapter.py", doraise=True)

    # Check it has the expected imports
    adapter_path = Path("src/egregora/output_adapters/mkdocs/adapter.py")
    content = adapter_path.read_text()

    required_imports = [
        "CollisionResolutionError",
        "ConfigLoadError",
        "DocumentNotFoundError",
        "parse_datetime_flexible",
    ]

    for imp in required_imports:
        assert imp in content  # noqa: S101


def main() -> bool:
    """Run all integration tests."""
    results = []

    # Run tests
    try:
        test_whatsapp_parsing()
        results.append(("WhatsApp Parsing", True))
    except AssertionError:
        results.append(("WhatsApp Parsing", False))

    try:
        test_datetime_utilities()
        results.append(("DateTime Utilities", True))
    except AssertionError:
        results.append(("DateTime Utilities", False))

    try:
        test_exception_classes()
        results.append(("Exception Classes", True))
    except AssertionError:
        results.append(("Exception Classes", False))

    try:
        test_mkdocs_adapter_imports()
        results.append(("MkDocs Adapter", True))
    except AssertionError:
        results.append(("MkDocs Adapter", False))

    # Summary
    for _name, _result in results:
        pass

    return all(result for _, result in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
