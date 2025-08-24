"""
Video Compressor Package

A modular, high-performance video compression system with parallel processing,
comprehensive progress tracking, and advanced safety protocols.

This package provides a clean separation of concerns:
- core: Core compression engine and FFmpeg integration
- concurrency: Threading, progress tracking, and parallel processing
- services: Analytics, logging, configuration, and file integrity
- ui: Gradio interface and progress display

Example usage:
    from video_compressor.core import CompressorEngine
    from video_compressor.ui import GradioInterface
    
    compressor = CompressorEngine()
    interface = GradioInterface(compressor)
"""

from .core import CompressorEngine, CompressionPipeline
from .services import ConfigLoader, LoggingService
from .ui import GradioInterface

__version__ = "2.0.0"
__author__ = "Video Compressor Development Team"
__all__ = [
    "CompressorEngine",
    "CompressionPipeline", 
    "ConfigLoader",
    "LoggingService",
    "GradioInterface"
]