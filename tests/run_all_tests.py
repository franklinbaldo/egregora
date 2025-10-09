#!/usr/bin/env python3
"""Run all egregora tests with WhatsApp integration validation."""

import subprocess
import sys
from pathlib import Path


def run_test_file(test_path: Path) -> tuple[bool, str]:
    """Run a single test file and return success status and output."""
    try:
        result = subprocess.run(
            [sys.executable, str(test_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per test file
        )
        
        return result.returncode == 0, result.stdout + result.stderr
    
    except subprocess.TimeoutExpired:
        return False, f"Test {test_path.name} timed out after 5 minutes"
    except Exception as e:
        return False, f"Error running {test_path.name}: {e}"


def main():
    """Run all test files and report results."""
    tests_dir = Path(__file__).parent
    
    # Define test files in execution order
    test_files = [
        "test_core_pipeline.py",
        "test_enrichment_simple.py", 
        "test_rag_integration.py",
        "test_post_simple.py",
        "test_whatsapp_integration.py",
    ]
    
    print("🚀 Running Egregora WhatsApp Integration Test Suite")
    print("=" * 60)
    
    total_tests = len(test_files)
    passed_tests = 0
    failed_tests = []
    
    for test_file in test_files:
        test_path = tests_dir / test_file
        
        if not test_path.exists():
            print(f"❌ Test file not found: {test_file}")
            failed_tests.append(test_file)
            continue
        
        print(f"\n📋 Running {test_file}...")
        success, output = run_test_file(test_path)
        
        if success:
            print(f"✅ {test_file} PASSED")
            passed_tests += 1
            
            # Extract and show summary from output
            lines = output.split('\n')
            for line in lines:
                if '✓' in line and 'test passed' in line:
                    print(f"   {line.strip()}")
                elif '🎉' in line and 'passed' in line:
                    print(f"   {line.strip()}")
        else:
            print(f"❌ {test_file} FAILED")
            failed_tests.append(test_file)
            
            # Show error details
            error_lines = output.split('\n')[-10:]  # Last 10 lines
            print("   Error details:")
            for line in error_lines:
                if line.strip():
                    print(f"   {line}")
    
    # Final summary
    print("\n" + "=" * 60)
    print(f"📊 TEST SUMMARY")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    
    if failed_tests:
        print(f"\n❌ Failed tests:")
        for test in failed_tests:
            print(f"   - {test}")
        print(f"\n🔧 Run individual tests for detailed error information:")
        for test in failed_tests:
            print(f"   python3 tests/{test}")
    else:
        print(f"\n🎉 ALL TESTS PASSED! WhatsApp integration is working correctly.")
        print(f"\n✨ Egregora is ready to process WhatsApp conversation exports!")
    
    # Exit with appropriate code
    sys.exit(0 if not failed_tests else 1)


if __name__ == "__main__":
    main()