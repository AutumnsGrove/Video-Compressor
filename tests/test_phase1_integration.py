#!/usr/bin/env python3
"""
Test Phase 1 Integration - Verify pipeline integrates with existing system
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from VideoCompression import ParallelVideoProcessor

def test_phase1_configuration_integration():
    """Test that Phase 1 integrates properly with existing configuration."""
    print("🧪 Testing Phase 1 Configuration Integration...")
    
    try:
        # Load configuration
        config_path = str(Path(__file__).parent.parent / "config.json")
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Verify parallel processing settings exist
        parallel_config = config.get("parallel_processing", {})
        assert "enabled" in parallel_config, "parallel_processing.enabled should exist"
        assert "max_workers" in parallel_config, "parallel_processing.max_workers should exist"
        assert "segment_parallel" in parallel_config, "parallel_processing.segment_parallel should exist"
        
        print(f"   ✓ Configuration has required parallel_processing settings")
        
        # Test processor initialization
        processor = ParallelVideoProcessor(config_path)
        
        # Verify processor has pipeline-related attributes
        assert hasattr(processor, 'parallel_enabled'), "Processor should have parallel_enabled attribute"
        assert hasattr(processor, 'segment_parallel'), "Processor should have segment_parallel attribute"
        assert hasattr(processor, 'max_concurrent_jobs'), "Processor should have max_concurrent_jobs attribute"
        
        print(f"   ✓ Processor has required pipeline attributes")
        print(f"   ✓ parallel_enabled: {processor.parallel_enabled}")
        print(f"   ✓ segment_parallel: {processor.segment_parallel}")
        print(f"   ✓ max_concurrent_jobs: {processor.max_concurrent_jobs}")
        
        # Test method existence
        assert hasattr(processor, '_process_large_files_with_segmentation'), "Should have _process_large_files_with_segmentation method"
        assert hasattr(processor, '_process_large_files_pipeline'), "Should have _process_large_files_pipeline method"
        assert hasattr(processor, '_process_large_files_sequential'), "Should have _process_large_files_sequential method"
        
        print(f"   ✓ Processor has required pipeline methods")
        
        print("✅ Phase 1 configuration integration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Phase 1 configuration integration test failed: {e}")
        return False

def test_pipeline_vs_sequential_decision():
    """Test the decision logic between pipeline and sequential processing."""
    print("🧪 Testing Pipeline vs Sequential Decision Logic...")
    
    try:
        config_path = str(Path(__file__).parent.parent / "config.json")
        processor = ParallelVideoProcessor(config_path)
        
        # Mock the _process_large_files_pipeline and _process_large_files_sequential methods
        # to track which one gets called
        pipeline_called = False
        sequential_called = False
        
        original_pipeline = processor._process_large_files_pipeline
        original_sequential = processor._process_large_files_sequential
        
        def mock_pipeline(*args, **kwargs):
            nonlocal pipeline_called
            pipeline_called = True
            return 0, 0  # processed_count, failed_count
        
        def mock_sequential(*args, **kwargs):
            nonlocal sequential_called
            sequential_called = True
            return 0, 0  # processed_count, failed_count
        
        processor._process_large_files_pipeline = mock_pipeline
        processor._process_large_files_sequential = mock_sequential
        
        # Test Case 1: Multiple files with pipeline enabled should use pipeline
        large_files_multi = ["/fake/file1.mp4", "/fake/file2.mp4"]
        
        # Reset flags
        pipeline_called = False
        sequential_called = False
        
        # Ensure conditions for pipeline are met
        original_segment_parallel = processor.segment_parallel
        original_max_jobs = processor.max_concurrent_jobs
        processor.segment_parallel = True
        processor.max_concurrent_jobs = 4
        
        processor._process_large_files_with_segmentation(large_files_multi)
        
        assert pipeline_called, "Pipeline method should be called for multiple files"
        assert not sequential_called, "Sequential method should not be called for multiple files"
        print(f"   ✓ Multiple files (2) with parallel enabled → Pipeline method called")
        
        # Test Case 2: Single file should use sequential
        large_files_single = ["/fake/file1.mp4"]
        
        # Reset flags
        pipeline_called = False
        sequential_called = False
        
        processor._process_large_files_with_segmentation(large_files_single)
        
        assert not pipeline_called, "Pipeline method should not be called for single file"
        assert sequential_called, "Sequential method should be called for single file"
        print(f"   ✓ Single file with parallel enabled → Sequential method called")
        
        # Test Case 3: Multiple files but segment_parallel disabled should use sequential
        large_files_multi = ["/fake/file1.mp4", "/fake/file2.mp4"]
        
        # Reset flags
        pipeline_called = False
        sequential_called = False
        
        # Disable segment parallel
        processor.segment_parallel = False
        
        processor._process_large_files_with_segmentation(large_files_multi)
        
        assert not pipeline_called, "Pipeline method should not be called when segment_parallel is disabled"
        assert sequential_called, "Sequential method should be called when segment_parallel is disabled"
        print(f"   ✓ Multiple files with segment_parallel disabled → Sequential method called")
        
        # Restore original methods and settings
        processor._process_large_files_pipeline = original_pipeline
        processor._process_large_files_sequential = original_sequential
        processor.segment_parallel = original_segment_parallel
        processor.max_concurrent_jobs = original_max_jobs
        
        print("✅ Pipeline vs Sequential decision logic tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Pipeline vs Sequential decision test failed: {e}")
        return False

def test_existing_methods_still_work():
    """Test that existing methods are not broken by Phase 1 changes."""
    print("🧪 Testing Existing Methods Still Work...")
    
    try:
        config_path = str(Path(__file__).parent.parent / "config.json")
        processor = ParallelVideoProcessor(config_path)
        
        # Test that existing methods exist and are callable
        methods_to_check = [
            'process_files_parallel',
            '_process_small_files_parallel',
            'process_segments_parallel',
            'compress_single_segment',
            'segment_video',
            'merge_compressed_segments'
        ]
        
        for method_name in methods_to_check:
            assert hasattr(processor, method_name), f"Method {method_name} should exist"
            method = getattr(processor, method_name)
            assert callable(method), f"Method {method_name} should be callable"
            print(f"   ✓ Method {method_name} exists and is callable")
        
        # Test that the main process_files_parallel method signature is unchanged
        import inspect
        sig = inspect.signature(processor.process_files_parallel)
        params = list(sig.parameters.keys())
        
        print(f"   All params (including self): {params}")
        
        # Should have self, file_list, dry_run, progress_callback
        assert 'file_list' in params, "process_files_parallel should have file_list parameter"
        assert 'dry_run' in params, "process_files_parallel should have dry_run parameter"
        assert 'progress_callback' in params, "process_files_parallel should have progress_callback parameter"
        
        print(f"   ✓ process_files_parallel method signature has required parameters")
        
        # Test that progress aggregator is still working
        assert hasattr(processor, 'progress_aggregator'), "Processor should have progress_aggregator"
        assert hasattr(processor.progress_aggregator, 'register_worker'), "ProgressAggregator should have register_worker method"
        assert hasattr(processor.progress_aggregator, 'update_worker_progress'), "ProgressAggregator should have update_worker_progress method"
        
        print(f"   ✓ ProgressAggregator functionality preserved")
        
        print("✅ Existing methods compatibility tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Existing methods compatibility test failed: {e}")
        return False

def run_all_integration_tests():
    """Run all Phase 1 integration tests."""
    print("🚀 Running Phase 1 Integration Tests...\n")
    
    tests = [
        test_phase1_configuration_integration,
        test_pipeline_vs_sequential_decision,
        test_existing_methods_still_work
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
    
    print(f"📊 Integration Test Summary:")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📈 Success Rate: {(passed/(passed+failed)*100):.1f}%")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_integration_tests()
    sys.exit(0 if success else 1)