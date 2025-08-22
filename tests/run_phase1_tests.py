#!/usr/bin/env python3
"""
Run all Phase 1 Pipeline tests
"""

import sys
import subprocess
from pathlib import Path

def run_test_file(test_file):
    """Run a specific test file and return success status."""
    print(f"🔬 Running {test_file}...")
    try:
        result = subprocess.run([sys.executable, test_file], 
                               capture_output=True, text=True, cwd=Path(__file__).parent)
        
        if result.returncode == 0:
            print(f"✅ {test_file} PASSED")
            return True
        else:
            print(f"❌ {test_file} FAILED")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {test_file} CRASHED: {e}")
        return False

def main():
    """Run all Phase 1 tests."""
    print("🚀 Running Phase 1 Pipeline Test Suite...\n")
    
    test_files = [
        "test_pipeline_phase1.py",
        "test_pipeline_logic.py", 
        "test_pipeline_threading.py",
        "test_phase1_integration.py"
    ]
    
    passed = 0
    failed = 0
    
    for test_file in test_files:
        if run_test_file(test_file):
            passed += 1
        else:
            failed += 1
        print()  # Spacing
    
    print("="*60)
    print(f"📊 PHASE 1 TEST SUITE SUMMARY:")
    print(f"   ✅ Test Files Passed: {passed}")
    print(f"   ❌ Test Files Failed: {failed}")
    print(f"   📈 Success Rate: {(passed/(passed+failed)*100):.1f}%")
    
    if failed == 0:
        print("🎉 ALL PHASE 1 TESTS PASSED! Ready for commit.")
    else:
        print("⚠️  Some tests failed. Review before committing.")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)