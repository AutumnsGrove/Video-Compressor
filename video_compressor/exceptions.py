"""
Typed exceptions for the video compressor library.

These provide structured error handling for programmatic use,
replacing the (success, message) tuple pattern with proper exception types.
"""


class CompressionError(Exception):
    """Base exception for all video compression errors."""
    pass


class FFmpegError(CompressionError):
    """Raised when FFmpeg fails to execute a command."""

    def __init__(self, message: str, returncode: int = None, stderr: str = None):
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(message)


class DiskSpaceError(CompressionError):
    """Raised when there is insufficient disk space for compression."""

    def __init__(self, message: str, required_gb: float = None, available_gb: float = None):
        self.required_gb = required_gb
        self.available_gb = available_gb
        super().__init__(message)


class VideoAnalysisError(CompressionError):
    """Raised when video analysis (ffprobe) fails."""
    pass


class IntegrityError(CompressionError):
    """Raised when compressed file fails integrity verification."""
    pass
