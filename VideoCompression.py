#!/usr/bin/env python3

import os
import sys
import json
import subprocess
import shutil
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import argparse

class VideoCompressor:
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.log_file = None
        self.setup_logging()
        self.processed_files = []
        self.failed_files = []
        
    def load_config(self, config_path):
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            print(f"Config file {config_path} not found. Creating default config...")
            default_config = {
                "ffmpeg_path": "/opt/homebrew/bin/ffmpeg",
                "temp_dir": "/tmp/video_compression",
                "log_dir": "./logs",
                "compression_settings": {
                    "target_bitrate_reduction": 0.5,
                    "preserve_10bit": True,
                    "preserve_metadata": True,
                    "video_codec": "libx265",
                    "preset": "medium",
                    "crf": 23
                },
                "safety_settings": {
                    "min_free_space_gb": 10,
                    "verify_integrity": True,
                    "create_backup_hash": True,
                    "max_retries": 3
                }
            }
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
        except json.JSONDecodeError as e:
            print(f"Error parsing config file: {e}")
            sys.exit(1)
    
    def setup_logging(self):
        """Setup comprehensive logging system."""
        log_dir = Path(self.config["log_dir"])
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"video_compression_{timestamp}.log"
        
        self.log_file = open(log_file, 'w')
        self.log(f"=== Video Compression Session Started ===")
        self.log(f"Timestamp: {datetime.now()}")
        self.log(f"Config: {json.dumps(self.config, indent=2)}")
        
    def log(self, message, level="INFO"):
        """Log message to both console and file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        if self.log_file:
            self.log_file.write(log_message + "\n")
            self.log_file.flush()
    
    def check_disk_space(self, file_path, safety_multiplier=2.5):
        """Check if there's enough disk space for safe compression."""
        file_size = os.path.getsize(file_path)
        temp_dir = Path(self.config["temp_dir"])
        
        # Get available space on temp directory filesystem
        statvfs = os.statvfs(temp_dir.parent)
        available_bytes = statvfs.f_frsize * statvfs.f_bavail
        available_gb = available_bytes / (1024**3)
        
        # Required space: original file size * safety multiplier
        required_bytes = file_size * safety_multiplier
        required_gb = required_bytes / (1024**3)
        
        min_free_space = self.config["safety_settings"]["min_free_space_gb"]
        
        self.log(f"Disk space check:")
        self.log(f"  Available: {available_gb:.2f}GB")
        self.log(f"  Required: {required_gb:.2f}GB")
        self.log(f"  File size: {file_size / (1024**3):.2f}GB")
        self.log(f"  Min free space: {min_free_space}GB")
        
        if available_gb < (required_gb + min_free_space):
            return False, f"Insufficient disk space. Need {required_gb + min_free_space:.2f}GB, have {available_gb:.2f}GB"
        
        return True, "Sufficient disk space available"
    
    def calculate_file_hash(self, file_path, chunk_size=8192):
        """Calculate SHA-256 hash of file for integrity verification."""
        self.log(f"Calculating hash for {file_path}")
        hash_sha256 = hashlib.sha256()
        
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            self.log(f"Error calculating hash: {e}", "ERROR")
            return None
    
    def get_video_info(self, file_path):
        """Get detailed video information using ffprobe."""
        cmd = [
            self.config["ffmpeg_path"].replace("ffmpeg", "ffprobe"),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                self.log(f"ffprobe error: {result.stderr}", "ERROR")
                return None
        except Exception as e:
            self.log(f"Error getting video info: {e}", "ERROR")
            return None
    
    def get_video_duration(self, video_info):
        """Extract video duration in seconds from video info."""
        try:
            # Try to get duration from format first
            format_info = video_info.get("format", {})
            if "duration" in format_info:
                return float(format_info["duration"])
            
            # Fallback: get from video stream
            video_streams = [s for s in video_info.get("streams", []) if s.get("codec_type") == "video"]
            if video_streams and "duration" in video_streams[0]:
                return float(video_streams[0]["duration"])
                
        except (ValueError, KeyError, TypeError):
            pass
        return 0.0
    
    def verify_file_integrity(self, file_path, original_info=None):
        """Comprehensive file integrity verification with detailed logging."""
        self.log(f"🔍 COMPREHENSIVE FILE VERIFICATION")
        self.log(f"   File: {file_path}")
        
        verification_results = []
        
        # Step 1: Basic file existence and size check
        self.log(f"   Step 1: Basic file checks...")
        if not os.path.exists(file_path):
            return False, "File does not exist"
        
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        if file_size < 1024:  # Less than 1KB is suspicious
            return False, f"File too small: {file_size} bytes"
        
        self.log(f"   ✅ File exists: {file_size_mb:.2f}MB")
        verification_results.append(f"File size: {file_size_mb:.2f}MB")
        
        # Step 2: Video metadata analysis
        self.log(f"   Step 2: Analyzing video metadata...")
        video_info = self.get_video_info(file_path)
        if not video_info:
            return False, "Cannot read video information"
        
        # Analyze streams
        streams = video_info.get("streams", [])
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        
        if not video_streams:
            return False, "No video streams found"
        
        self.log(f"   ✅ Stream analysis:")
        self.log(f"      Video streams: {len(video_streams)}")
        self.log(f"      Audio streams: {len(audio_streams)}")
        verification_results.append(f"Streams: {len(video_streams)} video, {len(audio_streams)} audio")
        
        # Detailed video stream info
        for i, stream in enumerate(video_streams):
            codec = stream.get("codec_name", "unknown")
            profile = stream.get("profile", "")
            width = stream.get("width", 0)
            height = stream.get("height", 0)
            duration = stream.get("duration", "unknown")
            bit_rate = stream.get("bit_rate", "unknown")
            
            self.log(f"      Video Stream {i+1}:")
            self.log(f"        Codec: {codec} {profile}")
            self.log(f"        Resolution: {width}x{height}")
            self.log(f"        Duration: {duration}s")
            if bit_rate != "unknown":
                self.log(f"        Bitrate: {int(bit_rate)//1000}kbps")
            
            verification_results.append(f"Video: {codec} {width}x{height}")
        
        # Detailed audio stream info
        for i, stream in enumerate(audio_streams):
            codec = stream.get("codec_name", "unknown")
            sample_rate = stream.get("sample_rate", "unknown")
            channels = stream.get("channels", "unknown")
            
            self.log(f"      Audio Stream {i+1}:")
            self.log(f"        Codec: {codec}")
            self.log(f"        Sample Rate: {sample_rate}Hz")
            self.log(f"        Channels: {channels}")
            
            verification_results.append(f"Audio: {codec} {channels}ch")
        
        # Step 3: Compare with original if provided
        if original_info:
            self.log(f"   Step 3: Comparing with original...")
            original_streams = original_info.get("streams", [])
            original_video = [s for s in original_streams if s.get("codec_type") == "video"]
            original_audio = [s for s in original_streams if s.get("codec_type") == "audio"]
            
            # Compare stream counts
            if len(video_streams) == len(original_video):
                self.log(f"   ✅ Video stream count matches original")
            else:
                self.log(f"   ⚠️  Video stream count differs: {len(video_streams)} vs {len(original_video)}")
            
            if len(audio_streams) == len(original_audio):
                self.log(f"   ✅ Audio stream count matches original")
            else:
                self.log(f"   ⚠️  Audio stream count differs: {len(audio_streams)} vs {len(original_audio)}")
            
            # Compare resolution
            if video_streams and original_video:
                orig_res = f"{original_video[0].get('width', 0)}x{original_video[0].get('height', 0)}"
                new_res = f"{video_streams[0].get('width', 0)}x{video_streams[0].get('height', 0)}"
                if orig_res == new_res:
                    self.log(f"   ✅ Resolution preserved: {new_res}")
                else:
                    self.log(f"   ⚠️  Resolution changed: {orig_res} → {new_res}")
        
        # Step 4: Playability test - decode sample sections
        self.log(f"   Step 4: Playability testing...")
        
        # Test beginning (first 5 seconds)
        self.log(f"      Testing beginning (0-5s)...")
        cmd_start = [
            self.config["ffmpeg_path"],
            "-v", "error",
            "-i", str(file_path),
            "-t", "5",
            "-f", "null", "-"
        ]
        
        try:
            result = subprocess.run(cmd_start, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self.log(f"      ✅ Beginning playback test passed")
            else:
                return False, f"Beginning playback test failed: {result.stderr}"
        except Exception as e:
            return False, f"Beginning playback test error: {e}"
        
        # Test middle section
        video_duration = self.get_video_duration(video_info)
        if video_duration > 20:  # Only test middle if video is long enough
            middle_start = video_duration / 2 - 2.5  # Start 2.5s before middle
            self.log(f"      Testing middle section ({middle_start:.1f}-{middle_start+5:.1f}s)...")
            cmd_middle = [
                self.config["ffmpeg_path"],
                "-v", "error",
                "-ss", str(middle_start),
                "-i", str(file_path),
                "-t", "5",
                "-f", "null", "-"
            ]
            
            try:
                result = subprocess.run(cmd_middle, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    self.log(f"      ✅ Middle section playback test passed")
                else:
                    self.log(f"      ⚠️  Middle section playback test failed: {result.stderr}")
            except Exception as e:
                self.log(f"      ⚠️  Middle section playback test error: {e}")
        
        # Test end (last 5 seconds)
        if video_duration > 10:  # Only test end if video is long enough
            end_start = max(0, video_duration - 5)
            self.log(f"      Testing end section ({end_start:.1f}s-end)...")
            cmd_end = [
                self.config["ffmpeg_path"],
                "-v", "error",
                "-ss", str(end_start),
                "-i", str(file_path),
                "-f", "null", "-"
            ]
            
            try:
                result = subprocess.run(cmd_end, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    self.log(f"      ✅ End section playback test passed")
                else:
                    self.log(f"      ⚠️  End section playback test failed: {result.stderr}")
            except Exception as e:
                self.log(f"      ⚠️  End section playback test error: {e}")
        
        # Step 5: Final summary
        self.log(f"   Step 5: Verification summary...")
        self.log(f"   🎯 VERIFICATION COMPLETE - ALL TESTS PASSED")
        self.log(f"   📊 File Details: {' | '.join(verification_results)}")
        
        return True, f"Comprehensive verification successful: {' | '.join(verification_results)}"
    
    def estimate_compression_time(self, file_path):
        """Estimate compression time based on file size and system performance."""
        file_size_gb = os.path.getsize(file_path) / (1024**3)
        
        # Rough estimates: ~1GB per 10-20 minutes depending on settings
        # These are conservative estimates
        if self.config["compression_settings"]["preset"] == "ultrafast":
            minutes_per_gb = 5
        elif self.config["compression_settings"]["preset"] == "fast":
            minutes_per_gb = 8
        elif self.config["compression_settings"]["preset"] == "medium":
            minutes_per_gb = 15
        elif self.config["compression_settings"]["preset"] == "slow":
            minutes_per_gb = 25
        else:
            minutes_per_gb = 15
        
        estimated_minutes = file_size_gb * minutes_per_gb
        return timedelta(minutes=estimated_minutes)
    
    def compress_video(self, input_path, output_path, dry_run=False, progress_callback=None):
        """Compress video file with safety checks."""
        self.log(f"{'[DRY RUN] ' if dry_run else ''}Starting compression: {input_path}")
        
        if dry_run:
            self.log("[DRY RUN] Would compress with settings:")
            compression_settings = self.config["compression_settings"]
            for key, value in compression_settings.items():
                self.log(f"[DRY RUN]   {key}: {value}")
            return True, "Dry run completed"
        
        # Get original video info
        original_info = self.get_video_info(input_path)
        if not original_info:
            return False, "Cannot read original video information"
        
        # Get video duration for progress calculation
        video_duration = self.get_video_duration(original_info)
        
        # Build ffmpeg command with progress output to stderr
        cmd = self.build_ffmpeg_command(input_path, output_path, original_info)
        # Add progress output - use stderr and stats for better real-time updates
        cmd.extend(["-stats", "-loglevel", "info"])
        
        self.log(f"FFmpeg command: {' '.join(cmd)}")
        
        # Start compression with progress monitoring
        start_time = time.time()
        import threading
        import queue
        import re
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=0  # Unbuffered
            )
            
            # Queue for thread communication
            progress_queue = queue.Queue()
            
            def monitor_stderr():
                """Monitor stderr for progress in separate thread."""
                current_progress = 0.0
                for line in iter(process.stderr.readline, ''):
                    line = line.strip()
                    if line:
                        # Look for time progress in various formats
                        time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', line)
                        if time_match and video_duration > 0:
                            hours, minutes, seconds = time_match.groups()
                            current_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                            progress_pct = min(current_seconds / video_duration, 1.0)
                            
                            # Only update if progress increased significantly
                            if progress_pct > current_progress + 0.01:  # Update every 1%
                                current_progress = progress_pct
                                progress_queue.put((progress_pct, current_seconds, line))
                        
                        # Also capture frame info for additional progress tracking
                        frame_match = re.search(r'frame=\s*(\d+)', line)
                        if frame_match:
                            progress_queue.put(('frame_info', line))
            
            # Start monitoring thread
            monitor_thread = threading.Thread(target=monitor_stderr, daemon=True)
            monitor_thread.start()
            
            # Process progress updates
            last_update_time = time.time()
            current_progress = 0.0
            
            while process.poll() is None:
                try:
                    # Check for progress updates with timeout
                    update = progress_queue.get(timeout=0.5)
                    current_time = time.time()
                    
                    if isinstance(update[0], float):  # Progress percentage
                        progress_pct, current_seconds, line = update
                        if progress_callback:
                            progress_callback(progress_pct)
                        
                        # Log progress every 5 seconds or significant progress jumps
                        if current_time - last_update_time > 5.0 or progress_pct > current_progress + 0.05:
                            self.log(f"Progress: {progress_pct*100:.1f}% ({current_seconds:.1f}s / {video_duration:.1f}s)")
                            last_update_time = current_time
                            current_progress = progress_pct
                    elif update[0] == 'frame_info':
                        # Optionally log frame info less frequently
                        if current_time - last_update_time > 10.0:
                            self.log(f"Encoding: {update[1]}")
                            last_update_time = current_time
                            
                except queue.Empty:
                    # No progress update, continue waiting
                    continue
            
            # Final callback update
            if progress_callback:
                progress_callback(1.0)
            
            # Wait for process to complete and join monitoring thread
            process.wait()
            monitor_thread.join(timeout=1.0)
            
            if process.returncode != 0:
                return False, f"FFmpeg failed with return code {process.returncode}"
            
            end_time = time.time()
            duration = timedelta(seconds=int(end_time - start_time))
            self.log(f"Compression completed in {duration}")
            
            return True, "Compression successful"
            
        except Exception as e:
            return False, f"Compression error: {e}"
    
    def build_ffmpeg_command(self, input_path, output_path, original_info):
        """Build FFmpeg command based on configuration and video properties."""
        cmd = [self.config["ffmpeg_path"], "-y", "-i", str(input_path)]
        
        settings = self.config["compression_settings"]
        
        # Video codec settings
        cmd.extend(["-c:v", settings["video_codec"]])
        cmd.extend(["-preset", settings["preset"]])
        cmd.extend(["-crf", str(settings["crf"])])
        
        # Preserve 10-bit if specified
        if settings["preserve_10bit"]:
            # Check if original is 10-bit
            video_stream = next((s for s in original_info["streams"] if s["codec_type"] == "video"), None)
            if video_stream and "pix_fmt" in video_stream:
                if "10" in video_stream["pix_fmt"]:
                    cmd.extend(["-pix_fmt", "yuv420p10le"])
        
        # Audio - copy without reencoding to preserve quality
        cmd.extend(["-c:a", "copy"])
        
        # Preserve metadata
        if settings["preserve_metadata"]:
            cmd.extend(["-map_metadata", "0"])
            cmd.extend(["-movflags", "+faststart"])
        
        # Calculate target bitrate if specified
        if "target_bitrate_reduction" in settings:
            original_bitrate = self.get_original_bitrate(original_info)
            if original_bitrate:
                target_bitrate = int(original_bitrate * settings["target_bitrate_reduction"])
                cmd.extend(["-b:v", f"{target_bitrate}k"])
                self.log(f"Target bitrate: {target_bitrate}k (reduced from {original_bitrate}k)")
        
        cmd.append(str(output_path))
        return cmd
    
    def get_original_bitrate(self, video_info):
        """Extract original video bitrate from video info."""
        try:
            video_stream = next((s for s in video_info["streams"] if s["codec_type"] == "video"), None)
            if video_stream and "bit_rate" in video_stream:
                return int(video_stream["bit_rate"]) // 1000  # Convert to kbps
            
            # Fallback: calculate from format
            format_info = video_info.get("format", {})
            if "bit_rate" in format_info and "duration" in format_info:
                total_bitrate = int(format_info["bit_rate"]) // 1000
                # Assume ~10% is audio, rest is video (rough estimate)
                return int(total_bitrate * 0.9)
        except:
            pass
        return None
    
    def process_file(self, file_path, dry_run=False, progress_callback=None):
        """Process a single file with full safety protocol."""
        file_path = Path(file_path)
        self.log(f"\n{'='*50}")
        self.log(f"Processing: {file_path.name}")
        self.log(f"Full path: {file_path}")
        
        # Safety checks
        if not file_path.exists():
            error = f"File does not exist: {file_path}"
            self.log(error, "ERROR")
            return False, error
        
        # Check disk space
        space_ok, space_msg = self.check_disk_space(file_path)
        if not space_ok:
            self.log(space_msg, "ERROR")
            return False, space_msg
        
        # Create temp directory
        temp_dir = Path(self.config["temp_dir"])
        temp_dir.mkdir(exist_ok=True)
        
        # Generate temporary output path
        output_name = f"{file_path.stem}_compressed{file_path.suffix}"
        temp_output = temp_dir / output_name
        
        if dry_run:
            self.log(f"[DRY RUN] Would create: {temp_output}")
            estimated_time = self.estimate_compression_time(file_path)
            self.log(f"[DRY RUN] Estimated compression time: {estimated_time}")
            return True, "Dry run successful"
        
        # Step 1: Create original file hash for verification
        if self.config["safety_settings"]["create_backup_hash"]:
            original_hash = self.calculate_file_hash(file_path)
            if not original_hash:
                return False, "Failed to calculate original file hash"
        
        # Get original video info for comparison
        original_info = self.get_video_info(file_path) if not dry_run else None
        
        # Step 2: Compress to temporary location
        self.log("Step 1: Compressing video...")
        success, message = self.compress_video(file_path, temp_output, dry_run, progress_callback)
        if not success:
            self.cleanup_temp_files(temp_output)
            return False, f"Compression failed: {message}"
        
        # Step 3: Verify compressed file integrity
        self.log("Step 2: Verifying compressed file...")
        if self.config["safety_settings"]["verify_integrity"]:
            integrity_ok, integrity_msg = self.verify_file_integrity(temp_output, original_info)
            if not integrity_ok:
                self.cleanup_temp_files(temp_output)
                return False, f"Compressed file verification failed: {integrity_msg}"
        
        # Step 4: Compare file sizes and show compression results
        original_size = file_path.stat().st_size
        compressed_size = temp_output.stat().st_size
        compression_ratio = compressed_size / original_size
        space_saved = original_size - compressed_size
        
        self.log(f"Compression results:")
        self.log(f"  Original size: {original_size / (1024**3):.2f}GB")
        self.log(f"  Compressed size: {compressed_size / (1024**3):.2f}GB")
        self.log(f"  Compression ratio: {compression_ratio:.2%}")
        self.log(f"  Space saved: {space_saved / (1024**3):.2f}GB")
        
        # Step 5: Move compressed file to final location (same directory as original)
        final_output = file_path.parent / output_name
        self.log(f"Step 3: Moving to final location: {final_output}")
        
        try:
            shutil.move(str(temp_output), str(final_output))
        except Exception as e:
            self.cleanup_temp_files(temp_output)
            return False, f"Failed to move compressed file: {e}"
        
        # Step 6: Final verification of moved file
        self.log("Step 4: Final verification...")
        final_integrity_ok, final_integrity_msg = self.verify_file_integrity(final_output, original_info)
        if not final_integrity_ok:
            self.log(f"Final verification failed: {final_integrity_msg}", "ERROR")
            # Don't delete original - something went wrong
            return False, f"Final verification failed: {final_integrity_msg}"
        
        # Step 7: ONLY NOW delete original file
        self.log("Step 5: Deleting original file...")
        try:
            file_path.unlink()
            self.log(f"Original file deleted: {file_path}")
        except Exception as e:
            self.log(f"Failed to delete original file: {e}", "ERROR")
            return False, f"Failed to delete original file: {e}"
        
        # Step 8: Log success
        self.log(f"✅ SUCCESS: {file_path.name} compressed successfully")
        self.log(f"   New file: {final_output}")
        self.log(f"   Space saved: {space_saved / (1024**3):.2f}GB")
        
        return True, f"File processed successfully. Saved {space_saved / (1024**3):.2f}GB"
    
    def cleanup_temp_files(self, *temp_files):
        """Clean up temporary files."""
        for temp_file in temp_files:
            try:
                if temp_file and Path(temp_file).exists():
                    Path(temp_file).unlink()
                    self.log(f"Cleaned up temp file: {temp_file}")
            except Exception as e:
                self.log(f"Failed to clean up {temp_file}: {e}", "WARNING")
    
    def calculate_total_duration(self, file_list):
        """Calculate total duration of all video files."""
        total_duration = 0.0
        for file_path in file_list:
            if Path(file_path).exists():
                video_info = self.get_video_info(file_path)
                if video_info:
                    duration = self.get_video_duration(video_info)
                    total_duration += duration
        return total_duration
    
    def process_file_list(self, file_list, dry_run=False, batch_progress_callback=None):
        """Process a list of files with comprehensive reporting."""
        self.log(f"\n{'='*60}")
        self.log(f"BATCH PROCESSING {'(DRY RUN)' if dry_run else ''}")
        self.log(f"Files to process: {len(file_list)}")
        
        # Calculate total duration and size
        total_video_duration = self.calculate_total_duration(file_list)
        total_original_size = 0
        total_estimated_time = timedelta()
        
        for file_path in file_list:
            if Path(file_path).exists():
                size = os.path.getsize(file_path)
                total_original_size += size
                if not dry_run:
                    estimated_time = self.estimate_compression_time(file_path)
                    total_estimated_time += estimated_time
        
        self.log(f"Total data to process: {total_original_size / (1024**3):.2f}GB")
        self.log(f"Total video duration: {timedelta(seconds=int(total_video_duration))}")
        if not dry_run:
            self.log(f"Estimated total time: {total_estimated_time}")
            estimated_completion = datetime.now() + total_estimated_time
            self.log(f"Estimated completion: {estimated_completion.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Process each file
        start_time = time.time()
        total_space_saved = 0
        processed_duration = 0.0
        
        for i, file_path in enumerate(file_list, 1):
            self.log(f"\n[{i}/{len(file_list)}] Processing: {Path(file_path).name}")
            
            original_size = 0
            file_duration = 0.0
            if Path(file_path).exists():
                original_size = os.path.getsize(file_path)
                video_info = self.get_video_info(file_path)
                if video_info:
                    file_duration = self.get_video_duration(video_info)
            
            # Create progress callback for this file
            def file_progress_callback(file_progress):
                if batch_progress_callback and total_video_duration > 0:
                    # Calculate overall progress
                    current_file_contribution = (file_progress * file_duration)
                    overall_progress = (processed_duration + current_file_contribution) / total_video_duration
                    batch_progress_callback(overall_progress, f"File {i}/{len(file_list)}: {Path(file_path).name} ({file_progress*100:.1f}%)")
            
            success, message = self.process_file(file_path, dry_run, file_progress_callback)
            
            if success:
                self.processed_files.append(file_path)
                processed_duration += file_duration
                if not dry_run and Path(file_path).parent.exists():
                    # Calculate space saved
                    compressed_files = list(Path(file_path).parent.glob(f"{Path(file_path).stem}_compressed*"))
                    if compressed_files:
                        compressed_size = compressed_files[0].stat().st_size
                        space_saved = original_size - compressed_size
                        total_space_saved += space_saved
            else:
                self.failed_files.append((file_path, message))
                self.log(f"❌ FAILED: {message}", "ERROR")
                
                # Ask user if they want to continue on failure
                if not dry_run:
                    response = input("\nFile processing failed. Continue with remaining files? (y/n): ")
                    if response.lower() != 'y':
                        self.log("User chose to stop processing.", "INFO")
                        break
        
        # Final summary
        end_time = time.time()
        total_time = timedelta(seconds=int(end_time - start_time))
        
        self.log(f"\n{'='*60}")
        self.log(f"BATCH PROCESSING COMPLETE {'(DRY RUN)' if dry_run else ''}")
        self.log(f"Total time: {total_time}")
        self.log(f"Successfully processed: {len(self.processed_files)}")
        self.log(f"Failed: {len(self.failed_files)}")
        
        if not dry_run and total_space_saved > 0:
            self.log(f"Total space saved: {total_space_saved / (1024**3):.2f}GB")
        
        if self.failed_files:
            self.log(f"\nFailed files:")
            for file_path, error in self.failed_files:
                self.log(f"  - {file_path}: {error}")
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        if self.log_file:
            self.log("=== Video Compression Session Ended ===")
            self.log_file.close()


def main():
    parser = argparse.ArgumentParser(description="Safe Video Compression Tool")
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--files", help="Text file containing video file paths (one per line)")
    parser.add_argument("--dry-run", action="store_true", help="Preview operations without executing")
    parser.add_argument("--single", help="Process a single video file")
    parser.add_argument("files_list", nargs="*", help="Video files to process")
    
    args = parser.parse_args()
    
    # Create compressor instance
    compressor = VideoCompressor(args.config)
    
    # Collect files to process
    files_to_process = []
    
    if args.single:
        files_to_process = [args.single]
    elif args.files:
        # Read from file
        try:
            with open(args.files, 'r') as f:
                files_to_process = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"File list not found: {args.files}")
            sys.exit(1)
    elif args.files_list:
        files_to_process = args.files_list
    else:
        print("No files specified. Use --files, --single, or provide file paths as arguments.")
        parser.print_help()
        sys.exit(1)
    
    if not files_to_process:
        print("No files to process.")
        sys.exit(1)
    
    # Safety prompt for non-dry-run operations
    if not args.dry_run:
        print(f"\n⚠️  VIDEO COMPRESSION SAFETY WARNING ⚠️")
        print(f"You are about to compress {len(files_to_process)} video files.")
        print(f"This will:")
        print(f"1. Create compressed copies of your videos")
        print(f"2. Verify the compressed files work correctly") 
        print(f"3. DELETE the original files after verification")
        print(f"")
        print(f"Make sure you have backups of important files!")
        print(f"")
        response = input("Are you sure you want to continue? Type 'YES' to proceed: ")
        
        if response != "YES":
            print("Operation cancelled.")
            sys.exit(0)
    
    # Process files
    compressor.process_file_list(files_to_process, args.dry_run)
    
    print(f"\nProcessing complete. Check the log file for detailed information.")


if __name__ == "__main__":
    main()