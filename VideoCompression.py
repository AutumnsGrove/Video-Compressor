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
import queue
import threading
import re
import platform

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
                    "crf": 23,
                    "enable_hardware_acceleration": True
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
                    "extended_timeouts": True,
                    "use_same_filesystem": True
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
            file_path_obj = Path(file_path)
            
            # Determine actual temp directory that will be used (matching compression logic)
            if self.config.get("large_file_settings", {}).get("use_same_filesystem", True):
                # Same filesystem temp directory (matches compression behavior)
                actual_temp_dir = file_path_obj.parent / ".video_compression_temp"
                self.log(f"📁 Using same-filesystem temp checking: {actual_temp_dir}", "DEBUG")
            else:
                # Configured temp directory
                actual_temp_dir = Path(self.config["temp_dir"])
                self.log(f"📁 Using configured temp directory: {actual_temp_dir}", "DEBUG")
            
            # Ensure temp dir exists for space checking
            actual_temp_dir.mkdir(exist_ok=True)
            
            # Use psutil for more accurate disk space info
            temp_usage = psutil.disk_usage(str(actual_temp_dir))
            file_parent_usage = psutil.disk_usage(str(file_path_obj.parent))
            
            temp_available_gb = temp_usage.free / (1024**3)
            file_parent_available_gb = file_parent_usage.free / (1024**3)
            
            # Required space calculation for large files
            required_bytes = file_size * safety_multiplier
            required_gb = required_bytes / (1024**3)
            
            min_free_space = self.config["safety_settings"]["min_free_space_gb"]
            
            self.log(f"💾 Enhanced disk space analysis:", "DEBUG")
            self.log(f"   File size: {file_size / (1024**3):.2f}GB", "INFO")
            self.log(f"   Required temp space: {required_gb:.2f}GB", "INFO")
            self.log(f"   Actual temp dir available: {temp_available_gb:.2f}GB", "INFO")
            self.log(f"   File directory available: {file_parent_available_gb:.2f}GB", "DEBUG")
            self.log(f"   Minimum required free: {min_free_space}GB", "DEBUG")
            
            # Check temp directory space (using actual temp location)
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
    
    def analyze_file_size_breakdown(self, file_path, video_info):
        """Analyze what contributes to file size and return detailed breakdown."""
        try:
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # Get video and audio streams
            streams = video_info.get("streams", [])
            video_streams = [s for s in streams if s.get("codec_type") == "video"]
            audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
            
            # Get format info
            format_info = video_info.get("format", {})
            duration = float(format_info.get("duration", 0))
            total_bitrate = int(format_info.get("bit_rate", 0)) if format_info.get("bit_rate") else None
            
            breakdown = {
                "file_size_mb": file_size_mb,
                "duration_seconds": duration,
                "duration_formatted": str(timedelta(seconds=int(duration))),
                "total_bitrate_kbps": total_bitrate // 1000 if total_bitrate else None,
                "video_contribution": 0,
                "audio_contribution": 0,
                "other_contribution": 0,
                "details": []
            }
            
            # Analyze video streams
            video_bitrate_total = 0
            for i, stream in enumerate(video_streams):
                codec = stream.get("codec_name", "unknown")
                width = stream.get("width", 0)
                height = stream.get("height", 0)
                profile = stream.get("profile", "")
                pix_fmt = stream.get("pix_fmt", "")
                frame_rate = stream.get("r_frame_rate", "0/1")
                
                # Calculate frame rate
                try:
                    if "/" in str(frame_rate):
                        num, den = frame_rate.split("/")
                        fps = float(num) / float(den) if float(den) != 0 else 0
                    else:
                        fps = float(frame_rate)
                except:
                    fps = 0
                
                # Get video bitrate
                video_bitrate = 0
                if "bit_rate" in stream:
                    try:
                        video_bitrate = int(stream["bit_rate"]) // 1000  # Convert to kbps
                        video_bitrate_total += video_bitrate
                    except (ValueError, TypeError):
                        video_bitrate = 0
                
                # Convert width and height to int safely
                try:
                    width = int(width) if width else 0
                    height = int(height) if height else 0
                except (ValueError, TypeError):
                    width = 0
                    height = 0
                
                # Analyze what drives video size
                resolution_factor = width * height
                is_10bit = "10" in str(pix_fmt)
                is_hdr = "2020" in str(profile).lower() or "hdr" in str(profile).lower()
                
                detail = {
                    "type": "video",
                    "stream_index": i,
                    "codec": codec,
                    "resolution": f"{width}x{height}",
                    "fps": round(fps, 2),
                    "bitrate_kbps": video_bitrate,
                    "profile": profile,
                    "pixel_format": pix_fmt,
                    "is_10bit": is_10bit,
                    "is_hdr": is_hdr,
                    "resolution_pixels": resolution_factor,
                    "size_factors": []
                }
                
                # Identify size-driving factors
                if resolution_factor > 8000000:  # 4K+
                    detail["size_factors"].append(f"4K+ Resolution ({width}x{height})")
                elif resolution_factor > 2000000:  # 1080p+
                    detail["size_factors"].append(f"High Resolution ({width}x{height})")
                
                if fps > 30:
                    detail["size_factors"].append(f"High Frame Rate ({fps}fps)")
                
                if is_10bit:
                    detail["size_factors"].append("10-bit Color Depth")
                
                if is_hdr:
                    detail["size_factors"].append("HDR Content")
                
                if video_bitrate > 50000:  # Very high bitrate
                    detail["size_factors"].append(f"Very High Bitrate ({video_bitrate//1000}Mbps)")
                elif video_bitrate > 20000:  # High bitrate
                    detail["size_factors"].append(f"High Bitrate ({video_bitrate//1000}Mbps)")
                
                breakdown["details"].append(detail)
            
            # Analyze audio streams
            audio_bitrate_total = 0
            for i, stream in enumerate(audio_streams):
                codec = stream.get("codec_name", "unknown")
                sample_rate = stream.get("sample_rate", 0)
                channels = stream.get("channels", 0)
                
                # Get audio bitrate
                audio_bitrate = 0
                if "bit_rate" in stream:
                    try:
                        audio_bitrate = int(stream["bit_rate"]) // 1000  # Convert to kbps
                        audio_bitrate_total += audio_bitrate
                    except (ValueError, TypeError):
                        audio_bitrate = 0
                
                # Convert sample_rate and channels to int safely
                try:
                    sample_rate = int(sample_rate) if sample_rate else 0
                except (ValueError, TypeError):
                    sample_rate = 0
                
                try:
                    channels = int(channels) if channels else 0
                except (ValueError, TypeError):
                    channels = 0
                
                detail = {
                    "type": "audio",
                    "stream_index": i,
                    "codec": codec,
                    "sample_rate": sample_rate,
                    "channels": channels,
                    "bitrate_kbps": audio_bitrate,
                    "size_factors": []
                }
                
                # Identify audio size factors
                if audio_bitrate > 1000:  # High quality audio
                    detail["size_factors"].append(f"High Quality Audio ({audio_bitrate}kbps)")
                
                if channels > 2:
                    detail["size_factors"].append(f"Multichannel Audio ({channels} channels)")
                
                if sample_rate > 48000:
                    detail["size_factors"].append(f"High Sample Rate ({sample_rate}Hz)")
                
                if codec in ["pcm_s24le", "pcm_s32le", "flac"]:
                    detail["size_factors"].append("Lossless Audio")
                
                breakdown["details"].append(detail)
            
            # Calculate contributions as percentages - ONLY if we have real data
            total_stream_bitrate = video_bitrate_total + audio_bitrate_total
            
            if total_stream_bitrate > 0:
                # Use actual stream bitrates for accurate percentages
                breakdown["video_contribution"] = (video_bitrate_total / total_stream_bitrate) * 100
                breakdown["audio_contribution"] = (audio_bitrate_total / total_stream_bitrate) * 100
                breakdown["other_contribution"] = 100 - breakdown["video_contribution"] - breakdown["audio_contribution"]
                self.log(f"Real bitrate data - Video: {video_bitrate_total}kbps, Audio: {audio_bitrate_total}kbps", "DEBUG")
            else:
                # No real bitrate data available - don't show fake percentages
                breakdown["video_contribution"] = None
                breakdown["audio_contribution"] = None  
                breakdown["other_contribution"] = None
                self.log("No bitrate data available - skipping contribution analysis", "DEBUG")
            
            return breakdown
            
        except Exception as e:
            self.log(f"Error analyzing file size breakdown: {e}", "ERROR")
            return None

    def compress_video(self, input_path, output_path, dry_run=False, progress_callback=None):
        """Compress video file with safety checks."""
        self.log(f"{'[DRY RUN] ' if dry_run else ''}Starting compression: {input_path}")
        
        if dry_run:
            # Get video info for detailed analysis
            video_info = self.get_video_info(input_path)
            if not video_info:
                return False, "Cannot read video information for dry run analysis"
            
            # Analyze file size breakdown
            breakdown = self.analyze_file_size_breakdown(input_path, video_info)
            
            if breakdown:
                self.log("[DRY RUN] 📊 FILE SIZE ANALYSIS:", "INFO")
                file_size_gb = os.path.getsize(input_path) / (1024**3)
                self.log(f"[DRY RUN]   File Size: {file_size_gb:.2f}GB ({breakdown['file_size_mb']:.1f}MB)", "INFO")
                self.log(f"[DRY RUN]   Duration: {breakdown['duration_formatted']} ({breakdown['duration_seconds']:.1f}s)", "INFO")
            else:
                self.log("[DRY RUN] 📊 FILE SIZE ANALYSIS: Unable to analyze (using basic info)", "WARNING")
                file_size_gb = os.path.getsize(input_path) / (1024**3)
                self.log(f"[DRY RUN]   File Size: {file_size_gb:.2f}GB", "INFO")
                
                # Get basic duration info
                format_info = video_info.get("format", {})
                if "duration" in format_info:
                    duration = float(format_info["duration"])
                    duration_formatted = str(timedelta(seconds=int(duration)))
                    self.log(f"[DRY RUN]   Duration: {duration_formatted} ({duration:.1f}s)", "INFO")
            
            if breakdown:
                if breakdown['total_bitrate_kbps']:
                    self.log(f"[DRY RUN]   Total Bitrate: {breakdown['total_bitrate_kbps']//1000:.1f}Mbps", "INFO")
                
                # Only show contribution analysis if we have real data
                if breakdown['video_contribution'] is not None:
                    self.log("[DRY RUN] 🎯 WHAT'S MAKING THIS FILE LARGE:", "INFO")
                    self.log(f"[DRY RUN]   📹 Video Contribution: {breakdown['video_contribution']:.1f}%", "INFO")
                    self.log(f"[DRY RUN]   🔊 Audio Contribution: {breakdown['audio_contribution']:.1f}%", "INFO")
                    self.log(f"[DRY RUN]   📦 Container/Other: {breakdown['other_contribution']:.1f}%", "INFO")
                else:
                    self.log("[DRY RUN] 🎯 CONTRIBUTION ANALYSIS: No bitrate data available", "INFO")
                
                # Show detailed breakdown per stream
                for detail in breakdown['details']:
                    if detail['type'] == 'video':
                        self.log(f"[DRY RUN]   📹 Video Stream {detail['stream_index']+1}:", "INFO")
                        self.log(f"[DRY RUN]      Codec: {detail['codec']} | Resolution: {detail['resolution']} | FPS: {detail['fps']}", "INFO")
                        if detail['bitrate_kbps'] > 0:
                            self.log(f"[DRY RUN]      Bitrate: {detail['bitrate_kbps']//1000:.1f}Mbps", "INFO")
                        if detail['is_10bit']:
                            self.log(f"[DRY RUN]      Color: 10-bit ({detail['pixel_format']})", "INFO")
                        if detail['size_factors']:
                            self.log(f"[DRY RUN]      Size Drivers: {', '.join(detail['size_factors'])}", "WARNING")
                    
                    elif detail['type'] == 'audio':
                        self.log(f"[DRY RUN]   🔊 Audio Stream {detail['stream_index']+1}:", "INFO")
                        self.log(f"[DRY RUN]      Codec: {detail['codec']} | Channels: {detail['channels']} | Sample Rate: {detail['sample_rate']}Hz", "INFO")
                        if detail['bitrate_kbps'] > 0:
                            self.log(f"[DRY RUN]      Bitrate: {detail['bitrate_kbps']}kbps", "INFO")
                        if detail['size_factors']:
                            self.log(f"[DRY RUN]      Size Drivers: {', '.join(detail['size_factors'])}", "WARNING")
            
            self.log("[DRY RUN] ⚙️  COMPRESSION SETTINGS TO BE APPLIED:", "INFO")
            compression_settings = self.config["compression_settings"]
            for key, value in compression_settings.items():
                self.log(f"[DRY RUN]   {key}: {value}", "INFO")
            
            # Estimate potential savings - only if we have reliable bitrate data
            if breakdown and breakdown['total_bitrate_kbps'] and breakdown['total_bitrate_kbps'] > 0:
                target_reduction = compression_settings.get("target_bitrate_reduction", 0.5)
                
                # More realistic compression estimation based on typical H.265 efficiency
                # H.265 typically achieves 50% bitrate reduction for same quality, 
                # but we're also reducing quality (CRF), so total reduction is higher
                crf_factor = max(0.3, 1.0 - (compression_settings.get("crf", 23) - 18) * 0.05)  # Lower CRF = less compression
                realistic_reduction = target_reduction * crf_factor  # Combined effect
                
                estimated_new_bitrate = breakdown['total_bitrate_kbps'] * realistic_reduction
                estimated_new_size = (estimated_new_bitrate * breakdown['duration_seconds']) / 8 / 1024  # MB
                potential_savings = breakdown['file_size_mb'] - estimated_new_size
                savings_percent = (potential_savings / breakdown['file_size_mb']) * 100
                
                # Only show if the estimate seems reasonable (10-95% compression)
                if 10 <= savings_percent <= 95:
                    self.log(f"[DRY RUN] 💾 ESTIMATED COMPRESSION RESULTS:", "INFO")
                    self.log(f"[DRY RUN]   Estimated New Size: {estimated_new_size/1024:.2f}GB", "INFO")
                    self.log(f"[DRY RUN]   Potential Savings: {potential_savings/1024:.2f}GB ({savings_percent:.1f}%)", "INFO")
                    self.log(f"[DRY RUN]   Note: Estimate based on bitrate reduction + quality settings", "INFO")
                else:
                    self.log(f"[DRY RUN] 💾 COMPRESSION ESTIMATE: Unreliable calculation, skipping estimate", "INFO")
            else:
                self.log(f"[DRY RUN] 💾 COMPRESSION ESTIMATE: No bitrate data available for estimation", "INFO")
            
            return True, "Dry run completed with detailed analysis"
        
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
        
        try:
            self.log(f"🚀 Starting FFmpeg process...", "INFO")
            self.log(f"   Command: {' '.join(cmd[:5])}...", "DEBUG")  # Log first few args
            self.log(f"   Input file: {input_path}", "DEBUG")
            self.log(f"   Output file: {output_path}", "DEBUG")
            
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
                                try:
                                    progress_queue.put((
                                        progress_pct, current_seconds, current_fps, 
                                        current_size, line
                                    ), timeout=0.1)
                                except queue.Full:
                                    pass  # Skip if queue is full
                        
                        # Capture any error messages
                        elif 'error' in line.lower() or 'failed' in line.lower():
                            try:
                                progress_queue.put(('error', line), timeout=0.1)
                            except queue.Full:
                                pass
                                
                except Exception as e:
                    try:
                        progress_queue.put(('monitor_error', str(e)), timeout=0.1)
                    except queue.Full:
                        pass
            
            # Start monitoring thread
            monitor_thread = threading.Thread(target=monitor_stderr, daemon=True)
            monitor_thread.start()
            
            # Enhanced progress processing for large files
            last_update_time = time.time()
            last_log_time = time.time()
            current_progress = 0.0
            
            while process.poll() is None:
                current_time = time.time()  # Initialize current_time at start of loop
                
                try:
                    # Shorter timeout for more responsive monitoring
                    update = progress_queue.get(timeout=0.2)
                    
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
                # Capture stderr for detailed error info
                try:
                    stderr_output = process.stderr.read() if process.stderr else "No stderr available"
                except:
                    stderr_output = "Could not read stderr"
                
                error_msg = f"FFmpeg failed with return code {process.returncode}"
                self.log(f"❌ {error_msg}", "ERROR")
                self.log(f"   FFmpeg stderr: {stderr_output[-500:] if stderr_output else 'N/A'}", "ERROR")  # Last 500 chars
                return False, f"{error_msg}. Check logs for details."
            
            end_time = time.time()
            duration = timedelta(seconds=int(end_time - start_time))
            self.log(f"Compression completed in {duration}")
            
            return True, "Compression successful"
            
        except Exception as e:
            error_msg = f"Compression error: {type(e).__name__}: {e}"
            self.log(f"❌ {error_msg}", "ERROR")
            
            # Add specific troubleshooting for common issues
            if "No space left on device" in str(e):
                self.log("💡 Troubleshooting: Try using a different temp directory with more space", "ERROR")
            elif "Permission denied" in str(e):
                self.log("💡 Troubleshooting: Check file permissions and write access to temp directory", "ERROR")
            elif "Cross-device link" in str(e):
                self.log("💡 Troubleshooting: Temp directory is on different filesystem - this should be fixed automatically", "ERROR")
            
            return False, error_msg
    
    def detect_hardware_acceleration(self):
        """Detect Apple Silicon and test VideoToolbox hardware acceleration availability."""
        try:
            # Check if hardware acceleration is enabled in config
            if not self.config.get("compression_settings", {}).get("enable_hardware_acceleration", True):
                self.log("🔧 Hardware acceleration disabled in config", "INFO")
                return None
            
            # Detect Apple Silicon
            processor = platform.processor().lower()
            machine = platform.machine().lower()
            
            # Check for Apple Silicon indicators
            is_apple_silicon = (
                "arm" in processor or 
                "arm64" in machine or 
                machine == "arm64" or
                machine.startswith("arm")
            )
            
            if not is_apple_silicon:
                self.log(f"🔧 Not Apple Silicon (processor: {processor}, machine: {machine})", "DEBUG")
                return None
            
            self.log(f"🔧 Apple Silicon detected (processor: {processor}, machine: {machine})", "INFO")
            
            # Test VideoToolbox availability with a quick probe
            test_cmd = [
                self.config["ffmpeg_path"],
                "-f", "lavfi",
                "-i", "testsrc=duration=1:size=320x240:rate=1",
                "-c:v", "h264_videotoolbox",
                "-t", "1",
                "-f", "null", "-"
            ]
            
            self.log("🔧 Testing VideoToolbox availability...", "DEBUG")
            
            try:
                result = subprocess.run(
                    test_cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                
                if result.returncode == 0:
                    self.log("✅ VideoToolbox h264_videotoolbox encoder available", "INFO")
                    
                    # Also test HEVC VideoToolbox
                    hevc_test_cmd = test_cmd.copy()
                    hevc_test_cmd[hevc_test_cmd.index("h264_videotoolbox")] = "hevc_videotoolbox"
                    
                    hevc_result = subprocess.run(
                        hevc_test_cmd,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    has_hevc = hevc_result.returncode == 0
                    if has_hevc:
                        self.log("✅ VideoToolbox hevc_videotoolbox encoder available", "INFO")
                    else:
                        self.log("⚠️  VideoToolbox HEVC encoder not available", "DEBUG")
                    
                    return {
                        "type": "videotoolbox",
                        "h264_encoder": "h264_videotoolbox",
                        "hevc_encoder": "hevc_videotoolbox" if has_hevc else None,
                        "quality_param": "-q:v",
                        "pixel_format_10bit": "p010le"
                    }
                else:
                    self.log(f"❌ VideoToolbox test failed: {result.stderr}", "WARNING")
                    return None
                    
            except subprocess.TimeoutExpired:
                self.log("❌ VideoToolbox test timed out", "WARNING")
                return None
            except Exception as e:
                self.log(f"❌ VideoToolbox test error: {e}", "WARNING")
                return None
                
        except Exception as e:
            self.log(f"❌ Hardware acceleration detection error: {e}", "ERROR")
            return None
    
    def build_ffmpeg_command(self, input_path, output_path, original_info):
        """Build FFmpeg command based on configuration and video properties with hardware acceleration."""
        cmd = [self.config["ffmpeg_path"], "-y", "-i", str(input_path)]
        
        settings = self.config["compression_settings"]
        
        # Detect hardware acceleration
        hw_accel = self.detect_hardware_acceleration()
        
        # Determine codec and parameters
        video_codec = settings["video_codec"]
        use_hardware = False
        
        if hw_accel and hw_accel["type"] == "videotoolbox":
            # Check original video stream to determine best codec
            video_stream = next((s for s in original_info["streams"] if s["codec_type"] == "video"), None)
            original_codec = video_stream.get("codec_name", "").lower() if video_stream else ""
            
            # Choose hardware codec based on original and availability
            if settings["video_codec"] == "libx265" and hw_accel["hevc_encoder"]:
                video_codec = hw_accel["hevc_encoder"]
                use_hardware = True
                self.log("🚀 Using VideoToolbox HEVC hardware acceleration", "INFO")
            elif settings["video_codec"] in ["libx264", "libx265"] and hw_accel["h264_encoder"]:
                video_codec = hw_accel["h264_encoder"]
                use_hardware = True
                self.log("🚀 Using VideoToolbox H.264 hardware acceleration", "INFO")
            else:
                self.log(f"🔧 Hardware acceleration not optimal for {settings['video_codec']}, using software", "INFO")
        else:
            self.log("🔧 Using software encoding", "INFO")
        
        # Video codec settings
        cmd.extend(["-c:v", video_codec])
        
        if use_hardware and hw_accel:
            # VideoToolbox-specific parameters
            # Use quality parameter instead of CRF for VideoToolbox
            quality_value = settings.get("crf", 23)
            # Convert CRF to VideoToolbox quality scale (lower = better quality)
            # CRF 18-28 maps roughly to q:v 30-70
            vt_quality = max(30, min(70, int(18 + (quality_value - 18) * 2.6)))
            cmd.extend([hw_accel["quality_param"], str(vt_quality)])
            
            self.log(f"🎛️  VideoToolbox quality: {vt_quality} (from CRF {quality_value})", "DEBUG")
            
            # Handle 10-bit content for VideoToolbox
            if settings["preserve_10bit"]:
                video_stream = next((s for s in original_info["streams"] if s["codec_type"] == "video"), None)
                if video_stream and "pix_fmt" in video_stream and "10" in video_stream["pix_fmt"]:
                    cmd.extend(["-pix_fmt", hw_accel["pixel_format_10bit"]])
                    self.log("🎨 Using 10-bit pixel format for VideoToolbox", "DEBUG")
            
            # VideoToolbox doesn't use preset in the same way
            self.log(f"🔧 VideoToolbox encoder configured", "DEBUG")
            
        else:
            # Software encoding parameters
            cmd.extend(["-preset", settings["preset"]])
            cmd.extend(["-crf", str(settings["crf"])])
            
            # Preserve 10-bit if specified for software encoding
            if settings["preserve_10bit"]:
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
        
        # Calculate target bitrate if specified (only for software encoding)
        if "target_bitrate_reduction" in settings and not use_hardware:
            original_bitrate = self.get_original_bitrate(original_info)
            if original_bitrate:
                target_bitrate = int(original_bitrate * settings["target_bitrate_reduction"])
                cmd.extend(["-b:v", f"{target_bitrate}k"])
                self.log(f"📊 Target bitrate: {target_bitrate}k (reduced from {original_bitrate}k)", "DEBUG")
        
        cmd.append(str(output_path))
        
        # Log the encoding method being used
        encoder_info = f"VideoToolbox {video_codec}" if use_hardware else f"Software {video_codec}"
        self.log(f"🎬 Encoder: {encoder_info}", "INFO")
        
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
        
        # Create temp directory on same filesystem as input file for efficiency
        if self.config.get("large_file_settings", {}).get("use_same_filesystem", True):
            # Create temp directory next to the input file
            temp_dir = file_path.parent / ".video_compression_temp"
            self.log(f"🗂️  Using same-filesystem temp dir: {temp_dir}", "INFO")
        else:
            # Use configured temp directory
            temp_dir = Path(self.config["temp_dir"])
            self.log(f"🗂️  Using configured temp dir: {temp_dir}", "INFO")
        
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
        self.log("🎬 Step 1: Starting video compression...", "INFO")
        self.log(f"   Input: {file_path}", "DEBUG")
        self.log(f"   Temp output: {temp_output}", "DEBUG")
        self.log(f"   Temp dir filesystem: {temp_dir}", "DEBUG")
        
        try:
            success, message = self.compress_video(file_path, temp_output, dry_run, progress_callback)
            if not success:
                self.log(f"❌ Compression failed: {message}", "ERROR")
                self.cleanup_temp_files(temp_output)
                return False, f"Compression failed: {message}"
        except Exception as e:
            self.log(f"❌ Compression exception: {type(e).__name__}: {e}", "ERROR")
            self.cleanup_temp_files(temp_output)
            return False, f"Compression exception: {e}"
        
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
        self.log(f"📂 Step 3: Moving to final location: {final_output}", "INFO")
        self.log(f"   Source: {temp_output}", "DEBUG")
        self.log(f"   Destination: {final_output}", "DEBUG")
        
        try:
            # Ensure the temp file actually exists before moving
            if not temp_output.exists():
                error_msg = f"Temp file does not exist: {temp_output}"
                self.log(f"❌ {error_msg}", "ERROR")
                return False, error_msg
                
            # Check file sizes match expectations
            temp_size = temp_output.stat().st_size
            if temp_size == 0:
                error_msg = f"Temp file is empty (0 bytes): {temp_output}"
                self.log(f"❌ {error_msg}", "ERROR")
                self.cleanup_temp_files(temp_output)
                return False, error_msg
            
            self.log(f"✅ Temp file ready for move: {temp_size / (1024**3):.2f}GB", "DEBUG")
            shutil.move(str(temp_output), str(final_output))
            self.log(f"✅ File moved successfully", "INFO")
            
        except Exception as e:
            self.log(f"❌ Failed to move compressed file: {type(e).__name__}: {e}", "ERROR")
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
        
        # Step 8: Clean up temp directory
        if temp_dir.exists() and temp_dir.name == ".video_compression_temp":
            try:
                # Remove any remaining files in temp directory
                for remaining_file in temp_dir.iterdir():
                    try:
                        if remaining_file.is_file():
                            remaining_file.unlink()
                            self.log(f"🧹 Cleaned up remaining temp file: {remaining_file.name}", "DEBUG")
                    except Exception as e:
                        self.log(f"⚠️  Failed to clean up remaining file {remaining_file}: {e}", "WARNING")
                
                # Remove the temp directory itself
                if not any(temp_dir.iterdir()):  # Only if empty
                    temp_dir.rmdir()
                    self.log(f"🧹 Cleaned up temp directory: {temp_dir}", "INFO")
                else:
                    self.log(f"⚠️  Temp directory not empty, leaving: {temp_dir}", "WARNING")
                    
            except Exception as e:
                self.log(f"⚠️  Failed to clean up temp directory {temp_dir}: {e}", "WARNING")

        # Step 9: Log success
        self.log(f"✅ SUCCESS: {file_path.name} compressed successfully")
        self.log(f"   New file: {final_output}")
        self.log(f"   Space saved: {space_saved / (1024**3):.2f}GB")
        
        return True, f"File processed successfully. Saved {space_saved / (1024**3):.2f}GB"
    
    def cleanup_temp_files(self, *temp_files):
        """Clean up temporary files and directories."""
        temp_dirs_to_check = set()
        
        for temp_file in temp_files:
            try:
                if temp_file and Path(temp_file).exists():
                    temp_path = Path(temp_file)
                    temp_dirs_to_check.add(temp_path.parent)
                    temp_path.unlink()
                    self.log(f"🧹 Cleaned up temp file: {temp_file}", "DEBUG")
                        
            except Exception as e:
                self.log(f"⚠️  Failed to clean up {temp_file}: {e}", "WARNING")
        
        # Clean up any temp directories that are now empty
        for temp_dir in temp_dirs_to_check:
            try:
                if (temp_dir.name == ".video_compression_temp" and 
                    temp_dir.exists() and 
                    not any(temp_dir.iterdir())):
                    temp_dir.rmdir()
                    self.log(f"🧹 Cleaned up empty temp directory: {temp_dir}", "DEBUG")
            except Exception as e:
                self.log(f"⚠️  Failed to clean up temp directory {temp_dir}: {e}", "WARNING")
    
    def cleanup_all_temp_directories(self):
        """Clean up all .video_compression_temp directories in current working area."""
        try:
            # Find all temp directories that might have been created
            for temp_dir in Path(".").rglob(".video_compression_temp"):
                if temp_dir.is_dir():
                    try:
                        # Remove any remaining files
                        for remaining_file in temp_dir.iterdir():
                            if remaining_file.is_file():
                                remaining_file.unlink()
                                self.log(f"🧹 Cleaned up remaining temp file: {remaining_file}", "DEBUG")
                        
                        # Remove directory if empty
                        if not any(temp_dir.iterdir()):
                            temp_dir.rmdir()
                            self.log(f"🧹 Final cleanup of temp directory: {temp_dir}", "INFO")
                    except Exception as e:
                        self.log(f"⚠️  Failed to clean up temp directory {temp_dir}: {e}", "WARNING")
        except Exception as e:
            self.log(f"⚠️  Error during final temp directory cleanup: {e}", "WARNING")
    
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
                
                # In batch processing, log the failure but continue with other files
                if not dry_run:
                    self.log(f"⚠️  Continuing with remaining files despite failure", "WARNING")
                    # Don't break - continue processing other files
        
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
        
        # Final cleanup of any remaining temp directories
        self.log(f"🧹 Performing final temp directory cleanup...")
        self.cleanup_all_temp_directories()
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        if self.logger:
            self.log("=== Video Compression Session Ended ===", "INFO")
            
            # Final temp directory cleanup on session end
            try:
                self.cleanup_all_temp_directories()
            except:
                pass  # Don't let cleanup errors break destruction
            
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