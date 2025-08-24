"""
Core video compression components.

This module contains the fundamental classes for video compression:
- CompressorEngine: Base video compression functionality
- FFmpegRunner: FFmpeg command execution and management
- SegmentationEngine: Video segmentation for large files
- CompressionPipeline: High-level orchestration and workflow management

These components handle the core video processing logic while maintaining
clear separation from UI, concurrency, and service concerns.
"""

from .CompressorEngine import VideoCompressor as CompressorEngine
from .CompressionPipeline import ParallelVideoProcessor as CompressionPipeline

__all__ = [
    "CompressorEngine",
    "CompressionPipeline"
]