#!/usr/bin/env python3
"""
Quick test to launch Gradio and verify the enhanced progress tracking shows up in the UI.
"""

import os
import sys
import tempfile
import subprocess
import atexit
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def create_test_video(output_path, duration=30, resolution="640x480"):
    """Create a test video for demonstrating progress tracking."""
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
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.returncode == 0
    except Exception:
        return False

# Create test videos for demonstration
test_dir = Path(__file__).parent / "test_gradio_demo"
test_dir.mkdir(exist_ok=True)

# Cleanup function to remove test files
def cleanup_test_files():
    """Remove test video files after script completion."""
    try:
        if test_dir.exists():
            import shutil
            shutil.rmtree(test_dir)
            print(f"🧹 Cleaned up test files: {test_dir}")
    except Exception as e:
        print(f"⚠️ Could not clean up test files: {e}")

# Register cleanup to run when script exits
atexit.register(cleanup_test_files)

print("🎬 Creating test videos for Gradio demo...")

# Create a few test videos
small_video = test_dir / "small_test.mp4"
medium_video = test_dir / "medium_test.mp4"
long_video = test_dir / "long_test.mp4"

videos_created = []

if not small_video.exists():
    print(f"📁 Creating small test video...")
    if create_test_video(small_video, duration=5, resolution="320x240"):
        videos_created.append(small_video)
        print(f"   ✅ Created: {small_video.name} ({os.path.getsize(small_video) / (1024*1024):.1f}MB)")

if not medium_video.exists():
    print(f"📁 Creating medium test video...")
    if create_test_video(medium_video, duration=15, resolution="640x480"):
        videos_created.append(medium_video)
        print(f"   ✅ Created: {medium_video.name} ({os.path.getsize(medium_video) / (1024*1024):.1f}MB)")

if not long_video.exists():
    print(f"📁 Creating longer test video...")
    if create_test_video(long_video, duration=30, resolution="720x480"):
        videos_created.append(long_video)
        print(f"   ✅ Created: {long_video.name} ({os.path.getsize(long_video) / (1024*1024):.1f}MB)")

print(f"\n🎯 Test videos ready in: {test_dir.absolute()}")
print(f"📋 You can paste these paths into Gradio:")
for video in videos_created:
    print(f"   {video.absolute()}")

print(f"\n🔧 Recommended test procedure:")
print(f"1. Launch Gradio: python GradioVideoCompression.py")
print(f"2. Paste the paths above into the 'Video File Paths' field")  
print(f"3. Enable 'Dry Run Mode' to test enhanced progress tracking")
print(f"4. Click 'Process Videos' to see worker allocation simulation")
print(f"5. Look for enhanced progress info showing worker counts and ETA")

print(f"\n🧪 What to expect in dry run:")
print(f"- Enhanced worker allocation display")
print(f"- Progress bars showing X/Y workers active") 
print(f"- Throughput and ETA information")
print(f"- Detailed file analysis for each video")

# Also test the actual import to make sure there are no errors
try:
    print(f"\n🔍 Testing Gradio module import...")
    from GradioVideoCompression import create_interface
    print(f"   ✅ GradioVideoCompression imports successfully")
    
    interface = create_interface()
    print(f"   ✅ Interface creation successful")
    print(f"   🚀 Ready to launch Gradio!")
    
except Exception as e:
    print(f"   ❌ Import error: {e}")
    print(f"   🔧 Check that all dependencies are installed")

print(f"\n💡 To launch Gradio now, run:")
print(f"   python GradioVideoCompression.py")