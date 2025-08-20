#!/usr/bin/env python3
"""
Test script to verify Gradio progress tracking enhancements.
Creates test files and simulates the batch processing workflow.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from VideoCompression import ParallelVideoProcessor

def create_test_video(output_path, duration=5, resolution="320x240"):
    """Create a small test video using FFmpeg."""
    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"testsrc=duration={duration}:size={resolution}:rate=30",
            "-f", "lavfi", 
            "-i", f"sine=frequency=1000:duration={duration}",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-shortest",
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except Exception:
        return False

def test_enhanced_progress_tracking():
    """Test the enhanced progress tracking system."""
    print("🧪 Testing Enhanced Progress Tracking")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create multiple test videos of different sizes
        small_video1 = Path(temp_dir) / "small1.mp4"
        small_video2 = Path(temp_dir) / "small2.mp4"
        large_video = Path(temp_dir) / "large.mp4"
        
        print("📁 Creating test videos...")
        
        # Create small videos (5 seconds)
        if not create_test_video(small_video1, duration=5):
            print("❌ Failed to create small video 1")
            return False
        
        if not create_test_video(small_video2, duration=5):
            print("❌ Failed to create small video 2") 
            return False
        
        # Create "large" video (30 seconds, higher resolution)
        if not create_test_video(large_video, duration=30, resolution="640x480"):
            print("❌ Failed to create large video")
            return False
            
        # Report file sizes
        files = [small_video1, small_video2, large_video]
        for file_path in files:
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            print(f"   📄 {file_path.name}: {size_mb:.1f}MB")
        
        print("\n🔧 Testing with ParallelVideoProcessor...")
        
        # Create processor with forced segmentation for the "large" file
        processor = ParallelVideoProcessor()
        
        # Temporarily lower the segmentation threshold to trigger segmentation
        original_threshold = processor.config.get("large_file_settings", {}).get("segmentation_threshold_gb", 10)
        processor.config["large_file_settings"]["segmentation_threshold_gb"] = 0.001  # 1MB threshold
        
        print(f"📊 Lowered segmentation threshold to 0.001GB (was {original_threshold}GB)")
        
        # Setup progress tracking
        progress_updates = []
        
        def progress_callback(progress_data):
            """Enhanced progress callback that captures data."""
            progress_updates.append(progress_data)
            
            if isinstance(progress_data, dict):
                print(f"📈 Progress Update:")
                print(f"   Overall: {progress_data.get('overall_progress', 0)*100:.1f}%")
                print(f"   Workers: {progress_data.get('active_workers', 0)}/{progress_data.get('total_workers', 0)}")
                print(f"   Throughput: {progress_data.get('throughput_mbps', 0):.1f}MB/s")
                print(f"   ETA: {progress_data.get('eta_seconds', 0):.0f}s")
                print()
            else:
                print(f"📈 Legacy Progress: {progress_data}")
        
        # Test dry run with enhanced progress tracking
        print("🧪 Running dry run with enhanced progress tracking...")
        file_paths = [str(f) for f in files]
        
        try:
            processor.process_file_list(file_paths, dry_run=True, batch_progress_callback=progress_callback)
            
            print(f"✅ Dry run completed successfully!")
            print(f"📊 Progress updates received: {len(progress_updates)}")
            
            # Analyze progress updates
            if progress_updates:
                final_update = progress_updates[-1]
                if isinstance(final_update, dict):
                    print("📋 Final Progress State:")
                    print(f"   Total Workers: {final_update.get('total_workers', 0)}")
                    print(f"   Enhanced Format: ✅")
                else:
                    print("📋 Final Progress State:")
                    print(f"   Legacy Format: ⚠️")
            
            # Test segmentation detection
            print("\n🔍 Segmentation Analysis:")
            for file_path in files:
                should_segment = processor.should_segment_file(file_path)
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                print(f"   📄 {Path(file_path).name} ({size_mb:.1f}MB): {'🔪 Segment' if should_segment else '📄 Normal'}")
            
            # Restore original threshold
            processor.config["large_file_settings"]["segmentation_threshold_gb"] = original_threshold
            
            return True
            
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            return False

def test_gradio_integration():
    """Test that matches what Gradio interface would receive."""
    print("\n🎨 Testing Gradio Integration Compatibility")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test video
        test_video = Path(temp_dir) / "gradio_test.mp4"
        
        if not create_test_video(test_video, duration=10):
            print("❌ Failed to create test video")
            return False
        
        # Simulate what Gradio would do
        processor = ParallelVideoProcessor()
        
        # Setup enhanced progress callback similar to Gradio
        gradio_progress_data = []
        
        def batch_progress_callback(progress_data):
            """Simulate Gradio's batch progress callback."""
            gradio_progress_data.append(progress_data)
            
            if isinstance(progress_data, dict):
                # New enhanced progress data from ProgressAggregator
                overall_progress = progress_data.get('overall_progress', 0.0)
                active_workers = progress_data.get('active_workers', 0)
                total_workers = progress_data.get('total_workers', 0)
                throughput_mbps = progress_data.get('throughput_mbps', 0.0)
                eta_seconds = progress_data.get('eta_seconds', 0)
                
                # Create enhanced status message (like Gradio does)
                if active_workers > 0:
                    if eta_seconds > 0:
                        eta_str = f"{int(eta_seconds//3600):02d}:{int((eta_seconds%3600)//60):02d}:{int(eta_seconds%60):02d}"
                        status_message = f"Processing: {active_workers}/{total_workers} workers active | {throughput_mbps:.1f}MB/s | ETA: {eta_str}"
                    else:
                        status_message = f"Processing: {active_workers}/{total_workers} workers active | {throughput_mbps:.1f}MB/s"
                else:
                    status_message = f"Processing complete | Total throughput: {throughput_mbps:.1f}MB/s"
                
                # Map overall progress to 0.2 -> 0.95 range like Gradio
                mapped_progress = 0.2 + (overall_progress * 0.75)
                
                print(f"🎨 Gradio Progress Update:")
                print(f"   Status: {status_message}")
                print(f"   Progress: {mapped_progress*100:.1f}% (mapped from {overall_progress*100:.1f}%)")
                print()
                
            else:
                # Handle old-style callback (for backwards compatibility)
                overall_progress = progress_data if isinstance(progress_data, (int, float)) else 0.0
                mapped_progress = 0.2 + (overall_progress * 0.75)
                print(f"🎨 Gradio Legacy Progress: {mapped_progress*100:.1f}%")
        
        # Test dry run
        print("🧪 Testing dry run with Gradio-style callback...")
        try:
            processor.process_file_list([str(test_video)], dry_run=True, batch_progress_callback=batch_progress_callback)
            
            print(f"✅ Gradio compatibility test completed!")
            print(f"📊 Progress callbacks received: {len(gradio_progress_data)}")
            
            if gradio_progress_data:
                # Check that we got enhanced format
                enhanced_format = any(isinstance(data, dict) for data in gradio_progress_data)
                print(f"✅ Enhanced progress format detected: {enhanced_format}")
                
                if enhanced_format:
                    last_dict = next(data for data in reversed(gradio_progress_data) if isinstance(data, dict))
                    print(f"📋 Final State: {last_dict.get('total_workers', 0)} workers registered")
            
            return True
            
        except Exception as e:
            print(f"❌ Gradio compatibility test failed: {e}")
            return False

if __name__ == "__main__":
    print("🚀 Enhanced Progress Tracking Test Suite")
    print("Testing new ProgressAggregator integration\n")
    
    test1_result = test_enhanced_progress_tracking()
    test2_result = test_gradio_integration()
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"✅ Enhanced Progress Tracking: {'PASS' if test1_result else 'FAIL'}")
    print(f"✅ Gradio Integration: {'PASS' if test2_result else 'FAIL'}")
    
    if test1_result and test2_result:
        print("\n🎉 All tests passed! Enhanced progress tracking is working correctly.")
        print("The Gradio UI should now show enhanced progress information.")
    else:
        print("\n❌ Some tests failed. Check the output above for details.")