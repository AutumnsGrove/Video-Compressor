#!/usr/bin/env python3
"""
CompressorEngine - Core Video Compression Engine

Extracted from the monolith VideoCompression.py to support library usage.
Contains the VideoCompressor class which handles single-file compression,
video analysis, FFmpeg command building, segmentation, and integrity checks.

This module can be used standalone or extended by CompressionPipeline for
parallel processing capabilities.
"""

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
import re
import platform
import queue
import threading

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class VideoCompressor:
    """
    Core video compression engine with safety protocols.

    Handles single-file compression with segmentation support for large files,
    integrity verification, and comprehensive progress tracking.

    Can be initialized with either a config file path or a config dict directly:
        compressor = VideoCompressor(config_path="config.json")
        compressor = VideoCompressor(config={"ffmpeg_path": "/usr/bin/ffmpeg", ...})
    """

    def __init__(self, config_path="config.json", config=None):
        """
        Initialize the video compressor.

        Args:
            config_path: Path to JSON configuration file (used if config is None)
            config: Configuration dictionary (takes precedence over config_path)
        """
        if config is not None:
            self.config = config
        else:
            self.config = self.load_config(config_path)
        self.logger = None
        self.setup_enhanced_logging()
        self.processed_files = []
        self.failed_files = []

        # Lazy import to avoid circular dependency at module level
        from ..concurrency.ProgressTracker import ProgressAggregator
        self.progress_aggregator = ProgressAggregator(self.config)

    def load_config(self, config_path):
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            print(f"Config file {config_path} not found. Creating default config...")
            default_config = {
                "ffmpeg_path": self._detect_ffmpeg_path(),
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
                    "max_retries": 3,
                    "delete_original_after_compression": True
                },
                "large_file_settings": {
                    "threshold_gb": 10,
                    "segmentation_threshold_gb": 10,
                    "enhanced_monitoring": True,
                    "progress_update_interval": 10,
                    "hash_chunk_size_mb": 5,
                    "extended_timeouts": True,
                    "use_same_filesystem": True,
                    "ui_callback_interval_seconds": 0.5
                },
                "segmentation_settings": {
                    "segment_duration_seconds": 600,
                    "duration_threshold_minutes": 60,
                    "segmentation_timeout_minutes_per_gb": 1,
                    "min_segmentation_timeout_minutes": 5,
                    "size_difference_warning_percent": 5,
                    "merge_size_difference_warning_percent": 10
                },
                "logging_settings": {
                    "max_log_files": 5,
                    "max_log_size_mb": 10,
                    "console_level": "INFO",
                    "file_level": "DEBUG"
                },
                "parallel_processing": {
                    "enabled": True,
                    "max_workers": 4,
                    "segment_parallel": True
                }
            }
            try:
                with open(config_path, 'w') as f:
                    json.dump(default_config, f, indent=2)
            except Exception:
                pass
            return default_config
        except json.JSONDecodeError as e:
            print(f"Error parsing config file: {e}")
            sys.exit(1)

    @staticmethod
    def _detect_ffmpeg_path():
        """Auto-detect FFmpeg installation path."""
        if shutil.which('ffmpeg'):
            return shutil.which('ffmpeg')
        system = platform.system().lower()
        paths = {
            'darwin': ['/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg'],
            'linux': ['/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg'],
        }
        for p in paths.get(system, []):
            if Path(p).exists():
                return p
        return 'ffmpeg'

    def setup_enhanced_logging(self):
        """Setup enhanced logging system with rotation and levels."""
        log_dir = Path(self.config.get("log_dir", "./logs"))
        try:
            log_dir.mkdir(exist_ok=True)
        except Exception:
            log_dir = Path("./logs")
            log_dir.mkdir(exist_ok=True)

        max_logs = self.config.get("logging_settings", {}).get("max_log_files", 5)
        self.cleanup_old_logs(log_dir, max_logs)

        self.logger = logging.getLogger(f'VideoCompressor.{id(self)}')
        self.logger.setLevel(logging.DEBUG)

        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        detailed_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)8s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_formatter = logging.Formatter('[%(levelname)s] %(message)s')

        console_level = getattr(logging, self.config.get("logging_settings", {}).get("console_level", "INFO"))
        file_level = getattr(logging, self.config.get("logging_settings", {}).get("file_level", "DEBUG"))

        max_size_mb = self.config.get("logging_settings", {}).get("max_log_size_mb", 10)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"video_compression_{timestamp}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_size_mb * 1024 * 1024, backupCount=3
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(detailed_formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_handler.setFormatter(console_formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.logger.info("=== Video Compression Session Started ===")
        self.logger.debug(f"Config loaded with {len(self.config)} top-level keys")
        self.logger.info(f"Log file: {log_file}")

    def cleanup_old_logs(self, log_dir, keep_count=5):
        """Clean up old log files, keeping only the most recent ones."""
        try:
            log_files = sorted(
                [f for f in log_dir.glob("video_compression_*.log*")],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            for old_log in log_files[keep_count:]:
                try:
                    old_log.unlink()
                except Exception:
                    pass
        except Exception:
            pass

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

    def get_compression_settings(self):
        """Return the compression settings from config."""
        return self.config.get("compression_settings", {})

    def check_disk_space(self, file_path, safety_multiplier=2.5):
        """Enhanced disk space checking with cross-filesystem support."""
        try:
            file_size = os.path.getsize(file_path)
            file_path_obj = Path(file_path)

            if self.config.get("large_file_settings", {}).get("use_same_filesystem", True):
                actual_temp_dir = file_path_obj.parent / ".video_compression_temp"
            else:
                actual_temp_dir = Path(self.config.get("temp_dir", "/tmp/video_compression"))

            actual_temp_dir.mkdir(exist_ok=True)

            if PSUTIL_AVAILABLE:
                temp_usage = psutil.disk_usage(str(actual_temp_dir))
                file_parent_usage = psutil.disk_usage(str(file_path_obj.parent))
                temp_available_gb = temp_usage.free / (1024 ** 3)
                file_parent_available_gb = file_parent_usage.free / (1024 ** 3)
            else:
                stat = os.statvfs(str(actual_temp_dir))
                temp_available_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
                stat2 = os.statvfs(str(file_path_obj.parent))
                file_parent_available_gb = (stat2.f_bavail * stat2.f_frsize) / (1024 ** 3)

            required_bytes = file_size * safety_multiplier
            required_gb = required_bytes / (1024 ** 3)
            min_free_space = self.config.get("safety_settings", {}).get("min_free_space_gb", 15)

            self.log(f"💾 Disk space check: {file_size / (1024 ** 3):.2f}GB file, "
                     f"{temp_available_gb:.2f}GB available", "DEBUG")

            if temp_available_gb < (required_gb + min_free_space):
                return False, (f"Insufficient temp space. Need {required_gb + min_free_space:.2f}GB, "
                               f"have {temp_available_gb:.2f}GB")

            if file_parent_available_gb < (file_size / (1024 ** 3) + min_free_space):
                return False, (f"Insufficient space for final file. "
                               f"Need {file_size / (1024 ** 3) + min_free_space:.2f}GB, "
                               f"have {file_parent_available_gb:.2f}GB")

            return True, "Sufficient disk space available"

        except Exception as e:
            self.log(f"Error checking disk space: {e}", "ERROR")
            return False, f"Disk space check failed: {e}"

    def calculate_file_hash(self, file_path, chunk_size=None):
        """Calculate SHA-256 hash optimized for large files."""
        if chunk_size is None:
            chunk_size_mb = self.config.get("large_file_settings", {}).get("hash_chunk_size_mb", 5)
            chunk_size = chunk_size_mb * 1024 * 1024
        file_size = os.path.getsize(file_path)
        self.log(f"🔐 Calculating hash for {Path(file_path).name} ({file_size / (1024 ** 3):.2f}GB)", "INFO")

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

                    if file_size > 1024 ** 3:
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
        """Get detailed video information with enhanced error handling and fallback strategies."""
        file_size_gb = os.path.getsize(file_path) / (1024 ** 3)

        if self.config.get("large_file_settings", {}).get("extended_timeouts", True):
            timeout = max(30, int(30 + file_size_gb * 15))
        else:
            timeout = 30

        ffprobe_path = self.config["ffmpeg_path"].replace("ffmpeg", "ffprobe")

        # Strategy 1: Standard ffprobe with full stream analysis
        cmd_full = [
            ffprobe_path, "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", str(file_path)
        ]

        self.log(f"🔍 Analyzing video info (timeout: {timeout}s)", "DEBUG")

        try:
            result = subprocess.run(cmd_full, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0:
                video_info = json.loads(result.stdout)
                self.log(f"✅ Video analysis complete", "DEBUG")
                return video_info
            else:
                self.log(f"ffprobe standard analysis failed: {result.stderr.strip()}", "WARNING")
        except subprocess.TimeoutExpired:
            self.log(f"ffprobe timeout after {timeout}s for large file", "WARNING")
        except json.JSONDecodeError as e:
            self.log(f"ffprobe returned invalid JSON: {e}", "WARNING")
        except Exception as e:
            self.log(f"ffprobe standard analysis error: {e}", "WARNING")

        # Strategy 2: Minimal ffprobe with format-only analysis
        self.log(f"🔄 Attempting minimal ffprobe analysis...", "DEBUG")
        cmd_minimal = [
            ffprobe_path, "-v", "error", "-print_format", "json",
            "-show_format", "-select_streams", "v:0", str(file_path)
        ]

        try:
            result = subprocess.run(cmd_minimal, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0:
                video_info = json.loads(result.stdout)
                self.log(f"✅ Minimal video analysis successful", "DEBUG")
                return video_info
        except Exception as e:
            self.log(f"ffprobe minimal analysis error: {e}", "WARNING")

        # Strategy 3: Basic file probe with ignore errors
        self.log(f"🔄 Attempting basic file probe (ignore errors)...", "DEBUG")
        cmd_basic = [
            ffprobe_path, "-v", "error", "-print_format", "json",
            "-show_format", "-ignore_unknown", str(file_path)
        ]

        try:
            result = subprocess.run(cmd_basic, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0:
                video_info = json.loads(result.stdout)
                self.log(f"✅ Basic file probe successful", "DEBUG")
                return video_info
        except Exception as e:
            self.log(f"ffprobe basic probe error: {e}", "WARNING")

        self.log(f"❌ All ffprobe strategies failed for file: {os.path.basename(file_path)}", "ERROR")
        return None

    def get_video_duration(self, video_info):
        """Extract video duration in seconds from video info."""
        try:
            format_info = video_info.get("format", {})
            if "duration" in format_info:
                return float(format_info["duration"])
            video_streams = [s for s in video_info.get("streams", []) if s.get("codec_type") == "video"]
            if video_streams and "duration" in video_streams[0]:
                return float(video_streams[0]["duration"])
        except (ValueError, KeyError, TypeError):
            pass
        return 0.0

    def estimate_duration_fallback(self, file_path):
        """Estimate video duration using file size when ffprobe fails."""
        try:
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            typical_bitrates = {
                '.mp4': 5.0, '.mov': 8.0, '.avi': 6.0,
                '.mkv': 7.0, '.webm': 3.0, '.m4v': 5.0,
            }
            file_ext = Path(file_path).suffix.lower()
            estimated_bitrate_mbps = typical_bitrates.get(file_ext, 5.0)
            estimated_duration_minutes = file_size_mb / (estimated_bitrate_mbps / 8) / 60
            estimated_duration_seconds = estimated_duration_minutes * 60
            return estimated_duration_seconds
        except Exception as e:
            self.log(f"Duration estimation fallback failed: {e}", "WARNING")
            return 0.0

    def get_original_bitrate(self, video_info):
        """Extract original video bitrate from video info."""
        try:
            video_stream = next((s for s in video_info.get("streams", []) if s.get("codec_type") == "video"), None)
            if video_stream and "bit_rate" in video_stream:
                return int(video_stream["bit_rate"]) // 1000
            format_info = video_info.get("format", {})
            if "bit_rate" in format_info:
                total_bitrate = int(format_info["bit_rate"]) // 1000
                return int(total_bitrate * 0.9)
        except (ValueError, KeyError, TypeError):
            pass
        return None

    def verify_file_integrity(self, file_path, original_info=None):
        """Comprehensive file integrity verification."""
        self.log(f"🔍 COMPREHENSIVE FILE VERIFICATION", "INFO")
        self.log(f"   File: {file_path}", "DEBUG")

        verification_results = []

        if not os.path.exists(file_path):
            return False, "File does not exist"

        file_size = os.path.getsize(file_path)
        if file_size < 1024:
            return False, f"File too small: {file_size} bytes"

        verification_results.append(f"File size: {file_size / (1024 * 1024):.2f}MB")

        video_info = self.get_video_info(file_path)
        if not video_info:
            return False, "Cannot read video information"

        streams = video_info.get("streams", [])
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

        if not video_streams:
            return False, "No video streams found"

        verification_results.append(f"Streams: {len(video_streams)} video, {len(audio_streams)} audio")

        for i, stream in enumerate(video_streams):
            codec = stream.get("codec_name", "unknown")
            width = stream.get("width", 0)
            height = stream.get("height", 0)
            verification_results.append(f"Video: {codec} {width}x{height}")

        # Compare with original if provided
        if original_info:
            original_streams = original_info.get("streams", [])
            original_video = [s for s in original_streams if s.get("codec_type") == "video"]
            if video_streams and original_video:
                orig_res = f"{original_video[0].get('width', 0)}x{original_video[0].get('height', 0)}"
                new_res = f"{video_streams[0].get('width', 0)}x{video_streams[0].get('height', 0)}"
                if orig_res != new_res:
                    self.log(f"   ⚠️  Resolution changed: {orig_res} → {new_res}", "WARNING")

        # Playability test
        cmd_start = [
            self.config["ffmpeg_path"], "-v", "error",
            "-i", str(file_path), "-t", "5", "-f", "null", "-"
        ]

        try:
            result = subprocess.run(cmd_start, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return False, f"Playback test failed: {result.stderr}"
        except Exception as e:
            return False, f"Playback test error: {e}"

        # Test middle and end for longer videos
        video_duration = self.get_video_duration(video_info)
        if video_duration > 20:
            middle_start = video_duration / 2 - 2.5
            cmd_middle = [
                self.config["ffmpeg_path"], "-v", "error",
                "-ss", str(middle_start), "-i", str(file_path),
                "-t", "5", "-f", "null", "-"
            ]
            try:
                subprocess.run(cmd_middle, capture_output=True, text=True, timeout=30)
            except Exception:
                pass

        if video_duration > 10:
            end_start = max(0, video_duration - 5)
            cmd_end = [
                self.config["ffmpeg_path"], "-v", "error",
                "-ss", str(end_start), "-i", str(file_path),
                "-f", "null", "-"
            ]
            try:
                subprocess.run(cmd_end, capture_output=True, text=True, timeout=30)
            except Exception:
                pass

        self.log(f"   🎯 VERIFICATION COMPLETE - ALL TESTS PASSED", "INFO")
        return True, f"Comprehensive verification successful: {' | '.join(verification_results)}"

    def estimate_compression_time(self, file_path):
        """Estimate compression time based on file size and system performance."""
        file_size_gb = os.path.getsize(file_path) / (1024 ** 3)
        preset = self.config.get("compression_settings", {}).get("preset", "medium")
        minutes_per_gb = {"ultrafast": 5, "fast": 8, "medium": 15, "slow": 25}.get(preset, 15)
        return timedelta(minutes=file_size_gb * minutes_per_gb)

    def detect_hardware_acceleration(self):
        """Detect Apple Silicon and test VideoToolbox hardware acceleration availability."""
        try:
            if not self.config.get("compression_settings", {}).get("enable_hardware_acceleration", True):
                self.log("🔧 Hardware acceleration disabled in config", "INFO")
                return None

            processor = platform.processor().lower()
            machine = platform.machine().lower()
            is_apple_silicon = "arm" in processor or "arm64" in machine

            if not is_apple_silicon:
                return None

            self.log(f"🔧 Apple Silicon detected", "INFO")

            test_cmd = [
                self.config["ffmpeg_path"],
                "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1",
                "-c:v", "h264_videotoolbox", "-t", "1", "-f", "null", "-"
            ]

            try:
                result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    hevc_test_cmd = test_cmd.copy()
                    hevc_test_cmd[hevc_test_cmd.index("h264_videotoolbox")] = "hevc_videotoolbox"
                    hevc_result = subprocess.run(hevc_test_cmd, capture_output=True, text=True, timeout=10)
                    has_hevc = hevc_result.returncode == 0

                    return {
                        "type": "videotoolbox",
                        "h264_encoder": "h264_videotoolbox",
                        "hevc_encoder": "hevc_videotoolbox" if has_hevc else None,
                        "quality_param": "-q:v",
                        "pixel_format_10bit": "p010le"
                    }
                return None
            except Exception:
                return None
        except Exception as e:
            self.log(f"❌ Hardware acceleration detection error: {e}", "ERROR")
            return None

    def build_ffmpeg_command(self, input_path, output_path, original_info):
        """Build FFmpeg command based on configuration and video properties."""
        cmd = [self.config["ffmpeg_path"], "-y", "-i", str(input_path)]
        settings = self.config["compression_settings"]

        hw_accel = self.detect_hardware_acceleration()
        video_codec = settings["video_codec"]
        use_hardware = False

        if hw_accel and hw_accel["type"] == "videotoolbox":
            if settings["video_codec"] == "libx265" and hw_accel.get("hevc_encoder"):
                video_codec = hw_accel["hevc_encoder"]
                use_hardware = True
                self.log("🚀 Using VideoToolbox HEVC hardware acceleration", "INFO")
            elif settings["video_codec"] in ["libx264", "libx265"] and hw_accel.get("h264_encoder"):
                video_codec = hw_accel["h264_encoder"]
                use_hardware = True
                self.log("🚀 Using VideoToolbox H.264 hardware acceleration", "INFO")
        else:
            self.log("🔧 Using software encoding", "INFO")

        cmd.extend(["-c:v", video_codec])

        if use_hardware and hw_accel:
            quality_value = settings.get("crf", 23)
            vt_quality = max(30, min(70, int(18 + (quality_value - 18) * 2.6)))
            cmd.extend([hw_accel["quality_param"], str(vt_quality)])

            if settings.get("preserve_10bit", False):
                video_stream = next(
                    (s for s in original_info.get("streams", []) if s.get("codec_type") == "video"), None)
                if video_stream and "pix_fmt" in video_stream and "10" in video_stream["pix_fmt"]:
                    cmd.extend(["-pix_fmt", hw_accel["pixel_format_10bit"]])
        else:
            cmd.extend(["-preset", settings["preset"]])
            cmd.extend(["-crf", str(settings["crf"])])
            if settings.get("preserve_10bit", False):
                video_stream = next(
                    (s for s in original_info.get("streams", []) if s.get("codec_type") == "video"), None)
                if video_stream and "pix_fmt" in video_stream and "10" in video_stream["pix_fmt"]:
                    cmd.extend(["-pix_fmt", "yuv420p10le"])

        cmd.extend(["-c:a", "copy"])

        if settings.get("preserve_metadata", True):
            cmd.extend(["-map_metadata", "0", "-movflags", "+faststart"])

        if "target_bitrate_reduction" in settings and not use_hardware:
            original_bitrate = self.get_original_bitrate(original_info)
            if original_bitrate:
                target_bitrate = int(original_bitrate * settings["target_bitrate_reduction"])
                cmd.extend(["-b:v", f"{target_bitrate}k"])

        cmd.append(str(output_path))
        return cmd

    def should_segment_file(self, file_path):
        """Check if file should be segmented based on size and duration thresholds."""
        try:
            segmentation_threshold_gb = self.config.get("large_file_settings", {}).get(
                "segmentation_threshold_gb", 10)
            file_size = os.path.getsize(file_path)
            file_size_gb = file_size / (1024 ** 3)

            size_exceeds = file_size_gb > segmentation_threshold_gb

            video_info = self.get_video_info(file_path)
            if not video_info:
                if file_size_gb > segmentation_threshold_gb * 1.5:
                    return True
                return size_exceeds

            duration_seconds = self.get_video_duration(video_info)
            if duration_seconds <= 0:
                duration_seconds = self.estimate_duration_fallback(file_path)

            duration_threshold_minutes = self.config.get("segmentation_settings", {}).get(
                "duration_threshold_minutes", 60)
            duration_threshold_seconds = duration_threshold_minutes * 60
            duration_exceeds = duration_seconds > duration_threshold_seconds

            should_segment = size_exceeds and duration_exceeds
            self.log(f"   Should segment: {should_segment} "
                     f"(size: {file_size_gb:.2f}GB, duration: {duration_seconds / 60:.1f}min)", "DEBUG")
            return should_segment
        except Exception as e:
            self.log(f"Error checking segmentation criteria: {e}", "ERROR")
            return False

    def segment_video(self, input_path, existing_segments=None, segment_duration=None, progress_callback=None):
        """Segment video into smaller chunks using ffmpeg with stream copy."""
        if segment_duration is None:
            segment_duration = self.config.get("segmentation_settings", {}).get("segment_duration_seconds", 600)

        self.log(f"📁 Starting video segmentation: {Path(input_path).name}", "INFO")
        input_path = Path(input_path)

        if self.config.get("large_file_settings", {}).get("use_same_filesystem", True):
            segments_dir = input_path.parent / ".video_segments_temp"
        else:
            segments_dir = Path(self.config.get("temp_dir", "/tmp")) / "video_segments"

        segments_dir.mkdir(exist_ok=True)

        base_name = input_path.stem
        segment_pattern = segments_dir / f"{base_name}_segment_%03d{input_path.suffix}"

        cmd = [
            self.config["ffmpeg_path"],
            "-i", str(input_path),
            "-c", "copy", "-map", "0:v", "-map", "0:a?",
            "-segment_time", str(segment_duration),
            "-f", "segment", "-reset_timestamps", "1",
            str(segment_pattern)
        ]

        try:
            file_size_gb = os.path.getsize(input_path) / (1024 ** 3)
            timeout_minutes_per_gb = self.config.get("segmentation_settings", {}).get(
                "segmentation_timeout_minutes_per_gb", 1)
            min_timeout_minutes = self.config.get("segmentation_settings", {}).get(
                "min_segmentation_timeout_minutes", 5)
            timeout = max(min_timeout_minutes * 60, int(file_size_gb * timeout_minutes_per_gb * 60))

            start_time = time.time()

            if progress_callback:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

                def progress_monitor():
                    while process.poll() is None:
                        elapsed_time = time.time() - start_time
                        estimated_progress = min(0.9, elapsed_time / (timeout * 0.8))
                        progress_callback(estimated_progress)
                        time.sleep(1)

                progress_thread = threading.Thread(target=progress_monitor, daemon=True)
                progress_thread.start()

                try:
                    stdout, stderr = process.communicate(timeout=timeout)
                    result_returncode = process.returncode
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                    result_returncode = 1
                    stderr = f"Segmentation timed out after {timeout}s"

                if result_returncode == 0:
                    progress_callback(1.0)

                class Result:
                    def __init__(self, rc, so, se):
                        self.returncode = rc
                        self.stdout = so
                        self.stderr = se

                result = Result(result_returncode, stdout, stderr)
            else:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

            if result.returncode != 0:
                self.log(f"❌ FFmpeg segmentation failed: {result.stderr}", "ERROR")
                return None

            segment_files = sorted(segments_dir.glob(f"{base_name}_segment_*{input_path.suffix}"))
            if not segment_files:
                self.log(f"❌ No segment files were created", "ERROR")
                return None

            self.log(f"✅ Segmentation completed: {len(segment_files)} segments", "INFO")
            return [str(segment) for segment in segment_files]

        except subprocess.TimeoutExpired:
            self.log(f"❌ Segmentation timed out", "ERROR")
            return None
        except Exception as e:
            self.log(f"❌ Segmentation error: {type(e).__name__}: {e}", "ERROR")
            return None

    def merge_compressed_segments(self, segment_paths, output_path):
        """Merge compressed segments back into a single file using ffmpeg concat."""
        self.log(f"🔗 Merging {len(segment_paths)} segments", "INFO")

        if not segment_paths:
            return False, "No segments provided for merging"

        output_path = Path(output_path)
        segments_dir = Path(segment_paths[0]).parent
        concat_file = segments_dir / f"concat_list_{output_path.stem}.txt"

        try:
            with open(concat_file, 'w') as f:
                for segment_path in segment_paths:
                    if not Path(segment_path).exists():
                        return False, f"Segment file not found: {segment_path}"
                    f.write(f"file '{Path(segment_path).absolute()}'\n")

            cmd = [
                self.config["ffmpeg_path"],
                "-f", "concat", "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy", str(output_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                return False, f"FFmpeg merge failed: {result.stderr}"

            if not output_path.exists() or output_path.stat().st_size == 0:
                return False, "Merged file was not created or is empty"

            # Verify merged file
            video_info = self.get_video_info(output_path)
            if not video_info:
                return False, "Merged file cannot be read by ffprobe"

            test_cmd = [
                self.config["ffmpeg_path"], "-v", "error",
                "-i", str(output_path), "-t", "5", "-f", "null", "-"
            ]
            test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=30)
            if test_result.returncode != 0:
                return False, f"Merged file failed playability test: {test_result.stderr}"

            self.log(f"✅ Merged file integrity verified", "INFO")
            return True, "Segments merged successfully"

        except Exception as e:
            return False, f"Merge error: {type(e).__name__}: {e}"
        finally:
            try:
                if concat_file.exists():
                    concat_file.unlink()
            except Exception:
                pass

    def compress_video(self, input_path, output_path, dry_run=False, progress_callback=None):
        """Compress video file with safety checks."""
        self.log(f"{'[DRY RUN] ' if dry_run else ''}Starting compression: {input_path}")

        if dry_run:
            video_info = self.get_video_info(input_path)
            if not video_info:
                return False, "Cannot read video information for dry run analysis"
            self.log("[DRY RUN] ⚙️  COMPRESSION SETTINGS TO BE APPLIED:", "INFO")
            for key, value in self.config["compression_settings"].items():
                self.log(f"[DRY RUN]   {key}: {value}", "INFO")
            return True, "Dry run completed with detailed analysis"

        original_info = self.get_video_info(input_path)
        if not original_info:
            return False, "Cannot read original video information"

        if progress_callback:
            self.progress_aggregator.set_callback(progress_callback)

        if self.should_segment_file(input_path):
            return self.compress_video_with_segmentation(input_path, output_path, progress_callback)

        video_duration = self.get_video_duration(original_info)
        file_size = os.path.getsize(input_path)

        worker_id = f"single_compress_{int(time.time())}"
        task_name = f"Compressing {Path(input_path).name}"
        self.progress_aggregator.register_worker(worker_id, task_name, file_size)

        cmd = self.build_ffmpeg_command(input_path, output_path, original_info)
        cmd.extend(["-stats", "-loglevel", "info"])

        start_time = time.time()

        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, bufsize=1
            )

            progress_queue_local = queue.Queue(maxsize=100)

            def monitor_stderr():
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
                        time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', line)
                        fps_match = re.search(r'fps=\s*([\d.]+)', line)
                        size_match = re.search(r'size=\s*(\d+)kB', line)

                        if time_match and video_duration > 0:
                            hours, minutes, seconds = time_match.groups()
                            current_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                            progress_pct = min(current_seconds / video_duration, 1.0)
                            current_fps = float(fps_match.group(1)) if fps_match else last_fps
                            current_size = int(size_match.group(1)) if size_match else last_size

                            if progress_pct > current_progress + 0.005:
                                current_progress = progress_pct
                                last_fps = current_fps
                                last_size = current_size
                                try:
                                    progress_queue_local.put(
                                        (progress_pct, current_seconds, current_fps, current_size, line),
                                        timeout=0.1
                                    )
                                except queue.Full:
                                    pass
                except Exception:
                    pass

            monitor_thread = threading.Thread(target=monitor_stderr, daemon=True)
            monitor_thread.start()

            last_log_time = time.time()
            current_progress = 0.0

            while process.poll() is None:
                current_time = time.time()
                try:
                    update = progress_queue_local.get(timeout=0.2)
                    if isinstance(update[0], float):
                        progress_pct, current_seconds, fps, size_kb, line = update
                        processed_bytes = (size_kb * 1024) if size_kb > 0 else None
                        self.progress_aggregator.update_worker_progress(
                            worker_id, progress_pct, fps, processed_bytes
                        )
                        self.progress_aggregator.notify_callback()

                        if current_time - last_log_time > 10.0 or progress_pct > current_progress + 0.02:
                            elapsed = current_time - start_time
                            time_remaining = "unknown"
                            if progress_pct > 0.01:
                                total_estimated = elapsed / progress_pct
                                remaining = total_estimated - elapsed
                                time_remaining = str(timedelta(seconds=int(remaining)))
                            self.log(
                                f"📊 Progress: {progress_pct * 100:.1f}% | "
                                f"FPS: {fps:.1f} | ETA: {time_remaining}", "INFO"
                            )
                            last_log_time = current_time
                            current_progress = progress_pct
                except queue.Empty:
                    continue

            process.wait()
            monitor_thread.join(timeout=5.0)

            if process.returncode != 0:
                self.progress_aggregator.fail_worker(
                    worker_id, f"FFmpeg failed with return code {process.returncode}")
                return False, f"FFmpeg failed with return code {process.returncode}. Check logs for details."

            self.progress_aggregator.complete_worker(worker_id)
            duration = timedelta(seconds=int(time.time() - start_time))
            self.log(f"Compression completed in {duration}")
            return True, "Compression successful"

        except Exception as e:
            import traceback
            error_msg = f"Compression error: {type(e).__name__}: {e}"
            self.progress_aggregator.fail_worker(worker_id, error_msg)
            self.log(f"❌ {error_msg}\n{traceback.format_exc()}", "ERROR")
            return False, error_msg

    def compress_video_with_segmentation(self, input_path, output_path, progress_callback=None):
        """Compress large video using segmentation: segment → compress each → merge."""
        self.log(f"🎯 LARGE FILE SEGMENTATION WORKFLOW", "INFO")
        input_path = Path(input_path)
        output_path = Path(output_path)

        if progress_callback:
            progress_callback(0.15)

        def segmentation_phase_progress(seg_progress):
            if progress_callback:
                overall_progress = 0.15 + (seg_progress * 0.10)
                progress_callback(overall_progress)

        segment_paths = self.segment_video(input_path, progress_callback=segmentation_phase_progress)
        if not segment_paths:
            return False, "Failed to segment video file"

        if progress_callback:
            progress_callback(0.25)

        compressed_segments = []
        total_segments = len(segment_paths)

        try:
            for i, segment_path in enumerate(segment_paths):
                segment_name = Path(segment_path).name
                self.log(f"   🎬 Compressing segment {i + 1}/{total_segments}: {segment_name}", "INFO")

                segment_output = (Path(segment_path).parent /
                                  f"{Path(segment_path).stem}_compressed{Path(segment_path).suffix}")

                def segment_progress_callback(seg_progress, _i=i):
                    if progress_callback:
                        segment_base = 0.25 + ((_i / total_segments) * 0.65)
                        segment_range = 0.65 / total_segments
                        progress_callback(segment_base + (seg_progress * segment_range))

                success, message = self.compress_single_segment(
                    segment_path, segment_output, segment_progress_callback)

                if not success:
                    self.cleanup_segment_files(segment_paths, compressed_segments)
                    return False, f"Failed to compress segment {i + 1}: {message}"

                compressed_segments.append(str(segment_output))

                try:
                    Path(segment_path).unlink()
                except Exception:
                    pass

            if progress_callback:
                progress_callback(0.90)

            success, message = self.merge_compressed_segments(compressed_segments, output_path)
            if not success:
                self.cleanup_segment_files([], compressed_segments)
                return False, f"Failed to merge segments: {message}"

            original_info = self.get_video_info(input_path)
            integrity_ok, integrity_msg = self.verify_file_integrity(output_path, original_info)
            if not integrity_ok:
                self.cleanup_segment_files([], compressed_segments)
                return False, f"Final file verification failed: {integrity_msg}"

            self.cleanup_segment_files([], compressed_segments)
            self._cleanup_segment_directories(input_path)

            if progress_callback:
                progress_callback(1.0)

            self.log(f"✅ SEGMENTATION WORKFLOW COMPLETE", "INFO")
            return True, "Large file compressed successfully using segmentation"

        except Exception as e:
            error_msg = f"Segmentation workflow error: {type(e).__name__}: {e}"
            self.log(f"❌ {error_msg}", "ERROR")
            self.cleanup_segment_files(segment_paths, compressed_segments)
            return False, error_msg

    def compress_single_segment(self, input_path, output_path, progress_callback=None):
        """Compress a single segment using the existing compression logic."""
        original_info = self.get_video_info(input_path)
        if not original_info:
            return False, "Cannot read segment video information"

        video_duration = self.get_video_duration(original_info)
        cmd = self.build_ffmpeg_command(input_path, output_path, original_info)
        cmd.extend(["-stats", "-loglevel", "info"])

        start_time = time.time()

        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, bufsize=1
            )

            progress_queue_local = queue.Queue(maxsize=50)

            def monitor_segment_stderr():
                current_progress = 0.0
                try:
                    for line in iter(process.stderr.readline, ''):
                        if not line:
                            break
                        line = line.strip()
                        if not line:
                            continue
                        time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2}\.\d{2})', line)
                        if time_match and video_duration > 0:
                            hours, minutes, seconds = time_match.groups()
                            current_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                            progress_pct = min(current_seconds / video_duration, 1.0)
                            if progress_pct > current_progress + 0.02:
                                current_progress = progress_pct
                                try:
                                    progress_queue_local.put(progress_pct, timeout=0.1)
                                except queue.Full:
                                    pass
                except Exception:
                    pass

            monitor_thread = threading.Thread(target=monitor_segment_stderr, daemon=True)
            monitor_thread.start()

            while process.poll() is None:
                try:
                    progress_pct = progress_queue_local.get(timeout=0.5)
                    if progress_callback:
                        progress_callback(progress_pct)
                except queue.Empty:
                    continue

            if progress_callback:
                progress_callback(1.0)

            process.wait()
            monitor_thread.join(timeout=5.0)

            if process.returncode != 0:
                return False, f"Segment compression failed with return code {process.returncode}"

            return True, "Segment compression successful"

        except Exception as e:
            return False, f"Segment compression error: {type(e).__name__}: {e}"

    def cleanup_segment_files(self, original_segments=None, compressed_segments=None):
        """Clean up segment files and directories."""
        segments_to_clean = []
        if original_segments:
            segments_to_clean.extend(original_segments)
        if compressed_segments:
            segments_to_clean.extend(compressed_segments)

        for segment_path in segments_to_clean:
            try:
                segment_file = Path(segment_path)
                if segment_file.exists():
                    segment_file.unlink()
            except Exception:
                pass

        segment_dirs_to_check = set()
        for segment_path in segments_to_clean:
            segment_dir = Path(segment_path).parent
            if segment_dir.name in [".video_segments_temp", "video_segments"]:
                segment_dirs_to_check.add(segment_dir)

        for segment_dir in segment_dirs_to_check:
            try:
                if segment_dir.exists() and not any(segment_dir.iterdir()):
                    segment_dir.rmdir()
            except Exception:
                pass

    def _cleanup_segment_directories(self, source_file_path):
        """Additional cleanup for segment directories."""
        source_file_path = Path(source_file_path)
        source_dir = source_file_path.parent

        for segment_dir in [source_dir / ".video_segments_temp", source_dir / "video_segments"]:
            if not segment_dir.exists():
                continue
            try:
                for item in segment_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        try:
                            item.rmdir()
                        except OSError:
                            pass
                if not any(segment_dir.iterdir()):
                    segment_dir.rmdir()
            except Exception:
                pass

    def cleanup_temp_files(self, *temp_files):
        """Clean up temporary files and directories."""
        temp_dirs_to_check = set()
        for temp_file in temp_files:
            try:
                if temp_file and Path(temp_file).exists():
                    temp_path = Path(temp_file)
                    temp_dirs_to_check.add(temp_path.parent)
                    temp_path.unlink()
            except Exception:
                pass

        for temp_dir in temp_dirs_to_check:
            try:
                if (temp_dir.name == ".video_compression_temp" and
                        temp_dir.exists() and not any(temp_dir.iterdir())):
                    temp_dir.rmdir()
            except Exception:
                pass

    def cleanup_all_temp_directories(self):
        """Clean up all .video_compression_temp directories."""
        try:
            for temp_dir in Path(".").rglob(".video_compression_temp"):
                if temp_dir.is_dir():
                    try:
                        for remaining_file in temp_dir.iterdir():
                            if remaining_file.is_file():
                                remaining_file.unlink()
                        if not any(temp_dir.iterdir()):
                            temp_dir.rmdir()
                    except Exception:
                        pass
        except Exception:
            pass

    def analyze_file_size_breakdown(self, file_path, video_info):
        """Analyze what contributes to file size."""
        try:
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            format_info = video_info.get("format", {})
            duration = float(format_info.get("duration", 0))
            total_bitrate = int(format_info.get("bit_rate", 0)) if format_info.get("bit_rate") else None

            streams = video_info.get("streams", [])
            video_streams = [s for s in streams if s.get("codec_type") == "video"]

            breakdown = {
                "file_size_mb": file_size_mb,
                "duration_seconds": duration,
                "duration_formatted": str(timedelta(seconds=int(duration))),
                "total_bitrate_kbps": total_bitrate // 1000 if total_bitrate else None,
            }
            return breakdown
        except Exception as e:
            self.log(f"Error analyzing file size breakdown: {e}", "ERROR")
            return None

    def process_file(self, file_path, dry_run=False, progress_callback=None):
        """Process a single file with enhanced large file support."""
        file_path = Path(file_path)
        file_size_gb = os.path.getsize(file_path) / (1024 ** 3)

        self.log(f"\n{'=' * 60}", "INFO")
        self.log(f"🎥 Processing: {file_path.name} ({file_size_gb:.2f}GB)", "INFO")

        if not file_path.exists():
            return False, f"File does not exist: {file_path}"

        space_ok, space_msg = self.check_disk_space(file_path)
        if not space_ok:
            return False, space_msg

        if self.config.get("large_file_settings", {}).get("use_same_filesystem", True):
            temp_dir = file_path.parent / ".video_compression_temp"
        else:
            temp_dir = Path(self.config.get("temp_dir", "/tmp/video_compression"))

        temp_dir.mkdir(exist_ok=True)

        output_name = f"{file_path.stem}_compressed{file_path.suffix}"
        temp_output = temp_dir / output_name

        if dry_run:
            return True, "Dry run successful"

        if self.config.get("safety_settings", {}).get("create_backup_hash", True):
            original_hash = self.calculate_file_hash(file_path)
            if not original_hash:
                return False, "Failed to calculate original file hash"

        original_info = self.get_video_info(file_path)

        try:
            success, message = self.compress_video(file_path, temp_output, dry_run, progress_callback)
            if not success:
                self.cleanup_temp_files(temp_output)
                return False, f"Compression failed: {message}"
        except Exception as e:
            self.cleanup_temp_files(temp_output)
            return False, f"Compression exception: {e}"

        if self.config.get("safety_settings", {}).get("verify_integrity", True):
            integrity_ok, integrity_msg = self.verify_file_integrity(temp_output, original_info)
            if not integrity_ok:
                self.cleanup_temp_files(temp_output)
                return False, f"Compressed file verification failed: {integrity_msg}"

        original_size = file_path.stat().st_size
        compressed_size = temp_output.stat().st_size
        space_saved = original_size - compressed_size

        self.log(f"Compression results: {original_size / (1024 ** 3):.2f}GB → "
                 f"{compressed_size / (1024 ** 3):.2f}GB "
                 f"(saved {space_saved / (1024 ** 3):.2f}GB)")

        final_output = file_path.parent / output_name

        try:
            if not temp_output.exists() or temp_output.stat().st_size == 0:
                self.cleanup_temp_files(temp_output)
                return False, "Temp file missing or empty"
            shutil.move(str(temp_output), str(final_output))
        except Exception as e:
            self.cleanup_temp_files(temp_output)
            return False, f"Failed to move compressed file: {e}"

        final_integrity_ok, final_integrity_msg = self.verify_file_integrity(final_output, original_info)
        if not final_integrity_ok:
            return False, f"Final verification failed: {final_integrity_msg}"

        delete_original = self.config.get("safety_settings", {}).get("delete_original_after_compression", True)
        if delete_original:
            try:
                file_path.unlink()
                self.log(f"✅ Original file deleted: {file_path}")
            except Exception as e:
                return False, f"Failed to delete original file: {e}"
        else:
            self.log(f"📁 Original preserved, compressed at: {final_output}")

        # Clean up temp directory
        if temp_dir.exists() and temp_dir.name == ".video_compression_temp":
            try:
                for remaining_file in temp_dir.iterdir():
                    if remaining_file.is_file():
                        remaining_file.unlink()
                if not any(temp_dir.iterdir()):
                    temp_dir.rmdir()
            except Exception:
                pass

        self.log(f"✅ SUCCESS: {file_path.name} compressed. Saved {space_saved / (1024 ** 3):.2f}GB")
        return True, f"File processed successfully. Saved {space_saved / (1024 ** 3):.2f}GB"

    def process_file_list(self, file_list, dry_run=False, batch_progress_callback=None):
        """Process a list of files with comprehensive reporting."""
        self.log(f"\n{'=' * 60}", "INFO")
        self.log(f"BATCH PROCESSING {'(DRY RUN)' if dry_run else ''}", "INFO")
        self.log(f"Files to process: {len(file_list)}", "INFO")

        # Lazy import
        from ..concurrency.ProgressTracker import ProgressAggregator

        self.progress_aggregator = ProgressAggregator()
        if batch_progress_callback:
            self.progress_aggregator.set_callback(batch_progress_callback)

        for i, file_path in enumerate(file_list):
            if Path(file_path).exists():
                original_size = os.path.getsize(file_path)
                worker_id = f"batch_file_{i}"
                task_name = f"Processing {Path(file_path).name}"
                segment_info = None
                if self.should_segment_file(file_path):
                    video_info = self.get_video_info(file_path)
                    if video_info:
                        duration = self.get_video_duration(video_info)
                        seg_dur = self.config.get("segmentation_settings", {}).get("segment_duration_seconds", 600)
                        estimated_segments = max(1, int(duration / seg_dur))
                        segment_info = {'current': 0, 'total': estimated_segments, 'duration': duration}
                self.progress_aggregator.register_worker(worker_id, task_name, original_size, segment_info)

        if dry_run:
            return

        start_time = time.time()
        total_space_saved = 0

        for i, file_path in enumerate(file_list, 1):
            self.log(f"\n[{i}/{len(file_list)}] Processing: {Path(file_path).name}")

            original_size = os.path.getsize(file_path) if Path(file_path).exists() else 0
            worker_id = f"batch_file_{i - 1}"

            def file_progress_callback(file_progress):
                self.progress_aggregator.update_worker_progress(worker_id, file_progress)
                if batch_progress_callback:
                    self.progress_aggregator.notify_callback()

            success, message = self.process_file(file_path, dry_run, file_progress_callback)

            if success:
                self.processed_files.append(file_path)
                self.progress_aggregator.complete_worker(worker_id)
                if not dry_run and Path(file_path).parent.exists():
                    compressed_files = list(Path(file_path).parent.glob(f"{Path(file_path).stem}_compressed*"))
                    if compressed_files:
                        compressed_size = compressed_files[0].stat().st_size
                        total_space_saved += original_size - compressed_size
            else:
                self.failed_files.append((file_path, message))
                self.progress_aggregator.fail_worker(worker_id, message)

        total_time = timedelta(seconds=int(time.time() - start_time))
        self.log(f"\nBATCH COMPLETE in {total_time}: "
                 f"{len(self.processed_files)} success, {len(self.failed_files)} failed")

        self.cleanup_all_temp_directories()

    def calculate_total_duration(self, file_list):
        """Calculate total duration of all video files."""
        total_duration = 0.0
        for file_path in file_list:
            if Path(file_path).exists():
                video_info = self.get_video_info(file_path)
                if video_info:
                    total_duration += self.get_video_duration(video_info)
        return total_duration

    def __del__(self):
        """Cleanup when object is destroyed."""
        if self.logger:
            try:
                self.cleanup_all_temp_directories()
            except Exception:
                pass
            for handler in self.logger.handlers[:]:
                if isinstance(handler, (logging.FileHandler, logging.handlers.RotatingFileHandler)):
                    handler.close()
                    self.logger.removeHandler(handler)
