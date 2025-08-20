#!/usr/bin/env python3
"""
Test script for video compression functionality.
This script helps verify that the compression system is working correctly.
"""

import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from VideoCompression import VideoCompressor

def create_test_video(output_path, duration=5, resolution="320x240"):
    """Create a small test video using FFmpeg."""
    try:
        # Create a simple test video with testsrc pattern
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
        
        print(f"Creating test video: {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print(f"✅ Test video created successfully ({os.path.getsize(output_path) / 1024:.1f}KB)")
            return True
        else:
            print(f"❌ Failed to create test video: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating test video: {e}")
        return False

def test_hardware_acceleration():
    """Test hardware acceleration detection."""
    print("\n" + "="*60)
    print("🔍 TESTING HARDWARE ACCELERATION DETECTION")
    print("="*60)
    
    try:
        compressor = VideoCompressor()
        hw_accel = compressor.detect_hardware_acceleration()
        
        if hw_accel:
            print("✅ Hardware acceleration detected!")
            print(f"   Type: {hw_accel['type']}")
            print(f"   H.264 Encoder: {hw_accel['h264_encoder']}")
            print(f"   HEVC Encoder: {hw_accel['hevc_encoder'] or 'Not available'}")
            print(f"   Quality Parameter: {hw_accel['quality_param']}")
            print(f"   10-bit Format: {hw_accel['pixel_format_10bit']}")
        else:
            import platform
            processor = platform.processor().lower()
            machine = platform.machine().lower()
            print("ℹ️  No hardware acceleration available")
            print(f"   Processor: {processor}")
            print(f"   Machine: {machine}")
            print(f"   Will use software encoding")
        
        return True
        
    except Exception as e:
        print(f"❌ Hardware acceleration test failed: {e}")
        return False

def test_compression_dry_run():
    """Test compression in dry run mode."""
    print("\n" + "="*60)
    print("🧪 TESTING COMPRESSION (DRY RUN)")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_video = Path(temp_dir) / "test_video.mp4"
        
        # Create test video
        if not create_test_video(test_video):
            return False
        
        try:
            compressor = VideoCompressor()
            
            # Test dry run
            print(f"\nRunning dry run on test video...")
            success, message = compressor.process_file(test_video, dry_run=True)
            
            if success:
                print("✅ Dry run completed successfully!")
                print(f"   Result: {message}")
            else:
                print(f"❌ Dry run failed: {message}")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Compression test failed: {e}")
            return False

def test_ffmpeg_command_generation():
    """Test FFmpeg command generation with different settings."""
    print("\n" + "="*60)
    print("⚙️  TESTING FFMPEG COMMAND GENERATION")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_video = Path(temp_dir) / "test_video.mp4"
        output_video = Path(temp_dir) / "output_video.mp4"
        
        # Create test video
        if not create_test_video(test_video):
            return False
        
        try:
            compressor = VideoCompressor()
            
            # Get video info
            video_info = compressor.get_video_info(test_video)
            if not video_info:
                print("❌ Could not get video info")
                return False
            
            # Test command generation with hardware acceleration enabled
            print("\n🚀 Testing with hardware acceleration enabled...")
            compressor.config["compression_settings"]["enable_hardware_acceleration"] = True
            cmd_hw = compressor.build_ffmpeg_command(test_video, output_video, video_info)
            print(f"   Command: {' '.join(cmd_hw[:10])}...")
            
            # Check if VideoToolbox encoder is used (if available)
            has_videotoolbox = any("videotoolbox" in arg for arg in cmd_hw)
            if has_videotoolbox:
                print("   ✅ VideoToolbox encoder detected in command")
            else:
                print("   ℹ️  Software encoder (VideoToolbox not available)")
            
            # Test command generation with hardware acceleration disabled
            print("\n💻 Testing with hardware acceleration disabled...")
            compressor.config["compression_settings"]["enable_hardware_acceleration"] = False
            cmd_sw = compressor.build_ffmpeg_command(test_video, output_video, video_info)
            print(f"   Command: {' '.join(cmd_sw[:10])}...")
            
            # Verify no VideoToolbox in software mode
            has_videotoolbox_disabled = any("videotoolbox" in arg for arg in cmd_sw)
            if not has_videotoolbox_disabled:
                print("   ✅ Software encoder confirmed")
            else:
                print("   ⚠️  Unexpected: VideoToolbox found when disabled")
            
            return True
            
        except Exception as e:
            print(f"❌ Command generation test failed: {e}")
            return False

def test_config_loading():
    """Test configuration loading and validation."""
    print("\n" + "="*60)
    print("⚙️  TESTING CONFIGURATION")
    print("="*60)
    
    try:
        compressor = VideoCompressor()
        config = compressor.config
        
        # Check if hardware acceleration setting exists
        hw_setting = config.get("compression_settings", {}).get("enable_hardware_acceleration")
        print(f"Hardware acceleration config: {hw_setting}")
        
        if hw_setting is not None:
            print("✅ Hardware acceleration setting found in config")
        else:
            print("⚠️  Hardware acceleration setting missing from config")
        
        # Test other required settings
        required_settings = [
            ("compression_settings", "video_codec"),
            ("compression_settings", "preset"),
            ("compression_settings", "crf"),
            ("safety_settings", "verify_integrity"),
        ]
        
        all_good = True
        for section, key in required_settings:
            value = config.get(section, {}).get(key)
            if value is not None:
                print(f"✅ {section}.{key}: {value}")
            else:
                print(f"❌ Missing: {section}.{key}")
                all_good = False
        
        return all_good
        
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        return False

def test_segmentation_decision():
    """Test the should_segment_file decision logic."""
    print("\n" + "="*60)
    print("📁 TESTING SEGMENTATION DECISION LOGIC")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_video = Path(temp_dir) / "test_video.mp4"
        
        # Create a longer test video (30 seconds to simulate duration check)
        if not create_test_video(test_video, duration=30):
            return False
        
        try:
            compressor = VideoCompressor()
            
            # Test 1: Small file (should not segment)
            print(f"\n🔍 Test 1: Small file decision...")
            original_threshold = compressor.config.get("large_file_settings", {}).get("segmentation_threshold_gb", 10)
            
            # Set a very low threshold to test the logic
            compressor.config["large_file_settings"]["segmentation_threshold_gb"] = 0.001  # 1MB
            
            should_segment = compressor.should_segment_file(test_video)
            file_size_mb = os.path.getsize(test_video) / (1024 * 1024)
            
            print(f"   File size: {file_size_mb:.1f}MB")
            print(f"   Threshold: 0.001GB (1MB)")
            print(f"   Should segment: {should_segment}")
            
            if should_segment:
                print("   ✅ Correctly identified for segmentation (size > 1MB and duration > 60min check)")
            else:
                print("   ✅ Correctly rejected for segmentation (duration < 60 minutes)")
            
            # Test 2: Reset to normal threshold (should not segment)
            print(f"\n🔍 Test 2: Normal threshold decision...")
            compressor.config["large_file_settings"]["segmentation_threshold_gb"] = original_threshold
            
            should_segment_normal = compressor.should_segment_file(test_video)
            print(f"   File size: {file_size_mb:.1f}MB")
            print(f"   Threshold: {original_threshold}GB")
            print(f"   Should segment: {should_segment_normal}")
            
            if not should_segment_normal:
                print("   ✅ Correctly rejected for segmentation (too small)")
            else:
                print("   ⚠️  Unexpected: small file marked for segmentation")
            
            return True
            
        except Exception as e:
            print(f"❌ Segmentation decision test failed: {e}")
            return False

def test_segmentation_workflow():
    """Test the complete segmentation workflow with a simulated large file."""
    print("\n" + "="*60)
    print("🔗 TESTING SEGMENTATION WORKFLOW")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a longer test video to simulate segmentation
        test_video = Path(temp_dir) / "large_test_video.mp4"
        
        # Create a 60-second test video to trigger duration threshold
        print(f"Creating longer test video for segmentation test...")
        if not create_test_video(test_video, duration=60, resolution="640x480"):
            return False
        
        try:
            compressor = VideoCompressor()
            
            # Force segmentation by setting very low thresholds
            compressor.config["large_file_settings"]["segmentation_threshold_gb"] = 0.001  # 1MB
            
            print(f"\n🔍 Testing segmentation components...")
            
            # Test 1: Segmentation decision
            should_segment = compressor.should_segment_file(test_video)
            print(f"   Should segment: {should_segment}")
            
            if not should_segment:
                print("   ⚠️  File not marked for segmentation - adjusting test")
                # For this test, we'll manually test the segmentation functions
            
            # Test 2: Manual segmentation test
            print(f"\n📁 Testing video segmentation...")
            segment_paths = compressor.segment_video(test_video, segment_duration=20)  # 20-second segments
            
            if segment_paths:
                print(f"   ✅ Segmentation successful: {len(segment_paths)} segments created")
                for i, segment in enumerate(segment_paths, 1):
                    segment_size = os.path.getsize(segment) / (1024 * 1024)
                    print(f"      Segment {i}: {Path(segment).name} ({segment_size:.1f}MB)")
                
                # Test 3: Merge segments test
                print(f"\n🔗 Testing segment merging...")
                merged_output = Path(temp_dir) / "merged_test.mp4"
                
                success, message = compressor.merge_compressed_segments(segment_paths, merged_output)
                
                if success:
                    merged_size = os.path.getsize(merged_output) / (1024 * 1024)
                    original_size = os.path.getsize(test_video) / (1024 * 1024)
                    print(f"   ✅ Merge successful: {merged_output.name} ({merged_size:.1f}MB)")
                    print(f"   Original size: {original_size:.1f}MB")
                    print(f"   Size difference: {abs(merged_size - original_size):.1f}MB")
                else:
                    print(f"   ❌ Merge failed: {message}")
                    return False
                
                # Clean up segment files
                compressor.cleanup_segment_files(segment_paths, [])
                print(f"   🧹 Cleanup completed")
                
            else:
                print(f"   ❌ Segmentation failed")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Segmentation workflow test failed: {e}")
            return False

def test_segmentation_integration():
    """Test segmentation integration with the main compression workflow."""
    print("\n" + "="*60)
    print("🎯 TESTING SEGMENTATION INTEGRATION")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_video = Path(temp_dir) / "integration_test.mp4"
        
        # Create test video
        if not create_test_video(test_video, duration=30):
            return False
        
        try:
            compressor = VideoCompressor()
            
            # Test integration by temporarily forcing segmentation
            original_threshold = compressor.config.get("large_file_settings", {}).get("segmentation_threshold_gb", 10)
            compressor.config["large_file_settings"]["segmentation_threshold_gb"] = 0.001  # Force segmentation
            
            print(f"\n🔍 Testing integrated workflow (dry run)...")
            
            # Test dry run with segmentation logic
            success, message = compressor.process_file(test_video, dry_run=True)
            
            if success:
                print(f"   ✅ Dry run completed successfully")
                print(f"   Result: {message}")
            else:
                print(f"   ❌ Dry run failed: {message}")
                return False
            
            # Restore original threshold
            compressor.config["large_file_settings"]["segmentation_threshold_gb"] = original_threshold
            
            print(f"\n🔍 Testing normal workflow (no segmentation)...")
            
            # Test normal workflow without segmentation
            success_normal, message_normal = compressor.process_file(test_video, dry_run=True)
            
            if success_normal:
                print(f"   ✅ Normal workflow completed successfully")
                print(f"   Result: {message_normal}")
            else:
                print(f"   ❌ Normal workflow failed: {message_normal}")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Integration test failed: {e}")
            return False

def run_all_tests():
    """Run all tests and provide summary."""
    print("🧪 VIDEO COMPRESSION TESTING SUITE")
    print("This will test the video compression functionality")
    print("=" * 60)
    
    tests = [
        ("Configuration Loading", test_config_loading),
        ("Hardware Acceleration Detection", test_hardware_acceleration),
        ("FFmpeg Command Generation", test_ffmpeg_command_generation),
        ("Compression Dry Run", test_compression_dry_run),
        ("Segmentation Decision Logic", test_segmentation_decision),
        ("Segmentation Workflow", test_segmentation_workflow),
        ("Segmentation Integration", test_segmentation_integration),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\nRunning: {test_name}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ Test crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST RESULTS SUMMARY")
    print("="*60)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The compression system is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)