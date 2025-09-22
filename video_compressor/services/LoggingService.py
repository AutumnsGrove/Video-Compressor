#!/usr/bin/env python3
"""
Logging Service - Enhanced Logging System with Rotation and Filtering

This module provides a comprehensive logging system designed specifically for
video compression workflows. It implements intelligent log rotation, multi-level
filtering, and structured logging to support debugging and performance analysis.

Key features:
- Automatic log rotation based on size and age
- Configurable log levels for console and file output
- Structured logging with consistent formatting
- Performance-aware logging with minimal overhead
- Session-based log organization
- Cleanup mechanisms for disk space management
- Integration with progress tracking and analytics

The logging system is designed to provide detailed debugging information
while maintaining performance and preventing excessive disk usage through
intelligent rotation and cleanup mechanisms.
"""

import os
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
import json
import time
import threading


class PerformanceLogFormatter(logging.Formatter):
    """
    Custom formatter that includes performance metrics and structured data.
    
    This formatter enhances standard log messages with performance timing,
    memory usage information, and structured data for easier analysis.
    """
    
    def __init__(self, include_performance: bool = True):
        """
        Initialize performance formatter.
        
        Args:
            include_performance: Whether to include performance metrics
        """
        super().__init__()
        self.include_performance = include_performance
        self.start_time = time.time()
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with performance information.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted log message
        """
        # Base formatting
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        level_name = f"[{record.levelname:8}]"
        logger_name = record.name
        
        # Performance metrics if enabled
        perf_info = ""
        if self.include_performance and hasattr(record, 'elapsed'):
            elapsed = getattr(record, 'elapsed', 0)
            perf_info = f" ({elapsed:.3f}s)"
        
        # Session time
        session_time = time.time() - self.start_time
        session_info = f"[+{session_time:8.1f}s]"
        
        # Thread information for debugging concurrency issues
        thread_name = threading.current_thread().name
        thread_info = f"[{thread_name}]" if thread_name != "MainThread" else ""
        
        # Construct message
        message = getattr(record, 'getMessage', lambda: str(record.msg))()
        
        return f"{timestamp} {session_info} {level_name} {logger_name}{thread_info}{perf_info}: {message}"


class RotatingLogHandler(logging.handlers.RotatingFileHandler):
    """
    Enhanced rotating file handler with additional cleanup features.
    
    This handler extends the standard RotatingFileHandler with intelligent
    cleanup based on both file count and age, plus compression for old logs.
    """
    
    def __init__(self, filename: str, max_bytes: int, backup_count: int, 
                 max_age_days: int = 30, compress_old_logs: bool = True):
        """
        Initialize enhanced rotating handler.
        
        Args:
            filename: Base filename for logs
            max_bytes: Maximum size per log file
            backup_count: Number of backup files to keep
            max_age_days: Maximum age for log files in days
            compress_old_logs: Whether to compress old log files
        """
        super().__init__(filename, maxBytes=max_bytes, backupCount=backup_count)
        self.max_age_days = max_age_days
        self.compress_old_logs = compress_old_logs
        
    def doRollover(self) -> None:
        """
        Perform log rollover with enhanced cleanup.
        
        This method extends the standard rollover process with age-based
        cleanup and optional compression of old log files.
        """
        # Standard rollover
        super().doRollover()
        
        # Additional cleanup based on age
        self._cleanup_old_logs()
        
        # Compress old logs if requested
        if self.compress_old_logs:
            self._compress_old_logs()
    
    def _cleanup_old_logs(self) -> None:
        """Clean up log files older than max_age_days."""
        try:
            log_dir = Path(self.baseFilename).parent
            cutoff_time = time.time() - (self.max_age_days * 24 * 60 * 60)
            
            # Find old log files
            pattern = Path(self.baseFilename).name + "*"
            old_files = []
            
            for log_file in log_dir.glob(pattern):
                if log_file.stat().st_mtime < cutoff_time:
                    old_files.append(log_file)
            
            # Remove old files
            for old_file in old_files:
                try:
                    old_file.unlink()
                    print(f"🧹 Cleaned up old log file: {old_file.name}")
                except OSError:
                    pass  # File might be in use or already deleted
                    
        except Exception:
            pass  # Don't let cleanup errors affect logging
    
    def _compress_old_logs(self) -> None:
        """Compress old log files to save disk space."""
        try:
            import gzip
            import shutil
            
            log_dir = Path(self.baseFilename).parent
            base_name = Path(self.baseFilename).name
            
            # Find uncompressed backup files
            for i in range(1, self.backupCount + 1):
                backup_file = log_dir / f"{base_name}.{i}"
                compressed_file = log_dir / f"{base_name}.{i}.gz"
                
                if backup_file.exists() and not compressed_file.exists():
                    try:
                        with open(backup_file, 'rb') as f_in:
                            with gzip.open(compressed_file, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        
                        # Remove original after successful compression
                        backup_file.unlink()
                        print(f"🗜️ Compressed log file: {backup_file.name} -> {compressed_file.name}")
                        
                    except Exception:
                        pass  # Continue if compression fails
                        
        except ImportError:
            pass  # gzip not available


class LoggingContext:
    """
    Context manager for adding structured logging context.
    
    This class provides a context manager that adds structured information
    to log records, making it easier to trace operations across the system.
    """
    
    def __init__(self, logger: logging.Logger, context: Dict[str, Any]):
        """
        Initialize logging context.
        
        Args:
            logger: Logger to add context to
            context: Context information to add to log records
        """
        self.logger = logger
        self.context = context
        self.old_factory = None
    
    def __enter__(self):
        """Enter context and install record factory."""
        self.old_factory = logging.getLogRecordFactory()
        
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
            
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and restore record factory."""
        if self.old_factory:
            logging.setLogRecordFactory(self.old_factory)


