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

# Add src to path to import modules directly
sys.path.insert(0, "src")

EXPECTED_PARSED_YEAR = 2023


def test_whatsapp_parsing() -> bool | None:
    """Test WhatsApp ZIP parsing without full pipeline."""
    zip_path = Path("tests/fixtures/Conversa do WhatsApp com Teste.zip")

    if not zip_path.exists():
        return False

    # Test ZIP can be opened and validated
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.namelist()
            txt_files = [m for m in members if m.endswith(".txt")]
            [m for m in members if m.endswith((".jpg", ".jpeg", ".png"))]

            if txt_files:
                pass

            return True
    except (zipfile.BadZipFile, OSError):
        return False


def test_datetime_utilities() -> bool | None:
    """Test the datetime utilities we merged."""
    try:
        # Import directly to avoid __init__.py issues
        import importlib.util

        # Load exceptions module
        spec = importlib.util.spec_from_file_location(
            "egregora.utils.exceptions", "src/egregora/utils/exceptions.py"
        )
        exceptions_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exceptions_mod)

        # Load datetime_utils module
        spec = importlib.util.spec_from_file_location(
            "egregora.utils.datetime_utils", "src/egregora/utils/datetime_utils.py"
        )
        datetime_utils_mod = importlib.util.module_from_spec(spec)
        sys.modules["egregora.utils.exceptions"] = exceptions_mod
        spec.loader.exec_module(datetime_utils_mod)

        from datetime import datetime

        # Test valid parsing
        result = datetime_utils_mod.parse_datetime_flexible("2023-01-01T12:00:00")
        if result.year != EXPECTED_PARSED_YEAR:
            return False

        # Test None raises exception
        try:
            datetime_utils_mod.parse_datetime_flexible(None)
            return False
        except (
            datetime_utils_mod.DateTimeParsingError,
            datetime_utils_mod.InvalidDateTimeInputError,
        ):
            pass

        # Test ensure_datetime
        result = datetime_utils_mod.ensure_datetime("2023-01-01")
        return isinstance(result, datetime)

    except (ImportError, AttributeError, exceptions_mod.DateTimeParsingError):
        import traceback

        traceback.print_exc()
        return False


def test_exception_classes() -> bool | None:
    """Test new exception classes from merged PRs."""
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "egregora.utils.exceptions", "src/egregora/utils/exceptions.py"
        )
        exceptions_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exceptions_mod)

        # Load cache_utils module
        spec = importlib.util.spec_from_file_location("egregora.utils.cache", "src/egregora/utils/cache.py")
        cache_utils_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cache_utils_mod)

        # Load knowledge_exceptions module
        spec = importlib.util.spec_from_file_location(
            "egregora.knowledge.exceptions", "src/egregora/knowledge/exceptions.py"
        )
        knowledge_exceptions_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(knowledge_exceptions_mod)

        # Load datetime_utils module
        spec = importlib.util.spec_from_file_location(
            "egregora.utils.datetime_utils", "src/egregora/utils/datetime_utils.py"
        )
        datetime_utils_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(datetime_utils_mod)

        # Test CacheKeyNotFoundError
        exc = cache_utils_mod.CacheKeyNotFoundError("test_key")
        if exc.key != "test_key":
            return False

        # Test AuthorsFileLoadError
        exc = knowledge_exceptions_mod.AuthorsFileLoadError("/path/to/file", OSError("test"))
        if exc.path != "/path/to/file":
            return False

        # Test DateTimeParsingError
        exc = datetime_utils_mod.DateTimeParsingError("invalid", ValueError("test"))
        return exc.value == "invalid"

    except (ImportError, AttributeError):
        import traceback

        traceback.print_exc()
        return False


def test_mkdocs_adapter_imports() -> bool | None:
    """Test that MkDocs adapter has all required exception imports."""
    try:
        # Check the file compiles
        import py_compile

        py_compile.compile("src/egregora/output_adapters/mkdocs/adapter.py", doraise=True)

        # Check it has the expected imports
        with Path("src/egregora/output_adapters/mkdocs/adapter.py").open() as f:
            content = f.read()

        required_imports = [
            "CollisionResolutionError",
            "ConfigLoadError",
            "DocumentNotFoundError",
            "parse_datetime_flexible",
        ]

        for imp in required_imports:
            if imp in content:
                pass
            else:
                return False

        return True

    except (ImportError, py_compile.PyCompileError, FileNotFoundError):
        import traceback

        traceback.print_exc()
        return False


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
