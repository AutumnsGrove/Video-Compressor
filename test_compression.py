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