class VideoCompressionLogger:
    """
    Specialized logger for video compression operations.
    
    This class provides a high-level interface for logging video compression
    activities with built-in context, performance tracking, and structured
    logging capabilities.
    """
    
    def __init__(self, name: str = "VideoCompressor", config: Optional[Dict[str, Any]] = None):
        """
        Initialize video compression logger.
        
        Args:
            name: Logger name
            config: Configuration dictionary with logging settings
        """
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(name)
        self.session_start_time = time.time()
        self._context_stack: List[Dict[str, Any]] = []
        
        # Performance tracking
        self._operation_start_times: Dict[str, float] = {}
        self._setup_logger()
    
    def _setup_logger(self) -> None:
        """Setup logger with handlers and formatters."""
        # Clear existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        self.logger.setLevel(logging.DEBUG)
        
        # Get logging configuration
        logging_config = self.config.get("logging_settings", {})
        console_level = getattr(logging, logging_config.get("console_level", "INFO"))
        file_level = getattr(logging, logging_config.get("file_level", "DEBUG"))
        
        # Setup console handler
        self._setup_console_handler(console_level)
        
        # Setup file handler if log directory specified
        if "log_dir" in self.config:
            self._setup_file_handler(file_level, logging_config)
    
    def _setup_console_handler(self, level: int) -> None:
        """Setup console handler with appropriate formatting."""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        
        # Simple formatter for console
        console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
        console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(console_handler)
    
    def _setup_file_handler(self, level: int, logging_config: Dict[str, Any]) -> None:
        """Setup file handler with rotation and enhanced features."""
        log_dir = Path(self.config["log_dir"])
        log_dir.mkdir(exist_ok=True)
        
        # Clean up old logs first
        max_logs = logging_config.get("max_log_files", 10)
        self._cleanup_old_logs(log_dir, max_logs)
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"video_compression_{timestamp}.log"
        
        # Setup rotating handler
        max_size_mb = logging_config.get("max_log_size_mb", 20)
        max_bytes = max_size_mb * 1024 * 1024
        
        file_handler = RotatingLogHandler(
            str(log_file), 
            max_bytes=max_bytes,
            backup_count=3,
            max_age_days=30,
            compress_old_logs=True
        )
        file_handler.setLevel(level)
        
        # Enhanced formatter for file logs
        file_formatter = PerformanceLogFormatter(include_performance=True)
        file_handler.setFormatter(file_formatter)
        
        self.logger.addHandler(file_handler)
        
        # Log session start
        self.info("=== Video Compression Session Started ===")
        self.info(f"Timestamp: {datetime.now()}")
        self.info(f"Log file: {log_file}")
        self.debug(f"Configuration: {json.dumps(self.config, indent=2)}")
    
    def _cleanup_old_logs(self, log_dir: Path, keep_count: int) -> None:
        """Clean up old log files, keeping only the most recent ones."""
        try:
            # Find all log files
            log_files = sorted(
                [f for f in log_dir.glob("video_compression_*.log*")],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            # Remove excess files
            files_to_remove = log_files[keep_count:]
            for log_file in files_to_remove:
                try:
                    log_file.unlink()
                    print(f"🧹 Cleaned up old log: {log_file.name}")
                except OSError:
                    pass
                    
        except Exception as e:
            print(f"⚠️ Error cleaning up logs: {e}")
    
    def add_context(self, context: Dict[str, Any]) -> LoggingContext:
        """
        Add context to log messages.
        
        Args:
            context: Context information to include in logs
            
        Returns:
            LoggingContext that can be used as context manager
        """
        return LoggingContext(self.logger, context)
    
    def start_operation(self, operation_name: str, **context) -> None:
        """
        Start tracking an operation for performance logging.
        
        Args:
            operation_name: Name of the operation
            **context: Additional context information
        """
        self._operation_start_times[operation_name] = time.time()
        
        context_str = ", ".join(f"{k}={v}" for k, v in context.items()) if context else ""
        self.info(f"🚀 Starting {operation_name}" + (f" ({context_str})" if context_str else ""))
    
    def end_operation(self, operation_name: str, success: bool = True, **context) -> float:
        """
        End operation tracking and log performance.
        
        Args:
            operation_name: Name of the operation
            success: Whether operation was successful
            **context: Additional context information
            
        Returns:
            Elapsed time in seconds
        """
        start_time = self._operation_start_times.pop(operation_name, time.time())
        elapsed = time.time() - start_time
        
        status_icon = "✅" if success else "❌"
        context_str = ", ".join(f"{k}={v}" for k, v in context.items()) if context else ""
        
        # Create log record with elapsed time
        record = self.logger.makeRecord(
            self.logger.name, logging.INFO, __file__, 0,
            f"{status_icon} Completed {operation_name} in {elapsed:.3f}s" + 
            (f" ({context_str})" if context_str else ""), (), None
        )
        record.elapsed = elapsed
        self.logger.handle(record)
        
        return elapsed
    
    def debug(self, message: str, **context) -> None:
        """Log debug message with optional context."""
        self._log_with_context(logging.DEBUG, message, context)
    
    def info(self, message: str, **context) -> None:
        """Log info message with optional context."""
        self._log_with_context(logging.INFO, message, context)
    
    def warning(self, message: str, **context) -> None:
        """Log warning message with optional context."""
        self._log_with_context(logging.WARNING, message, context)
    
    def error(self, message: str, **context) -> None:
        """Log error message with optional context."""
        self._log_with_context(logging.ERROR, message, context)
    
    def _log_with_context(self, level: int, message: str, context: Dict[str, Any]) -> None:
        """Log message with context information."""
        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            message = f"{message} ({context_str})"
        
        self.logger.log(level, message)
    
    def log_compression_start(self, file_path: str, file_size: int, codec: str) -> None:
        """Log compression operation start with structured data."""
        size_mb = file_size / (1024 * 1024)
        self.info(f"🎬 Starting compression: {Path(file_path).name} ({size_mb:.1f}MB, {codec})")
    
    def log_compression_complete(self, file_path: str, original_size: int, 
                               compressed_size: int, processing_time: float) -> None:
        """Log compression completion with metrics."""
        reduction = ((original_size - compressed_size) / original_size) * 100
        throughput = (original_size / (1024 * 1024)) / max(processing_time, 0.001)
        
        self.info(
            f"✅ Compression complete: {Path(file_path).name} | "
            f"Reduction: {reduction:.1f}% | "
            f"Throughput: {throughput:.1f} MB/s"
        )
    
    def log_error_with_suggestion(self, error_message: str, suggestion: str) -> None:
        """Log error with helpful suggestion."""
        self.error(f"{error_message}")
        self.info(f"💡 Suggestion: {suggestion}")


# Module-level convenience functions
_default_logger: Optional[VideoCompressionLogger] = None


def setup_enhanced_logging(config: Dict[str, Any]) -> VideoCompressionLogger:
    """
    Setup enhanced logging system with given configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configured VideoCompressionLogger instance
    """
    global _default_logger
    _default_logger = VideoCompressionLogger("VideoCompressor", config)
    return _default_logger


def get_logger() -> VideoCompressionLogger:
    """
    Get the default video compression logger.
    
    Returns:
        Default logger instance
        
    Raises:
        RuntimeError: If setup_enhanced_logging hasn't been called
    """
    if _default_logger is None:
        raise RuntimeError("Enhanced logging not setup. Call setup_enhanced_logging() first.")
    return _default_logger


def log_with_performance(operation_name: str):
    """
    Decorator for automatic performance logging.
    
    Args:
        operation_name: Name of the operation for logging
        
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger()
            logger.start_operation(operation_name)
            try:
                result = func(*args, **kwargs)
                logger.end_operation(operation_name, success=True)
                return result
            except Exception as e:
                logger.end_operation(operation_name, success=False)
                logger.error(f"Operation {operation_name} failed: {e}")
                raise
        return wrapper
    return decorator