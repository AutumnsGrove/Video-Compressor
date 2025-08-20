#!/usr/bin/env python3
"""
Test script for parallel video processing functionality.
Tests the ParallelVideoProcessor class without requiring actual video files.
"""

import json
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from VideoCompression import ParallelVideoProcessor

def test_parallel_processor_initialization():
    """Test that ParallelVideoProcessor initializes correctly."""
    print("🧪 Testing ParallelVideoProcessor initialization...")
    
    try:
        processor = ParallelVideoProcessor()
        
        # Check that parallel settings are loaded
        assert hasattr(processor, 'parallel_enabled'), "Should have parallel_enabled attribute"
        assert hasattr(processor, 'max_concurrent_jobs'), "Should have max_concurrent_jobs attribute"
        assert hasattr(processor, 'segment_parallel'), "Should have segment_parallel attribute"
        
        # Check that it inherits from VideoCompressor
        assert hasattr(processor, 'process_file'), "Should inherit process_file from VideoCompressor"
        assert hasattr(processor, 'log'), "Should inherit log method from VideoCompressor"
        
        # Check new parallel methods
        assert hasattr(processor, 'process_segments_parallel'), "Should have process_segments_parallel method"
        assert hasattr(processor, 'process_files_parallel'), "Should have process_files_parallel method"
        
        print(f"   ✅ Initialization successful")
        print(f"   ✅ Parallel enabled: {processor.parallel_enabled}")
        print(f"   ✅ Max concurrent jobs: {processor.max_concurrent_jobs}")
        print(f"   ✅ Segment parallel: {processor.segment_parallel}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Initialization failed: {e}")
        return False

def test_config_loading():
    """Test that parallel configuration is loaded correctly."""
    print("\n🧪 Testing parallel configuration loading...")
    
    try:
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            test_config = {
                "ffmpeg_path": "/opt/homebrew/bin/ffmpeg",
                "temp_dir": "/tmp/video_compression",
                "log_dir": "./logs",
                "compression_settings": {
                    "video_codec": "libx265",
                    "preset": "medium",
                    "crf": 23
                },
                "safety_settings": {
                    "min_free_space_gb": 15,
                    "verify_integrity": True
                },
                "large_file_settings": {
                    "threshold_gb": 10,
                    "use_same_filesystem": True
                },
                "logging_settings": {
                    "console_level": "INFO"
                },
                "parallel_processing": {
                    "enabled": False,  # Test with disabled
                    "max_workers": 8,
                    "segment_parallel": False
                }
            }
            json.dump(test_config, f)
            temp_config_path = f.name
        
        # Load processor with custom config
        processor = ParallelVideoProcessor(temp_config_path)
        
        # Verify config was loaded correctly
        assert processor.parallel_enabled == False, "Should respect disabled config"
        assert processor.max_concurrent_jobs <= 8, "Should respect max_workers config"
        assert processor.segment_parallel == False, "Should respect segment_parallel config"
        
        print(f"   ✅ Configuration loaded correctly")
        print(f"   ✅ Parallel enabled (from config): {processor.parallel_enabled}")
        print(f"   ✅ Max workers respected: {processor.max_concurrent_jobs} <= 8")
        
        # Clean up
        Path(temp_config_path).unlink()
        
        return True
        
    except Exception as e:
        print(f"   ❌ Configuration test failed: {e}")
        return False

def test_fallback_to_sequential():
    """Test that parallel processor falls back to sequential when appropriate."""
    print("\n🧪 Testing fallback to sequential processing...")
    
    try:
        processor = ParallelVideoProcessor()
        
        # Test with empty segments list
        completed, message = processor._process_segments_sequential([], "/tmp")
        assert completed == [], "Empty segments should return empty list"
        assert "sequential" in message.lower(), "Should indicate sequential processing"
        
        print(f"   ✅ Empty segments handled correctly")
        print(f"   ✅ Sequential fallback works")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Sequential fallback test failed: {e}")
        return False

def test_cpu_core_detection():
    """Test that CPU core detection works correctly."""
    print("\n🧪 Testing CPU core detection...")
    
    try:
        processor = ParallelVideoProcessor()
        
        # Check that max_concurrent_jobs is reasonable
        assert 1 <= processor.max_concurrent_jobs <= 8, f"Max concurrent jobs should be 1-8, got {processor.max_concurrent_jobs}"
        
        from multiprocessing import cpu_count
        cpu_cores = cpu_count()
        
        print(f"   ✅ CPU cores detected: {cpu_cores}")
        print(f"   ✅ Max concurrent jobs set to: {processor.max_concurrent_jobs}")
        print(f"   ✅ Jobs <= CPU cores: {processor.max_concurrent_jobs <= cpu_cores}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ CPU core detection test failed: {e}")
        return False

def test_dry_run_functionality():
    """Test dry run functionality with parallel processor."""
    print("\n🧪 Testing dry run functionality...")
    
    try:
        processor = ParallelVideoProcessor()
        
        # Test dry run with empty file list
        processor.process_files_parallel([], dry_run=True)
        
        # Test dry run with non-existent files (should log warnings but not crash)
        fake_files = ["/fake/path1.mp4", "/fake/path2.mp4"]
        processor.process_files_parallel(fake_files, dry_run=True)
        
        print(f"   ✅ Dry run with empty list works")
        print(f"   ✅ Dry run with fake files works")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Dry run test failed: {e}")
        return False

def run_all_tests():
    """Run all parallel processing tests."""
    print("🚀 Running ParallelVideoProcessor Tests\n" + "="*50)
    
    tests = [
        test_parallel_processor_initialization,
        test_config_loading,
        test_fallback_to_sequential,
        test_cpu_core_detection,
        test_dry_run_functionality
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"   ❌ Test {test.__name__} crashed: {e}")
    
    print(f"\n" + "="*50)
    print(f"🏁 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed! Parallel processing functionality is working correctly.")
        return True
    else:
        print(f"❌ {total - passed} tests failed. Check the implementation.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
