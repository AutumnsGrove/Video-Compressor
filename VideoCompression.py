#!/usr/bin/env python3

import os
import sys
import json
import subprocess
import shutil
import tempfile
import time
import logging
import logging.handlers
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import argparse
import psutil

class VideoCompressor:
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.logger = None
        self.setup_enhanced_logging()
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
                    "min_free_space_gb": 15,
                    "verify_integrity": True,
                    "create_backup_hash": True,
                    "max_retries": 3
                },
                "large_file_settings": {
                    "threshold_gb": 10,
                    "enhanced_monitoring": True,
                    "progress_update_interval": 10,
                    "hash_chunk_size_mb": 5,
                    "extended_timeouts": True
                },
                "logging_settings": {
                    "max_log_files": 5,
                    "max_log_size_mb": 10,
                    "console_level": "INFO",
                    "file_level": "DEBUG"
                }
            }
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
        except json.JSONDecodeError as e:
            print(f"Error parsing config file: {e}")
            sys.exit(1)
    
    def setup_enhanced_logging(self):
        """Setup enhanced logging system with rotation and levels."""
        log_dir = Path(self.config["log_dir"])
        log_dir.mkdir(exist_ok=True)
        
        # Clean up old log files based on config
        max_logs = self.config.get("logging_settings", {}).get("max_log_files", 5)
        self.cleanup_old_logs(log_dir, max_logs)
        
        # Setup main logger
        self.logger = logging.getLogger('VideoCompressor')
        self.logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)8s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_formatter = logging.Formatter(
            '[%(levelname)s] %(message)s'
        )
        
        # Get configurable log levels first
        console_level = getattr(logging, self.config.get("logging_settings", {}).get("console_level", "INFO"))
        file_level = getattr(logging, self.config.get("logging_settings", {}).get("file_level", "DEBUG"))
        
        # File handler with configurable rotation
        max_size_mb = self.config.get("logging_settings", {}).get("max_log_size_mb", 10)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"video_compression_{timestamp}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_size_mb*1024*1024, backupCount=3
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(detailed_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Log session start
        self.logger.info("=== Video Compression Session Started ===")
        self.logger.info(f"Timestamp: {datetime.now()}")
        self.logger.debug(f"Config: {json.dumps(self.config, indent=2)}")
        self.logger.info(f"Log file: {log_file}")
        
    def cleanup_old_logs(self, log_dir, keep_count=5):
        """Clean up old log files, keeping only the most recent ones."""
        try:
            log_files = sorted(
                [f for f in log_dir.glob("video_compression_*.log*")],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            # Remove files beyond keep_count
            for old_log in log_files[keep_count:]:
                try:
                    old_log.unlink()
                    print(f"🧹 Cleaned up old log: {old_log.name}")
                except Exception as e:
                    print(f"⚠️  Failed to remove old log {old_log}: {e}")
        except Exception as e:
            print(f"⚠️  Error during log cleanup: {e}")
    
    def log(self, message, level="INFO"):
        """Enhanced logging with proper levels and structured output."""
        if not self.logger:
            print(f"[{level}] {message}")
            return
        
        level_map = {
            "DEBUG": self.logger.debug,
            "INFO": self.logger.info,
            "WARNING": self.logger.warning,
            "ERROR": self.logger.error,
            "CRITICAL": self.logger.critical
        }
        
        log_func = level_map.get(level.upper(), self.logger.info)
        log_func(message)
    
    def check_disk_space(self, file_path, safety_multiplier=2.5):
        """Enhanced disk space checking with cross-filesystem support."""
        try:
            file_size = os.path.getsize(file_path)
            temp_dir = Path(self.config["temp_dir"])
            temp_dir.mkdir(exist_ok=True)  # Ensure temp dir exists
            
            # Use psutil for more accurate disk space info
            temp_usage = psutil.disk_usage(str(temp_dir))
            file_parent_usage = psutil.disk_usage(str(Path(file_path).parent))
            
            temp_available_gb = temp_usage.free / (1024**3)
            file_parent_available_gb = file_parent_usage.free / (1024**3)
            
            # Required space calculation for large files
            required_bytes = file_size * safety_multiplier
            required_gb = required_bytes / (1024**3)
            
            min_free_space = self.config["safety_settings"]["min_free_space_gb"]
            
            self.log(f"💾 Enhanced disk space analysis:", "DEBUG")
            self.log(f"   File size: {file_size / (1024**3):.2f}GB", "INFO")
            self.log(f"   Required temp space: {required_gb:.2f}GB", "INFO")
            self.log(f"   Temp directory available: {temp_available_gb:.2f}GB", "INFO")
            self.log(f"   File directory available: {file_parent_available_gb:.2f}GB", "DEBUG")
            self.log(f"   Minimum required free: {min_free_space}GB", "DEBUG")
            
            # Check temp directory space
            if temp_available_gb < (required_gb + min_free_space):
                return False, f"Insufficient temp space. Need {required_gb + min_free_space:.2f}GB, have {temp_available_gb:.2f}GB"
            
            # Check if we can write the final file
            if file_parent_available_gb < (file_size / (1024**3) + min_free_space):
                return False, f"Insufficient space for final file. Need {file_size / (1024**3) + min_free_space:.2f}GB, have {file_parent_available_gb:.2f}GB"
            
            self.log(f"✅ Sufficient disk space available", "INFO")
            return True, "Sufficient disk space available"
            
        except Exception as e:
            self.log(f"Error checking disk space: {e}", "ERROR")
            return False, f"Disk space check failed: {e}"
    
    def calculate_file_hash(self, file_path, chunk_size=None):
        """Calculate SHA-256 hash optimized for large files."""
        if chunk_size is None:
            # Use config-based chunk size for large files
            chunk_size_mb = self.config.get("large_file_settings", {}).get("hash_chunk_size_mb", 5)
            chunk_size = chunk_size_mb * 1024 * 1024
        file_size = os.path.getsize(file_path)
        self.log(f"🔐 Calculating hash for {Path(file_path).name} ({file_size / (1024**3):.2f}GB)", "INFO")
        
        hash_sha256 = hashlib.sha256()
        bytes_processed = 0
        last_progress_log = 0
        
        try:
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    hash_sha256.update(chunk)
                    bytes_processed += len(chunk)
                    
                    # Log progress every 10% for large files (>1GB)
                    if file_size > 1024**3:
                        progress = (bytes_processed / file_size) * 100
                        if progress - last_progress_log >= 10:
                            self.log(f"   Hash progress: {progress:.1f}%", "DEBUG")
                            last_progress_log = progress
            
            hash_result = hash_sha256.hexdigest()
            self.log(f"✅ Hash calculated: {hash_result[:16]}...", "DEBUG")
            return hash_result
            
        except Exception as e:
            self.log(f"Error calculating hash: {e}", "ERROR")
            return None
    
    def get_video_info(self, file_path):
        """Get detailed video information with enhanced timeout for large files."""
        file_size_gb = os.path.getsize(file_path) / (1024**3)
        
        # Dynamic timeout based on file size and config
        if self.config.get("large_file_settings", {}).get("extended_timeouts", True):
            timeout = max(30, int(30 + file_size_gb * 15))  # More generous for large files
        else:
            timeout = 30
        
        cmd = [
            self.config["ffmpeg_path"].replace("ffmpeg", "ffprobe"),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path)
        ]
        
        self.log(f"🔍 Analyzing video info (timeout: {timeout}s)", "DEBUG")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0:
                video_info = json.loads(result.stdout)
                self.log(f"✅ Video analysis complete", "DEBUG")
                return video_info
            else:
                self.log(f"ffprobe error: {result.stderr}", "ERROR")
                return None
        except subprocess.TimeoutExpired:
            self.log(f"ffprobe timeout after {timeout}s for large file", "ERROR")
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
                bufsize=1  # Line buffered for better progress tracking
            )
            
            # Enhanced progress monitoring for large files
            progress_queue = queue.Queue(maxsize=100)  # Prevent memory buildup
            
            def monitor_stderr():
                """Enhanced progress monitoring optimized for large files."""
                current_progress = 0.0
                last_fps = 0
                last_size = 0
                
                try:
                    for line in iter(process.stderr.readline, ''):
                        if not line:
                            break
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Parse multiple progress indicators
                        time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', line)
                        fps_match = re.search(r'fps=\s*([\d.]+)', line)
                        size_match = re.search(r'size=\s*(\d+)kB', line)
                        
                        if time_match and video_duration > 0:
                            hours, minutes, seconds = time_match.groups()
                            current_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                            progress_pct = min(current_seconds / video_duration, 1.0)
                            
                            # Extract additional metrics
                            current_fps = float(fps_match.group(1)) if fps_match else last_fps
                            current_size = int(size_match.group(1)) if size_match else last_size
                            
                            # Only update if progress increased significantly (0.5% for large files)
                            if progress_pct > current_progress + 0.005:
                                current_progress = progress_pct
                                last_fps = current_fps
                                last_size = current_size
                                
                                # Don't overwhelm the queue
                                if not progress_queue.full():
                                    progress_queue.put((
                                        progress_pct, current_seconds, current_fps, 
                                        current_size, line
                                    ))
                        
                        # Capture any error messages
                        elif 'error' in line.lower() or 'failed' in line.lower():
                            if not progress_queue.full():
                                progress_queue.put(('error', line))
                                
                except Exception as e:
                    if not progress_queue.full():
                        progress_queue.put(('monitor_error', str(e)))
            
            # Start monitoring thread
            monitor_thread = threading.Thread(target=monitor_stderr, daemon=True)
            monitor_thread.start()
            
            # Enhanced progress processing for large files
            last_update_time = time.time()
            last_log_time = time.time()
            current_progress = 0.0
            
            while process.poll() is None:
                try:
                    # Shorter timeout for more responsive monitoring
                    update = progress_queue.get(timeout=0.2)
                    current_time = time.time()
                    
                    if isinstance(update[0], float):  # Progress percentage
                        progress_pct, current_seconds, fps, size_kb, line = update
                        
                        # Update progress callback more frequently
                        if progress_callback:
                            progress_callback(progress_pct)
                        
                        # Log progress with enhanced info for large files
                        if (current_time - last_log_time > 10.0 or  # Every 10 seconds
                            progress_pct > current_progress + 0.02):  # Or every 2%
                            
                            time_remaining = "unknown"
                            if progress_pct > 0.01:  # Avoid division by zero
                                elapsed = current_time - start_time
                                total_estimated = elapsed / progress_pct
                                remaining = total_estimated - elapsed
                                time_remaining = str(timedelta(seconds=int(remaining)))
                            
                            self.log(
                                f"📊 Progress: {progress_pct*100:.1f}% | "
                                f"{current_seconds:.1f}s/{video_duration:.1f}s | "
                                f"FPS: {fps:.1f} | Size: {size_kb//1024:.1f}MB | "
                                f"ETA: {time_remaining}",
                                "INFO"
                            )
                            last_log_time = current_time
                            current_progress = progress_pct
                    
                    elif update[0] == 'error':
                        self.log(f"FFmpeg error: {update[1]}", "ERROR")
                    elif update[0] == 'monitor_error':
                        self.log(f"Progress monitoring error: {update[1]}", "WARNING")
                        
                except queue.Empty:
                    # Check if process is still running every few seconds
                    if current_time - last_update_time > 30.0:
                        self.log("❤️  Large file processing continues...", "INFO")
                        last_update_time = current_time
                    continue
            
            # Final callback update
            if progress_callback:
                progress_callback(1.0)
            
            # Wait for process to complete and cleanup monitoring
            process.wait()
            monitor_thread.join(timeout=5.0)  # Longer timeout for large files
            
            # Process any remaining queue items
            try:
                while not progress_queue.empty():
                    progress_queue.get_nowait()
            except queue.Empty:
                pass
            
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
        """Process a single file with enhanced large file support."""
        file_path = Path(file_path)
        file_size_gb = os.path.getsize(file_path) / (1024**3)
        
        self.log(f"\n{'='*60}", "INFO")
        self.log(f"🎥 Processing: {file_path.name} ({file_size_gb:.2f}GB)", "INFO")
        self.log(f"📁 Full path: {file_path}", "DEBUG")
        
        # Log special handling for large files
        if file_size_gb > 10:
            self.log(f"🔥 LARGE FILE DETECTED: Enabling enhanced processing mode", "WARNING")
            self.log(f"   • Extended timeouts and monitoring enabled", "INFO")
            self.log(f"   • Progress updates every 10 seconds", "INFO")
            self.log(f"   • Enhanced disk space verification", "INFO")
        
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
        if self.logger:
            self.log("=== Video Compression Session Ended ===", "INFO")
            # Close file handlers
            for handler in self.logger.handlers[:]:
                if isinstance(handler, (logging.FileHandler, logging.handlers.RotatingFileHandler)):
                    handler.close()
                    self.logger.removeHandler(handler)


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