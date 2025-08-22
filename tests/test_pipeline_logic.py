#!/usr/bin/env python3
"""
Test Phase 1 Pipeline Logic - Verify decision-making and flow control
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from VideoCompression import ParallelVideoProcessor

def test_pipeline_decision_logic():
    """Test when pipeline parallelism should be enabled vs disabled."""
    print("🧪 Testing Pipeline Decision Logic...")
    
    try:
        config_path = str(Path(__file__).parent.parent / "config.json")
        processor = ParallelVideoProcessor(config_path)
        
        # Test Case 1: Single large file (should use sequential)
        large_files_single = ["/fake/large_file1.mp4"]
        pipeline_enabled = (
            processor.segment_parallel and 
            len(large_files_single) > 1 and 
            processor.max_concurrent_jobs > 1
        )
        print(f"   Single large file → Pipeline enabled: {pipeline_enabled} (Expected: False)")
        assert not pipeline_enabled, "Pipeline should be disabled for single file"
        
        # Test Case 2: Multiple large files with parallel enabled (should use pipeline)
        large_files_multi = ["/fake/large_file1.mp4", "/fake/large_file2.mp4", "/fake/large_file3.mp4"]
        pipeline_enabled = (
            processor.segment_parallel and 
            len(large_files_multi) > 1 and 
            processor.max_concurrent_jobs > 1
        )
        print(f"   Multiple large files → Pipeline enabled: {pipeline_enabled} (Expected: True)")
        assert pipeline_enabled, "Pipeline should be enabled for multiple files"
        
        # Test Case 3: Multiple files but only 1 worker (should use sequential)
        original_workers = processor.max_concurrent_jobs
        processor.max_concurrent_jobs = 1  # Temporarily set to 1
        pipeline_enabled = (
            processor.segment_parallel and 
            len(large_files_multi) > 1 and 
            processor.max_concurrent_jobs > 1
        )
        print(f"   Multiple files, 1 worker → Pipeline enabled: {pipeline_enabled} (Expected: False)")
        assert not pipeline_enabled, "Pipeline should be disabled with only 1 worker"
        processor.max_concurrent_jobs = original_workers  # Restore
        
        # Test Case 4: Multiple files but segment_parallel disabled
        original_segment_parallel = processor.segment_parallel
        processor.segment_parallel = False  # Temporarily disable
        pipeline_enabled = (
            processor.segment_parallel and 
            len(large_files_multi) > 1 and 
            processor.max_concurrent_jobs > 1
        )
        print(f"   Segment parallel disabled → Pipeline enabled: {pipeline_enabled} (Expected: False)")
        assert not pipeline_enabled, "Pipeline should be disabled when segment_parallel is False"
        processor.segment_parallel = original_segment_parallel  # Restore
        
        print("✅ Pipeline decision logic tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Pipeline decision logic test failed: {e}")
        return False

def test_file_status_tracking():
    """Test that file status tracking structure is properly initialized."""
    print("🧪 Testing File Status Tracking Structure...")
    
    try:
        # Simulate the file status initialization from pipeline method
        large_files = ["/fake/file1.mp4", "/fake/file2.mp4"]
        file_status = {}
        
        # Initialize file tracking (from pipeline implementation)
        for file_path in large_files:
            file_status[file_path] = {
                'status': 'pending',
                'segments': [],
                'compressed_segments': [],
                'error': None
            }
        
        # Verify structure
        assert len(file_status) == 2, "Should track 2 files"
        
        for file_path, status in file_status.items():
            assert status['status'] == 'pending', f"Initial status should be 'pending' for {file_path}"
            assert status['segments'] == [], f"Segments should be empty initially for {file_path}"
            assert status['compressed_segments'] == [], f"Compressed segments should be empty initially for {file_path}"
            assert status['error'] is None, f"Error should be None initially for {file_path}"
            print(f"   ✓ File status structure correct for {file_path}")
        
        # Test status transitions
        file_status[large_files[0]]['status'] = 'segmenting'
        assert file_status[large_files[0]]['status'] == 'segmenting', "Status should update correctly"
        
        file_status[large_files[0]]['segments'] = ['seg1.mp4', 'seg2.mp4']
        assert len(file_status[large_files[0]]['segments']) == 2, "Segments should be tracked"
        
        print("✅ File status tracking structure tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ File status tracking test failed: {e}")
        return False

def test_queue_configuration():
    """Test queue size and configuration parameters."""
    print("🧪 Testing Queue Configuration...")
    
    try:
        import queue
        
        # Test queue creation with proper size limit (from pipeline implementation)
        segment_queue = queue.Queue(maxsize=50)
        
        # Verify queue properties
        assert segment_queue.maxsize == 50, "Queue should have maxsize of 50"
        assert segment_queue.empty(), "Queue should be empty initially"
        
        # Test adding items up to limit
        for i in range(10):
            test_item = {'type': 'segment', 'data': f'test_{i}'}
            segment_queue.put(test_item, block=False)  # Non-blocking
        
        assert segment_queue.qsize() == 10, "Queue should contain 10 items"
        assert not segment_queue.empty(), "Queue should not be empty"
        assert not segment_queue.full(), "Queue should not be full with 10/50 items"
        
        # Test retrieving items
        first_item = segment_queue.get(block=False)
        assert first_item['data'] == 'test_0', "Should retrieve items in FIFO order"
        assert segment_queue.qsize() == 9, "Queue size should decrease after get"
        
        print(f"   ✓ Queue configured with maxsize=50")
        print(f"   ✓ Queue FIFO behavior verified")
        print(f"   ✓ Queue size tracking works correctly")
        
        print("✅ Queue configuration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Queue configuration test failed: {e}")
        return False

def run_all_pipeline_tests():
    """Run all Phase 1 pipeline tests."""
    print("🚀 Running Phase 1 Pipeline Logic Tests...\n")
    
    tests = [
        test_pipeline_decision_logic,
        test_file_status_tracking,
        test_queue_configuration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
        print()  # Add spacing between tests
    
    print(f"📊 Test Summary:")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📈 Success Rate: {(passed/(passed+failed)*100):.1f}%")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_pipeline_tests()
    sys.exit(0 if success else 1)