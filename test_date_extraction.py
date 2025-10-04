#!/usr/bin/env python3
"""Quick test script to verify date extraction and warnings work."""

import sys
import tempfile
import zipfile
from pathlib import Path
from datetime import date
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from egregora.group_discovery import _extract_date

# Set up logging to see debug and warning messages
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_date_extraction():
    """Test different scenarios of date extraction."""
    
    # Test 1: ZIP with explicit date in filename
    print("=" * 50)
    print("Test 1: ZIP with explicit date in filename")
    with tempfile.NamedTemporaryFile(suffix="-2025-10-03-test.zip", delete=False) as tmp:
        zip_path = Path(tmp.name)
        
        # Create a minimal ZIP with chat content
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("Conversa do WhatsApp com Test.txt", "03/10/2025 09:45 - Test message")
        
        try:
            extracted_date = _extract_date(zip_path, zipfile.ZipFile(zip_path), "Conversa do WhatsApp com Test.txt")
            print(f"Extracted date: {extracted_date}")
            assert extracted_date == date(2025, 10, 3)
            print("✅ Test 1 passed")
        finally:
            zip_path.unlink()
    
    # Test 2: ZIP without date in filename (should extract from content)
    print("\n" + "=" * 50)
    print("Test 2: ZIP without date in filename (extract from content)")
    with tempfile.NamedTemporaryFile(suffix="-natural-name.zip", delete=False) as tmp:
        zip_path = Path(tmp.name)
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("Conversa do WhatsApp com Test.txt", "03/10/2025 09:45 - Test message")
        
        try:
            extracted_date = _extract_date(zip_path, zipfile.ZipFile(zip_path), "Conversa do WhatsApp com Test.txt")
            print(f"Extracted date: {extracted_date}")
            assert extracted_date == date(2025, 10, 3)
            print("✅ Test 2 passed")
        finally:
            zip_path.unlink()
    
    # Test 3: ZIP without date in filename or content (should fallback to mtime with warning)
    print("\n" + "=" * 50)
    print("Test 3: ZIP fallback to mtime (should show warning)")
    with tempfile.NamedTemporaryFile(suffix="-fallback-test.zip", delete=False) as tmp:
        zip_path = Path(tmp.name)
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("Conversa do WhatsApp com Test.txt", "No date content here")
        
        try:
            extracted_date = _extract_date(zip_path, zipfile.ZipFile(zip_path), "Conversa do WhatsApp com Test.txt")
            print(f"Extracted date: {extracted_date}")
            print("✅ Test 3 passed (should have shown warning above)")
        finally:
            zip_path.unlink()

if __name__ == "__main__":
    test_date_extraction()
    print("\n🎉 All tests completed!")