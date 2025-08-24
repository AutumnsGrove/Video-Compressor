"""
User interface components for video compression.

This module contains the Gradio web interface and related UI components:
- GradioInterface: Main web interface for video compression
- ProgressDisplay: Progress visualization and callback handling

The UI components provide an intuitive interface while maintaining clean
separation from core compression logic and system services.
"""

from .GradioInterface import GradioVideoInterface as GradioInterface

__all__ = [
    "GradioInterface"
]