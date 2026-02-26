"""
Data models for the video compressor library API.

Provides typed dataclasses for video metadata and compression results,
replacing raw dicts for programmatic consumers like the Nook pipeline.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class VideoInfo:
    """Video metadata returned by probe_video() and VideoAnalyzer.get_video_info()."""
    codec: str = "unknown"
    resolution: Tuple[int, int] = (0, 0)
    bitrate: int = 0  # kbps
    duration: float = 0.0  # seconds
    file_size: int = 0  # bytes
    is_progressive: bool = True
    pixel_format: str = "unknown"
    frame_rate: float = 0.0
    audio_codec: str = "unknown"
    audio_channels: int = 0
    audio_sample_rate: int = 0
    container_format: str = "unknown"
    is_10bit: bool = False
    raw_info: dict = field(default_factory=dict)  # Full ffprobe output


@dataclass
class CompressResult:
    """Result of a compression operation returned by CompressionPipeline.compress_file()."""
    output_path: str = ""
    original_size: int = 0  # bytes
    compressed_size: int = 0  # bytes
    compression_ratio: float = 0.0
    duration_seconds: float = 0.0
    codec: str = ""
    resolution: Tuple[int, int] = (0, 0)
    processing_time_seconds: float = 0.0
    segments_used: int = 1
    hardware_accelerated: bool = False
