#!/usr/bin/env python3
"""
FFmpeg Runner - FFmpeg Command Execution and Management

This module centralizes all FFmpeg-related operations for the video compression system.
It provides a clean interface for building commands, executing them, and handling
hardware acceleration detection and configuration.

Key components:
- FFmpegCommandBuilder: Template-based command construction
- FFmpegRunner: Process execution and monitoring
- HardwareAccelerationDetector: Platform-specific acceleration detection
- VideoAnalyzer: Video metadata extraction and analysis

All subprocess operations are centralized here to ensure consistent error handling,
timeout management, and logging across the application.
"""

import os
import json
import subprocess
import time
import platform
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import threading


class HardwareAccelerationDetector:
    """
    Detects and configures hardware acceleration capabilities.
    
    This class handles platform-specific hardware acceleration detection,
    particularly for Apple Silicon VideoToolbox integration.
    """
    
    def __init__(self, ffmpeg_path: str, logger=None):
        """
        Initialize hardware acceleration detector.
        
        Args:
            ffmpeg_path: Path to FFmpeg executable
            logger: Logging function (optional)
        """
        self.ffmpeg_path = ffmpeg_path
        self.log = logger if logger else lambda msg, level="INFO": print(f"[{level}] {msg}")
        self._hw_accel_cache = None
    
    def detect_hardware_acceleration(self) -> Optional[Dict[str, Any]]:
        """
        Detect available hardware acceleration with caching.
        
        Performs comprehensive hardware acceleration detection including:
        - Platform identification (Apple Silicon, Intel, etc.)
        - Available encoder testing
        - Quality parameter mapping
        - Pixel format support
        
        Returns:
            Dict containing hardware acceleration info or None if not available
            
        Example return value:
        {
            'type': 'videotoolbox',
            'h264_encoder': 'h264_videotoolbox',
            'hevc_encoder': 'hevc_videotoolbox',
            'quality_param': '-q:v',
            'pixel_format_10bit': 'p010le'
        }
        """
        # Return cached result if available
        if self._hw_accel_cache is not None:
            return self._hw_accel_cache
        
        try:
            self.log("🚀 Detecting hardware acceleration capabilities...", "INFO")
            
            # Platform detection
            processor = platform.processor().lower()
            machine = platform.machine().lower()
            is_apple_silicon = "arm" in processor or "arm64" in machine
            
            self.log(f"   Platform: {processor}, Machine: {machine}", "DEBUG")
            
            if not is_apple_silicon:
                self.log("   Non-Apple Silicon platform - VideoToolbox not available", "DEBUG")
                self._hw_accel_cache = None
                return None
            
            # Test VideoToolbox encoders
            hw_info = {
                'type': 'videotoolbox',
                'h264_encoder': None,
                'hevc_encoder': None,
                'quality_param': '-q:v',
                'pixel_format_10bit': 'p010le'
            }
            
            # Test H.264 VideoToolbox encoder
            if self._test_encoder('h264_videotoolbox'):
                hw_info['h264_encoder'] = 'h264_videotoolbox'
                self.log("   ✅ H.264 VideoToolbox encoder available", "DEBUG")
            
            # Test HEVC VideoToolbox encoder
            if self._test_encoder('hevc_videotoolbox'):
                hw_info['hevc_encoder'] = 'hevc_videotoolbox'
                self.log("   ✅ HEVC VideoToolbox encoder available", "DEBUG")
            
            # Validate at least one encoder is available
            if hw_info['h264_encoder'] or hw_info['hevc_encoder']:
                self.log("🚀 VideoToolbox hardware acceleration confirmed", "INFO")
                self._hw_accel_cache = hw_info
                return hw_info
            else:
                self.log("❌ No VideoToolbox encoders available", "WARNING")
                self._hw_accel_cache = None
                return None
                
        except Exception as e:
            self.log(f"❌ Hardware acceleration detection error: {e}", "ERROR")
            self._hw_accel_cache = None
            return None
    
    def _test_encoder(self, encoder_name: str, timeout: int = 10) -> bool:
        """
        Test if a specific encoder is available and functional.
        
        Args:
            encoder_name: Name of encoder to test (e.g., 'h264_videotoolbox')
            timeout: Test timeout in seconds
            
        Returns:
            True if encoder is available and functional
        """
        try:
            # Create a minimal test command
            test_cmd = [
                self.ffmpeg_path,
                "-f", "lavfi",
                "-i", "testsrc2=duration=1:size=64x64:rate=1",
                "-c:v", encoder_name,
                "-t", "1",
                "-f", "null", "-"
            ]
            
            self.log(f"   Testing encoder: {encoder_name}", "DEBUG")
            
            result = subprocess.run(
                test_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            success = result.returncode == 0
            if not success:
                self.log(f"   Encoder test failed: {result.stderr.split()[-50:]}", "DEBUG")
            
            return success
            
        except subprocess.TimeoutExpired:
            self.log(f"   Encoder test timed out: {encoder_name}", "DEBUG")
            return False
        except Exception as e:
            self.log(f"   Encoder test error: {encoder_name} - {e}", "DEBUG")
            return False


class VideoAnalyzer:
    """
    Handles video file analysis and metadata extraction.
    
    This class provides robust video analysis with multiple fallback strategies
    to handle various file formats and edge cases.
    """
    
    def __init__(self, ffprobe_path: str, logger=None):
        """
        Initialize video analyzer.
        
        Args:
            ffprobe_path: Path to ffprobe executable
            logger: Logging function (optional)
        """
        self.ffprobe_path = ffprobe_path
        self.log = logger if logger else lambda msg, level="INFO": print(f"[{level}] {msg}")
    
    def get_video_info(self, file_path: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """
        Extract comprehensive video information with multiple fallback strategies.
        
        Attempts multiple analysis strategies in order of robustness:
        1. Full metadata extraction
        2. Minimal stream analysis (ignore problematic streams)
        3. Basic file probe with error tolerance
        
        Args:
            file_path: Path to video file
            timeout: Analysis timeout in seconds
            
        Returns:
            Dict containing video metadata or None if all strategies fail
        """
        self.log(f"📊 Analyzing video: {Path(file_path).name}", "DEBUG")
        
        # Strategy 1: Full metadata extraction
        if info := self._try_full_analysis(file_path, timeout):
            return info
        
        # Strategy 2: Minimal stream analysis
        if info := self._try_minimal_analysis(file_path, timeout):
            return info
        
        # Strategy 3: Basic file probe
        if info := self._try_basic_probe(file_path, timeout):
            return info
        
        self.log(f"❌ All ffprobe strategies failed for: {Path(file_path).name}", "ERROR")
        return None
    
    def _try_full_analysis(self, file_path: str, timeout: int) -> Optional[Dict[str, Any]]:
        """Attempt full metadata extraction."""
        self.log("🔄 Attempting full metadata analysis...", "DEBUG")
        
        cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path)
        ]
        
        return self._run_ffprobe_command(cmd, timeout, "full")
    
    def _try_minimal_analysis(self, file_path: str, timeout: int) -> Optional[Dict[str, Any]]:
        """Attempt minimal stream analysis, ignoring data streams."""
        self.log("🔄 Attempting minimal stream analysis...", "DEBUG")
        
        cmd = [
            self.ffprobe_path,
            "-v", "error", 
            "-select_streams", "v:0",  # Only first video stream
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path)
        ]
        
        return self._run_ffprobe_command(cmd, timeout, "minimal")
    
    def _try_basic_probe(self, file_path: str, timeout: int) -> Optional[Dict[str, Any]]:
        """Attempt basic file probe with maximum error tolerance."""
        self.log("🔄 Attempting basic file probe (ignore errors)...", "DEBUG")
        
        cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-ignore_unknown",
            str(file_path)
        ]
        
        return self._run_ffprobe_command(cmd, timeout, "basic")
    
    def _run_ffprobe_command(self, cmd: List[str], timeout: int, strategy: str) -> Optional[Dict[str, Any]]:
        """Execute ffprobe command with error handling."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode == 0:
                video_info = json.loads(result.stdout)
                self.log(f"✅ {strategy.title()} analysis successful", "DEBUG")
                return video_info
            else:
                self.log(f"ffprobe {strategy} analysis failed: {result.stderr.strip()}", "WARNING")
                
        except subprocess.TimeoutExpired:
            self.log(f"ffprobe {strategy} timeout after {timeout}s", "WARNING")
        except json.JSONDecodeError as e:
            self.log(f"ffprobe {strategy} returned invalid JSON: {e}", "WARNING")
        except Exception as e:
            self.log(f"ffprobe {strategy} analysis error: {e}", "WARNING")
            
        return None
    
    def get_video_duration(self, video_info: Dict[str, Any]) -> float:
        """
        Extract video duration from metadata.
        
        Args:
            video_info: Video metadata dict from get_video_info()
            
        Returns:
            Duration in seconds, or 0.0 if unavailable
        """
        try:
            # Try format duration first
            if format_info := video_info.get("format", {}):
                if duration := format_info.get("duration"):
                    return float(duration)
            
            # Fallback to video stream duration
            video_streams = [s for s in video_info.get("streams", []) if s.get("codec_type") == "video"]
            if video_streams and "duration" in video_streams[0]:
                return float(video_streams[0]["duration"])
                
        except (ValueError, KeyError, TypeError):
            pass
            
        return 0.0
    
    def estimate_duration_fallback(self, file_path: str) -> float:
        """
        Estimate video duration based on file size when metadata is unavailable.
        
        Uses typical bitrate estimates for different container formats to
        provide a rough duration estimate for progress tracking purposes.
        
        Args:
            file_path: Path to video file
            
        Returns:
            Estimated duration in seconds
        """
        try:
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # Typical bitrates by container format (Mbps)
            typical_bitrates = {
                '.mp4': 5.0,   # H.264/H.265 in MP4
                '.mov': 8.0,   # ProRes/high quality
                '.avi': 6.0,   # Various codecs
                '.mkv': 7.0,   # High quality container
                '.webm': 3.0,  # Web-optimized
                '.m4v': 5.0,   # iTunes format
                '.flv': 2.0,   # Flash video
                '.wmv': 4.0    # Windows media
            }
            
            file_ext = Path(file_path).suffix.lower()
            estimated_bitrate_mbps = typical_bitrates.get(file_ext, 5.0)
            
            # Calculate duration: file_size_mb / (bitrate_mbps / 8 bits_per_byte) / 60 seconds_per_minute
            estimated_duration_seconds = file_size_mb / (estimated_bitrate_mbps / 8) / 60 * 60
            
            self.log(f"📊 Duration estimation:", "DEBUG")
            self.log(f"   File size: {file_size_mb:.1f}MB", "DEBUG") 
            self.log(f"   Estimated bitrate: {estimated_bitrate_mbps} Mbps", "DEBUG")
            self.log(f"   Estimated duration: {estimated_duration_seconds/60:.1f} minutes", "DEBUG")
            
            return estimated_duration_seconds
            
        except Exception as e:
            self.log(f"Duration estimation fallback failed: {e}", "WARNING")
            return 0.0


class FFmpegCommandBuilder:
    """
    Template-based FFmpeg command construction.
    
    This class provides a clean interface for building complex FFmpeg commands
    with hardware acceleration, quality settings, and stream handling.
    """
    
    def __init__(self, config: Dict[str, Any], hw_detector: HardwareAccelerationDetector, logger=None):
        """
        Initialize command builder.
        
        Args:
            config: Configuration dictionary
            hw_detector: Hardware acceleration detector instance
            logger: Logging function (optional)
        """
        self.config = config
        self.hw_detector = hw_detector
        self.log = logger if logger else lambda msg, level="INFO": print(f"[{level}] {msg}")
    
    def build_compression_command(self, input_path: str, output_path: str, original_info: Dict[str, Any]) -> List[str]:
        """
        Build comprehensive FFmpeg compression command.
        
        Constructs optimized FFmpeg command considering:
        - Hardware acceleration capabilities
        - Video quality settings (CRF/bitrate)
        - Audio stream preservation
        - Metadata handling
        - 10-bit content support
        
        Args:
            input_path: Source video file path
            output_path: Output video file path
            original_info: Video metadata from VideoAnalyzer
            
        Returns:
            Complete FFmpeg command as list of strings
        """
        cmd = [self.config["ffmpeg_path"], "-y", "-i", str(input_path)]
        settings = self.config["compression_settings"]
        
        # Detect and configure hardware acceleration
        hw_accel = self.hw_detector.detect_hardware_acceleration()
        video_codec, use_hardware = self._determine_codec(settings, hw_accel, original_info)
        
        # Add video codec
        cmd.extend(["-c:v", video_codec])
        
        # Configure codec-specific parameters
        if use_hardware and hw_accel:
            self._add_hardware_params(cmd, settings, hw_accel, original_info)
        else:
            self._add_software_params(cmd, settings, original_info)
        
        # Audio handling - preserve without reencoding
        cmd.extend(["-c:a", "copy"])
        
        # Metadata preservation
        if settings.get("preserve_metadata", True):
            cmd.extend(["-map_metadata", "0", "-movflags", "+faststart"])
        
        # Target bitrate for software encoding only
        if "target_bitrate_reduction" in settings and not use_hardware:
            self._add_bitrate_params(cmd, settings, original_info)
        
        cmd.append(str(output_path))
        
        # Log encoding method
        encoder_info = f"VideoToolbox {video_codec}" if use_hardware else f"Software {video_codec}"
        self.log(f"🎬 Encoder: {encoder_info}", "INFO")
        
        return cmd
    
    def build_segmentation_command(self, input_path: str, segment_pattern: str, segment_duration: int) -> List[str]:
        """
        Build FFmpeg segmentation command for large file processing.
        
        Creates command for splitting video into segments using stream copy
        for maximum speed (no reencoding during segmentation).
        
        Args:
            input_path: Source video file
            segment_pattern: Output filename pattern (e.g., "segment_%03d.mp4")
            segment_duration: Segment length in seconds
            
        Returns:
            FFmpeg segmentation command
        """
        return [
            self.config["ffmpeg_path"],
            "-i", str(input_path),
            "-c", "copy",  # Stream copy for speed
            "-map", "0:v",  # Video streams
            "-map", "0:a?",  # Audio streams (optional)
            "-segment_time", str(segment_duration),
            "-f", "segment",
            "-reset_timestamps", "1",
            str(segment_pattern)
        ]
    
    def _determine_codec(self, settings: Dict[str, Any], hw_accel: Optional[Dict[str, Any]], 
                        original_info: Dict[str, Any]) -> Tuple[str, bool]:
        """Determine optimal codec and hardware acceleration usage."""
        video_codec = settings["video_codec"]
        use_hardware = False
        
        if hw_accel and hw_accel["type"] == "videotoolbox":
            # Choose hardware codec based on settings and availability
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
        
        return video_codec, use_hardware
    
    def _add_hardware_params(self, cmd: List[str], settings: Dict[str, Any], 
                           hw_accel: Dict[str, Any], original_info: Dict[str, Any]) -> None:
        """Add VideoToolbox-specific parameters."""
        # Convert CRF to VideoToolbox quality scale
        quality_value = settings.get("crf", 23)
        vt_quality = max(30, min(70, int(18 + (quality_value - 18) * 2.6)))
        cmd.extend([hw_accel["quality_param"], str(vt_quality)])
        
        self.log(f"🎛️  VideoToolbox quality: {vt_quality} (from CRF {quality_value})", "DEBUG")
        
        # Handle 10-bit content
        if settings.get("preserve_10bit", False):
            video_stream = next((s for s in original_info.get("streams", []) if s.get("codec_type") == "video"), None)
            if video_stream and "pix_fmt" in video_stream and "10" in video_stream["pix_fmt"]:
                cmd.extend(["-pix_fmt", hw_accel["pixel_format_10bit"]])
                self.log("🎨 Using 10-bit pixel format for VideoToolbox", "DEBUG")
    
    def _add_software_params(self, cmd: List[str], settings: Dict[str, Any], original_info: Dict[str, Any]) -> None:
        """Add software encoding parameters."""
        cmd.extend(["-preset", settings["preset"]])
        cmd.extend(["-crf", str(settings["crf"])])
        
        # Preserve 10-bit for software encoding
        if settings.get("preserve_10bit", False):
            video_stream = next((s for s in original_info.get("streams", []) if s.get("codec_type") == "video"), None)
            if video_stream and "pix_fmt" in video_stream and "10" in video_stream["pix_fmt"]:
                cmd.extend(["-pix_fmt", "yuv420p10le"])
    
    def _add_bitrate_params(self, cmd: List[str], settings: Dict[str, Any], original_info: Dict[str, Any]) -> None:
        """Add bitrate limiting parameters."""
        original_bitrate = self._get_original_bitrate(original_info)
        if original_bitrate:
            target_bitrate = int(original_bitrate * settings["target_bitrate_reduction"])
            cmd.extend(["-b:v", f"{target_bitrate}k"])
            self.log(f"📊 Target bitrate: {target_bitrate}k (reduced from {original_bitrate}k)", "DEBUG")
    
    def _get_original_bitrate(self, video_info: Dict[str, Any]) -> Optional[int]:
        """Extract original video bitrate from metadata."""
        try:
            # Try format bitrate first
            if format_info := video_info.get("format", {}):
                if bit_rate := format_info.get("bit_rate"):
                    return int(bit_rate) // 1000  # Convert to kbps
            
            # Fallback to video stream bitrate
            video_streams = [s for s in video_info.get("streams", []) if s.get("codec_type") == "video"]
            if video_streams and "bit_rate" in video_streams[0]:
                return int(video_streams[0]["bit_rate"]) // 1000
                
        except (ValueError, KeyError, TypeError):
            pass
            
        return None


class FFmpegRunner:
    """
    FFmpeg process execution and monitoring.
    
    This class handles the actual execution of FFmpeg commands with progress
    monitoring, timeout management, and error handling.
    """
    
    def __init__(self, logger=None):
        """
        Initialize FFmpeg runner.
        
        Args:
            logger: Logging function (optional)
        """
        self.log = logger if logger else lambda msg, level="INFO": print(f"[{level}] {msg}")
    
    def run_compression(self, cmd: List[str], timeout: Optional[int] = None, 
                       progress_callback=None) -> Tuple[bool, str]:
        """
        Execute FFmpeg compression command with progress monitoring.
        
        Args:
            cmd: FFmpeg command as list of strings
            timeout: Optional timeout in seconds
            progress_callback: Optional progress callback function
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        self.log(f"🎬 Starting FFmpeg compression...", "INFO")
        self.log(f"Command: {' '.join(cmd[:8])}... [truncated for brevity]", "DEBUG")
        
        try:
            if progress_callback:
                return self._run_with_progress(cmd, timeout, progress_callback)
            else:
                return self._run_simple(cmd, timeout)
                
        except Exception as e:
            error_msg = f"FFmpeg execution error: {e}"
            self.log(f"❌ {error_msg}", "ERROR")
            return False, error_msg
    
    def run_segmentation(self, cmd: List[str], timeout: Optional[int] = None,
                        progress_callback=None) -> Tuple[bool, str]:
        """
        Execute FFmpeg segmentation command.
        
        Args:
            cmd: FFmpeg segmentation command
            timeout: Optional timeout in seconds
            progress_callback: Optional progress callback function
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        self.log(f"📁 Starting FFmpeg segmentation...", "INFO")
        self.log(f"Command: {' '.join(cmd)}", "DEBUG")
        
        try:
            start_time = time.time()
            
            if progress_callback:
                # Run with progress monitoring
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                # Monitor progress in separate thread
                def progress_monitor():
                    while process.poll() is None:
                        elapsed = time.time() - start_time
                        # Estimate progress (segmentation time varies)
                        estimated_progress = min(0.9, elapsed / (timeout * 0.8)) if timeout else 0.5
                        progress_callback(estimated_progress)
                        time.sleep(1)
                
                progress_thread = threading.Thread(target=progress_monitor, daemon=True)
                progress_thread.start()
                
                # Wait for completion
                stdout, stderr = process.communicate(timeout=timeout)
                
                if process.returncode == 0:
                    progress_callback(1.0)  # Complete
                    return True, "Segmentation completed successfully"
                else:
                    return False, f"Segmentation failed: {stderr}"
            else:
                # Simple execution
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                
                if result.returncode == 0:
                    return True, "Segmentation completed successfully"
                else:
                    return False, f"Segmentation failed: {result.stderr}"
                    
        except subprocess.TimeoutExpired:
            return False, f"Segmentation timed out after {timeout}s"
        except Exception as e:
            return False, f"Segmentation error: {e}"
    
    def _run_simple(self, cmd: List[str], timeout: Optional[int]) -> Tuple[bool, str]:
        """Execute simple FFmpeg command without progress monitoring."""
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        
        if result.returncode == 0:
            return True, "Compression completed successfully"
        else:
            return False, f"FFmpeg failed: {result.stderr}"
    
    def _run_with_progress(self, cmd: List[str], timeout: Optional[int], 
                          progress_callback) -> Tuple[bool, str]:
        """Execute FFmpeg command with progress monitoring."""
        # This would implement FFmpeg progress parsing from stderr
        # For now, return simple implementation
        # TODO: Implement actual progress parsing from FFmpeg output
        return self._run_simple(cmd, timeout)