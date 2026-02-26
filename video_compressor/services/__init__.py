"""
Services and utilities for video compression.

This module provides supporting services that complement the core compression:
- AnalyticsTracker: Compression metrics and performance analysis
- LoggingService: Enhanced logging with rotation and filtering
- ConfigLoader: Configuration management with validation
- FileIntegrityService: Hash verification and file safety protocols

These services maintain separation of concerns while providing essential
functionality for monitoring, debugging, and ensuring data integrity.
"""

from .ConfigLoader import load_config
from .LoggingService import setup_enhanced_logging
from .AnalyticsTracker import CompressionAnalytics

# Re-export module-level names for package __init__.py
ConfigLoader = load_config  # Callable alias
LoggingService = setup_enhanced_logging  # Callable alias

__all__ = [
    "load_config",
    "setup_enhanced_logging",
    "CompressionAnalytics",
    "ConfigLoader",
    "LoggingService",
]