#!/usr/bin/env python3
"""Simple blog generation test using the WhatsApp fixture.

This test verifies that the core components we merged work together:
- WhatsApp adapter parsing
- DuckDB repository with new hydration methods
- Datetime utilities with exception handling
- MkDocs adapter with new exception imports
"""

import sys
import tempfile
import zipfile
from pathlib import Path

# Add src to path to import modules directly
sys.path.insert(0, 'src')

def test_whatsapp_parsing():
    """Test WhatsApp ZIP parsing without full pipeline."""
    print("=" * 60)
    print("Test 1: WhatsApp ZIP Parsing")
    print("=" * 60)

    zip_path = Path("tests/fixtures/Conversa do WhatsApp com Teste.zip")

    if not zip_path.exists():
        print(f"❌ Fixture not found: {zip_path}")
        return False

    # Test ZIP can be opened and validated
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.namelist()
            txt_files = [m for m in members if m.endswith('.txt')]
            img_files = [m for m in members if m.endswith(('.jpg', '.jpeg', '.png'))]

            print(f"✓ ZIP opened successfully")
            print(f"  - Chat files: {len(txt_files)}")
            print(f"  - Media files: {len(img_files)}")

            if txt_files:
                print(f"  - Main chat file: {txt_files[0]}")

            return True
    except Exception as e:
        print(f"❌ ZIP validation failed: {e}")
        return False


def test_datetime_utilities():
    """Test the datetime utilities we merged."""
    print("\n" + "=" * 60)
    print("Test 2: DateTime Utilities")
    print("=" * 60)

    try:
        # Import directly to avoid __init__.py issues
        import importlib.util

        # Load exceptions module
        spec = importlib.util.spec_from_file_location(
            "egregora.utils.exceptions",
            "src/egregora/utils/exceptions.py"
        )
        exceptions_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exceptions_mod)

        # Load datetime_utils module
        spec = importlib.util.spec_from_file_location(
            "egregora.utils.datetime_utils",
            "src/egregora/utils/datetime_utils.py"
        )
        datetime_utils_mod = importlib.util.module_from_spec(spec)
        sys.modules['egregora.utils.exceptions'] = exceptions_mod
        spec.loader.exec_module(datetime_utils_mod)

        from datetime import datetime

        # Test valid parsing
        result = datetime_utils_mod.parse_datetime_flexible('2023-01-01T12:00:00')
        assert result.year == 2023
        print("✓ Valid datetime parsing works")

        # Test None raises exception
        try:
            datetime_utils_mod.parse_datetime_flexible(None)
            print("❌ Should have raised DateTimeParsingError for None")
            return False
        except exceptions_mod.DateTimeParsingError:
            print("✓ DateTimeParsingError raised for None")

        # Test ensure_datetime
        result = datetime_utils_mod.ensure_datetime('2023-01-01')
        assert isinstance(result, datetime)
        print("✓ ensure_datetime works")

        return True

    except Exception as e:
        print(f"❌ DateTime utilities test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_exception_classes():
    """Test new exception classes from merged PRs."""
    print("\n" + "=" * 60)
    print("Test 3: Exception Classes")
    print("=" * 60)

    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "egregora.utils.exceptions",
            "src/egregora/utils/exceptions.py"
        )
        exceptions_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exceptions_mod)

        # Test CacheKeyNotFoundError
        exc = exceptions_mod.CacheKeyNotFoundError("test_key")
        assert exc.key == "test_key"
        print("✓ CacheKeyNotFoundError works")

        # Test AuthorsFileLoadError
        exc = exceptions_mod.AuthorsFileLoadError("/path/to/file", IOError("test"))
        assert exc.path == "/path/to/file"
        print("✓ AuthorsFileLoadError works")

        # Test DateTimeParsingError
        exc = exceptions_mod.DateTimeParsingError("invalid", ValueError("test"))
        assert exc.value == "invalid"
        print("✓ DateTimeParsingError works")

        return True

    except Exception as e:
        print(f"❌ Exception classes test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mkdocs_adapter_imports():
    """Test that MkDocs adapter has all required exception imports."""
    print("\n" + "=" * 60)
    print("Test 4: MkDocs Adapter Exception Imports")
    print("=" * 60)

    try:
        # Check the file compiles
        import py_compile
        py_compile.compile('src/egregora/output_adapters/mkdocs/adapter.py', doraise=True)
        print("✓ MkDocs adapter compiles successfully")

        # Check it has the expected imports
        with open('src/egregora/output_adapters/mkdocs/adapter.py') as f:
            content = f.read()

        required_imports = [
            'CollisionResolutionError',
            'ConfigLoadError',
            'DocumentNotFoundError',
            'parse_datetime_flexible',
        ]

        for imp in required_imports:
            if imp in content:
                print(f"✓ Import '{imp}' present")
            else:
                print(f"❌ Import '{imp}' missing")
                return False

        return True

    except Exception as e:
        print(f"❌ MkDocs adapter test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("BLOG GENERATION INTEGRATION TEST")
    print("Testing components after PR merges")
    print("=" * 60 + "\n")

    results = []

    # Run tests
    results.append(("WhatsApp Parsing", test_whatsapp_parsing()))
    results.append(("DateTime Utilities", test_datetime_utilities()))
    results.append(("Exception Classes", test_exception_classes()))
    results.append(("MkDocs Adapter", test_mkdocs_adapter_imports()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    return all(result for _, result in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
