#!/usr/bin/env python3
"""
Test runner script that executes all test suites and cleans up after itself.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_test_script(script_path, description):
    """Run a test script and report results."""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print(f"{'='*60}")
    
    try:
        # Change to the parent directory so imports work correctly
        parent_dir = script_path.parent.parent
        result = subprocess.run([
            sys.executable, str(script_path)
        ], cwd=parent_dir, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(result.stdout)
            if result.stderr:
                print("Warnings/Info:")
                print(result.stderr)
            print(f"✅ {description} - PASSED")
            return True
        else:
            print(f"❌ {description} - FAILED")
            print("STDOUT:")
            print(result.stdout)
            if result.stderr:
                print("STDERR:")
                print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏱️ {description} - TIMEOUT (>5 minutes)")
        return False
    except Exception as e:
        print(f"💥 {description} - ERROR: {e}")
        return False

def cleanup_test_artifacts():
    """Clean up any test artifacts."""
    test_dir = Path(__file__).parent
    
    # Remove test video directories
    test_video_dirs = [
        test_dir / "test_gradio_demo",
        test_dir / "test_files",
        test_dir / "test_videos"
    ]
    
    for directory in test_video_dirs:
        if directory.exists():
            try:
                shutil.rmtree(directory)
                print(f"🧹 Cleaned up: {directory.name}")
            except Exception as e:
                print(f"⚠️ Could not clean up {directory.name}: {e}")
    
    # Remove any stray test video files
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv']
    for ext in video_extensions:
        for video_file in test_dir.glob(f"*{ext}"):
            try:
                video_file.unlink()
                print(f"🧹 Cleaned up: {video_file.name}")
            except Exception as e:
                print(f"⚠️ Could not clean up {video_file.name}: {e}")

def main():
    """Run all test suites."""
    print("🚀 Video Compression Test Suite Runner")
    print("=" * 60)
    
    test_dir = Path(__file__).parent
    
    # Define test scripts and their descriptions
    test_scripts = [
        (test_dir / "test_compression.py", "Core Compression Functionality"),
        (test_dir / "test_parallel.py", "Parallel Processing Features"),
        (test_dir / "test_gradio_progress.py", "Enhanced Progress Tracking"),
        (test_dir / "test_gradio_launch.py", "Gradio Integration Test")
    ]
    
    # Track results
    results = []
    
    # Run each test
    for script_path, description in test_scripts:
        if script_path.exists():
            success = run_test_script(script_path, description)
            results.append((description, success))
        else:
            print(f"⚠️ Test script not found: {script_path}")
            results.append((description, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 TEST SUITE SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {description}")
    
    print(f"\nOverall Results: {passed}/{total} test suites passed")
    
    # Clean up test artifacts
    print(f"\n🧹 Cleaning up test artifacts...")
    cleanup_test_artifacts()
    
    if passed == total:
        print("🎉 All test suites passed! The video compression system is working correctly.")
        return 0
    else:
        print("⚠️ Some test suites failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)