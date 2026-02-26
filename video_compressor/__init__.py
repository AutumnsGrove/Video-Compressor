"""
Video Compressor Package

A modular, high-performance video compression system with parallel processing,
comprehensive progress tracking, and advanced safety protocols.

Library API usage (for pipelines like Nook):

    from video_compressor import CompressionPipeline, probe_video
    from video_compressor.services import load_config

    # Probe a video without compressing
    info = probe_video("/path/to/video.mp4")

    # Compress a video programmatically
    config = load_config("config.json")
    pipeline = CompressionPipeline(config=config)
    result = pipeline.compress_file("/path/to/video.mp4", output_dir="/output/")
"""

from .core import CompressorEngine, CompressionPipeline
from .services import ConfigLoader, LoggingService, load_config
from .models import VideoInfo, CompressResult
from .exceptions import (
    CompressionError,
    FFmpegError,
    DiskSpaceError,
    VideoAnalysisError,
    IntegrityError,
)

# Lazy import to avoid pulling in Gradio when only using as a library
try:
    from .ui import GradioInterface
except ImportError:
    GradioInterface = None


def probe_video(file_path, ffprobe_path=None):
    """
    Probe a video file and return structured metadata.

    This is a standalone utility that does not require instantiating the
    full compression pipeline. It is designed for fast probing of many
    files (e.g. to decide which need compression).

    Args:
        file_path: Path to the video file.
        ffprobe_path: Optional path to ffprobe executable. If None,
                      auto-detects from PATH or common locations.

    Returns:
        VideoInfo dataclass with codec, resolution, bitrate, duration, etc.

    Raises:
        VideoAnalysisError: If the file cannot be analysed.
    """
    import os
    import shutil
    import platform
    from pathlib import Path as _Path

    file_path = str(file_path)

    if not os.path.exists(file_path):
        raise VideoAnalysisError(f"File does not exist: {file_path}")

    # Auto-detect ffprobe
    if ffprobe_path is None:
        ffprobe_path = shutil.which("ffprobe")
        if ffprobe_path is None:
            # Try common locations
            system = platform.system().lower()
            candidates = {
                'darwin': ['/opt/homebrew/bin/ffprobe', '/usr/local/bin/ffprobe'],
                'linux': ['/usr/bin/ffprobe', '/usr/local/bin/ffprobe'],
            }
            for p in candidates.get(system, []):
                if _Path(p).exists():
                    ffprobe_path = p
                    break
        if ffprobe_path is None:
            ffprobe_path = "ffprobe"

    from .core.FFmpegRunner import VideoAnalyzer

    analyzer = VideoAnalyzer(ffprobe_path=ffprobe_path)
    raw_info = analyzer.get_video_info(file_path)

    if raw_info is None:
        raise VideoAnalysisError(f"Failed to analyse video: {file_path}")

    # Parse raw ffprobe dict into VideoInfo dataclass
    format_info = raw_info.get("format", {})
    streams = raw_info.get("streams", [])
    video_stream = next(
        (s for s in streams if s.get("codec_type") == "video"), None
    )
    audio_stream = next(
        (s for s in streams if s.get("codec_type") == "audio"), None
    )

    # Extract video metadata
    codec = "unknown"
    resolution = (0, 0)
    bitrate = 0
    pixel_format = "unknown"
    frame_rate = 0.0
    is_progressive = True
    is_10bit = False

    if video_stream:
        codec = video_stream.get("codec_name", "unknown")
        width = video_stream.get("width", 0)
        height = video_stream.get("height", 0)
        resolution = (width, height)
        pixel_format = video_stream.get("pix_fmt", "unknown")
        is_10bit = "10" in pixel_format if pixel_format != "unknown" else False

        # Field order: progressive vs interlaced
        field_order = video_stream.get("field_order", "progressive")
        is_progressive = field_order in ("progressive", "unknown", "")

        # Frame rate from r_frame_rate or avg_frame_rate
        r_frame_rate = video_stream.get("r_frame_rate", "0/1")
        try:
            num, den = r_frame_rate.split("/")
            if int(den) > 0:
                frame_rate = round(int(num) / int(den), 3)
        except (ValueError, ZeroDivisionError):
            pass

        # Bitrate: prefer stream bitrate, fallback to format bitrate
        if "bit_rate" in video_stream:
            try:
                bitrate = int(video_stream["bit_rate"]) // 1000  # kbps
            except (ValueError, TypeError):
                pass

    if bitrate == 0 and "bit_rate" in format_info:
        try:
            bitrate = int(format_info["bit_rate"]) // 1000
        except (ValueError, TypeError):
            pass

    # Duration
    duration = 0.0
    if "duration" in format_info:
        try:
            duration = float(format_info["duration"])
        except (ValueError, TypeError):
            pass

    # File size
    file_size = os.path.getsize(file_path)

    # Audio metadata
    audio_codec = "unknown"
    audio_channels = 0
    audio_sample_rate = 0
    if audio_stream:
        audio_codec = audio_stream.get("codec_name", "unknown")
        audio_channels = audio_stream.get("channels", 0)
        try:
            audio_sample_rate = int(audio_stream.get("sample_rate", 0))
        except (ValueError, TypeError):
            pass

    # Container format
    container_format = format_info.get("format_name", "unknown")

    return VideoInfo(
        codec=codec,
        resolution=resolution,
        bitrate=bitrate,
        duration=duration,
        file_size=file_size,
        is_progressive=is_progressive,
        pixel_format=pixel_format,
        frame_rate=frame_rate,
        audio_codec=audio_codec,
        audio_channels=audio_channels,
        audio_sample_rate=audio_sample_rate,
        container_format=container_format,
        is_10bit=is_10bit,
        raw_info=raw_info,
    )


__version__ = "2.0.0"
__author__ = "Video Compressor Development Team"
__all__ = [
    # Core classes
    "CompressorEngine",
    "CompressionPipeline",
    # Standalone utility
    "probe_video",
    # Data models
    "VideoInfo",
    "CompressResult",
    # Exceptions
    "CompressionError",
    "FFmpegError",
    "DiskSpaceError",
    "VideoAnalysisError",
    "IntegrityError",
    # Services
    "ConfigLoader",
    "LoggingService",
    "load_config",
    # UI (optional)
    "GradioInterface",
]
