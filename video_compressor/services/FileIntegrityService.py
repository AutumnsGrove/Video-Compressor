#!/usr/bin/env python3
"""
File Integrity Service - Comprehensive File Safety and Verification

This module provides robust file integrity verification, hash calculation,
and safety protocols for video compression operations. It implements multiple
verification strategies to ensure data integrity throughout the compression
process.

Key features:
- Multi-algorithm hash verification (SHA-256, MD5, CRC32)
- Chunked hash calculation for large files with progress tracking
- File corruption detection and reporting
- Backup hash storage and verification
- Disk space monitoring and safety checks
- Temporary file cleanup and management
- File locking mechanisms for concurrent operations
- Recovery suggestions for corrupted files

The integrity service is designed to prevent data loss through comprehensive
verification while maintaining performance for large video files through
optimized chunked processing and intelligent caching.
"""

import os
import hashlib
import time
import shutil
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Callable, List
from dataclasses import dataclass
from enum import Enum
import json
import tempfile
import psutil


class HashAlgorithm(Enum):
    """Supported hash algorithms for file verification."""
    SHA256 = "sha256"
    MD5 = "md5" 
    CRC32 = "crc32"
    BLAKE2B = "blake2b"


@dataclass
class FileIntegrityResult:
    """Result of file integrity verification."""
    file_path: str
    is_valid: bool
    hash_value: str
    algorithm: HashAlgorithm
    file_size: int
    calculation_time: float
    error_message: Optional[str] = None
    suggestions: List[str] = None


@dataclass
class DiskSpaceInfo:
    """Disk space information for safety checks."""
    total_bytes: int
    used_bytes: int
    free_bytes: int
    free_gb: float
    usage_percent: float
    is_safe: bool
    warning_message: Optional[str] = None


class FileHashCalculator:
    """
    Optimized hash calculation for large video files.
    
    This class provides efficient hash calculation with progress tracking
    and chunked processing to handle large files without excessive memory usage.
    """
    
    def __init__(self, chunk_size_mb: int = 5, logger=None):
        """
        Initialize hash calculator.
        
        Args:
            chunk_size_mb: Chunk size for reading large files (MB)
            logger: Optional logger for progress reporting
        """
        self.chunk_size = chunk_size_mb * 1024 * 1024
        self.log = logger if logger else lambda msg, level="INFO": print(f"[{level}] {msg}")
    
    def calculate_hash(self, file_path: str, algorithm: HashAlgorithm = HashAlgorithm.SHA256,
                      progress_callback: Optional[Callable[[float], None]] = None) -> FileIntegrityResult:
        """
        Calculate file hash with progress tracking.
        
        Args:
            file_path: Path to file for hash calculation
            algorithm: Hash algorithm to use
            progress_callback: Optional progress callback (0.0 to 1.0)
            
        Returns:
            FileIntegrityResult with hash and metadata
        """
        start_time = time.time()
        
        try:
            # Validate file exists and get size
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return FileIntegrityResult(
                    file_path=file_path,
                    is_valid=False,
                    hash_value="",
                    algorithm=algorithm,
                    file_size=0,
                    calculation_time=0,
                    error_message="File does not exist",
                    suggestions=["Verify file path is correct", "Check file permissions"]
                )
            
            file_size = file_path_obj.stat().st_size
            
            # Initialize hasher
            hasher = self._create_hasher(algorithm)
            if not hasher:
                return FileIntegrityResult(
                    file_path=file_path,
                    is_valid=False,
                    hash_value="",
                    algorithm=algorithm,
                    file_size=file_size,
                    calculation_time=0,
                    error_message=f"Unsupported hash algorithm: {algorithm.value}",
                    suggestions=["Use SHA256, MD5, CRC32, or BLAKE2B"]
                )
            
            # Calculate hash with progress tracking
            bytes_processed = 0
            
            self.log(f"🔐 Calculating {algorithm.value.upper()} hash for: {file_path_obj.name}", "DEBUG")
            
            with open(file_path, 'rb') as f:
                while chunk := f.read(self.chunk_size):
                    hasher.update(chunk)
                    bytes_processed += len(chunk)
                    
                    # Report progress
                    if progress_callback and file_size > 0:
                        progress = bytes_processed / file_size
                        progress_callback(progress)
            
            # Get final hash
            if algorithm == HashAlgorithm.CRC32:
                hash_value = f"{hasher & 0xffffffff:08x}"  # CRC32 special handling
            else:
                hash_value = hasher.hexdigest()
            
            calculation_time = time.time() - start_time
            
            self.log(
                f"✅ Hash calculated: {algorithm.value.upper()} = {hash_value[:16]}... "
                f"({calculation_time:.2f}s, {file_size / (1024*1024) / calculation_time:.1f} MB/s)",
                "DEBUG"
            )
            
            return FileIntegrityResult(
                file_path=file_path,
                is_valid=True,
                hash_value=hash_value,
                algorithm=algorithm,
                file_size=file_size,
                calculation_time=calculation_time
            )
            
        except PermissionError:
            return FileIntegrityResult(
                file_path=file_path,
                is_valid=False,
                hash_value="",
                algorithm=algorithm,
                file_size=0,
                calculation_time=time.time() - start_time,
                error_message="Permission denied accessing file",
                suggestions=["Check file permissions", "Run with appropriate privileges"]
            )
        except Exception as e:
            return FileIntegrityResult(
                file_path=file_path,
                is_valid=False,
                hash_value="",
                algorithm=algorithm,
                file_size=file_size if 'file_size' in locals() else 0,
                calculation_time=time.time() - start_time,
                error_message=f"Hash calculation error: {e}",
                suggestions=["Check file is not corrupted", "Verify sufficient disk space"]
            )
    
    def _create_hasher(self, algorithm: HashAlgorithm):
        """Create hasher instance for specified algorithm."""
        if algorithm == HashAlgorithm.SHA256:
            return hashlib.sha256()
        elif algorithm == HashAlgorithm.MD5:
            return hashlib.md5()
        elif algorithm == HashAlgorithm.CRC32:
            import zlib
            return zlib.crc32(b'', 0)  # Initialize CRC32
        elif algorithm == HashAlgorithm.BLAKE2B:
            return hashlib.blake2b()
        return None
    
    def verify_hash(self, file_path: str, expected_hash: str, 
                   algorithm: HashAlgorithm = HashAlgorithm.SHA256,
                   progress_callback: Optional[Callable[[float], None]] = None) -> FileIntegrityResult:
        """
        Verify file hash against expected value.
        
        Args:
            file_path: Path to file for verification
            expected_hash: Expected hash value
            algorithm: Hash algorithm to use
            progress_callback: Optional progress callback
            
        Returns:
            FileIntegrityResult with verification status
        """
        result = self.calculate_hash(file_path, algorithm, progress_callback)
        
        if result.is_valid:
            # Compare hashes (case insensitive)
            result.is_valid = result.hash_value.lower() == expected_hash.lower()
            
            if not result.is_valid:
                result.error_message = "Hash verification failed - file may be corrupted"
                result.suggestions = [
                    "Re-download or restore file from backup",
                    "Check storage device for errors",
                    "Verify source file integrity"
                ]
        
        return result


class DiskSpaceMonitor:
    """
    Disk space monitoring for safe compression operations.
    
    This class monitors available disk space and provides safety checks
    to prevent operations from failing due to insufficient space.
    """
    
    def __init__(self, logger=None):
        """
        Initialize disk space monitor.
        
        Args:
            logger: Optional logger for reporting
        """
        self.log = logger if logger else lambda msg, level="INFO": print(f"[{level}] {msg}")
    
    def check_disk_space(self, file_path: str, safety_multiplier: float = 2.5) -> DiskSpaceInfo:
        """
        Check available disk space for compression operation.
        
        Args:
            file_path: Path to file being processed
            safety_multiplier: Safety factor for space calculation
            
        Returns:
            DiskSpaceInfo with space analysis and safety status
        """
        try:
            # Get file size and disk usage
            file_size = os.path.getsize(file_path)
            disk_usage = shutil.disk_usage(os.path.dirname(file_path))
            
            total_bytes = disk_usage.total
            free_bytes = disk_usage.free
            used_bytes = total_bytes - free_bytes
            free_gb = free_bytes / (1024**3)
            usage_percent = (used_bytes / total_bytes) * 100
            
            # Calculate required space (original + compressed + temp files)
            required_space = file_size * safety_multiplier
            is_safe = free_bytes >= required_space
            
            # Generate warning message if needed
            warning_message = None
            if not is_safe:
                required_gb = required_space / (1024**3)
                warning_message = (
                    f"Insufficient disk space: {free_gb:.1f}GB available, "
                    f"{required_gb:.1f}GB required for safe operation"
                )
            elif free_gb < 10:  # General low space warning
                warning_message = f"Low disk space: {free_gb:.1f}GB remaining"
            
            self.log(
                f"💾 Disk space check: {free_gb:.1f}GB free ({usage_percent:.1f}% used), "
                f"Status: {'✅ Safe' if is_safe else '⚠️ Insufficient'}",
                "DEBUG"
            )
            
            return DiskSpaceInfo(
                total_bytes=total_bytes,
                used_bytes=used_bytes,
                free_bytes=free_bytes,
                free_gb=free_gb,
                usage_percent=usage_percent,
                is_safe=is_safe,
                warning_message=warning_message
            )
            
        except Exception as e:
            return DiskSpaceInfo(
                total_bytes=0,
                used_bytes=0,
                free_bytes=0,
                free_gb=0,
                usage_percent=100,
                is_safe=False,
                warning_message=f"Error checking disk space: {e}"
            )


class BackupHashManager:
    """
    Manager for backup hash files and verification data.
    
    This class handles creation, storage, and verification of backup hashes
    that can be used to verify file integrity after compression operations.
    """
    
    def __init__(self, backup_dir: Optional[str] = None, logger=None):
        """
        Initialize backup hash manager.
        
        Args:
            backup_dir: Directory for storing backup hashes
            logger: Optional logger for reporting
        """
        self.backup_dir = Path(backup_dir) if backup_dir else Path.cwd() / ".integrity_backups"
        self.backup_dir.mkdir(exist_ok=True, parents=True)
        self.log = logger if logger else lambda msg, level="INFO": print(f"[{level}] {msg}")
    
    def create_backup_hash(self, file_path: str, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> Optional[str]:
        """
        Create and store backup hash for file.
        
        Args:
            file_path: Path to file for backup hash creation
            algorithm: Hash algorithm to use
            
        Returns:
            Path to backup hash file, or None if creation failed
        """
        try:
            # Calculate hash
            calculator = FileHashCalculator(logger=self.log)
            result = calculator.calculate_hash(file_path, algorithm)
            
            if not result.is_valid:
                self.log(f"❌ Failed to create backup hash: {result.error_message}", "ERROR")
                return None
            
            # Create backup hash metadata
            file_path_obj = Path(file_path)
            backup_data = {
                "file_path": str(file_path_obj.absolute()),
                "file_name": file_path_obj.name,
                "file_size": result.file_size,
                "hash_algorithm": algorithm.value,
                "hash_value": result.hash_value,
                "creation_time": time.time(),
                "creation_date": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Save backup hash file
            backup_filename = f"{file_path_obj.stem}_{algorithm.value}.hash"
            backup_path = self.backup_dir / backup_filename
            
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            self.log(f"💾 Backup hash created: {backup_filename}", "DEBUG")
            return str(backup_path)
            
        except Exception as e:
            self.log(f"❌ Error creating backup hash: {e}", "ERROR")
            return None
    
    def verify_with_backup_hash(self, file_path: str) -> Optional[FileIntegrityResult]:
        """
        Verify file against stored backup hash.
        
        Args:
            file_path: Path to file for verification
            
        Returns:
            FileIntegrityResult or None if no backup hash found
        """
        try:
            file_path_obj = Path(file_path)
            
            # Look for backup hash files
            for algorithm in HashAlgorithm:
                backup_filename = f"{file_path_obj.stem}_{algorithm.value}.hash"
                backup_path = self.backup_dir / backup_filename
                
                if backup_path.exists():
                    return self._verify_against_backup_file(file_path, backup_path, algorithm)
            
            self.log(f"⚠️ No backup hash found for: {file_path_obj.name}", "WARNING")
            return None
            
        except Exception as e:
            self.log(f"❌ Error verifying backup hash: {e}", "ERROR")
            return None
    
    def _verify_against_backup_file(self, file_path: str, backup_path: Path, 
                                   algorithm: HashAlgorithm) -> FileIntegrityResult:
        """Verify file against specific backup hash file."""
        try:
            # Load backup data
            with open(backup_path, 'r') as f:
                backup_data = json.load(f)
            
            expected_hash = backup_data["hash_value"]
            
            # Verify hash
            calculator = FileHashCalculator(logger=self.log)
            result = calculator.verify_hash(file_path, expected_hash, algorithm)
            
            if result.is_valid:
                self.log(f"✅ Backup hash verification passed: {Path(file_path).name}", "DEBUG")
            else:
                self.log(f"❌ Backup hash verification failed: {Path(file_path).name}", "ERROR")
            
            return result
            
        except Exception as e:
            return FileIntegrityResult(
                file_path=file_path,
                is_valid=False,
                hash_value="",
                algorithm=algorithm,
                file_size=0,
                calculation_time=0,
                error_message=f"Error reading backup hash: {e}",
                suggestions=["Recreate backup hash", "Check backup file integrity"]
            )


class FileIntegrityService:
    """
    Comprehensive file integrity service for video compression operations.
    
    This service provides a unified interface for all file integrity operations
    including hash calculation, verification, backup management, and disk space
    monitoring. It integrates all integrity-related functionality into a single
    service with consistent error handling and reporting.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, logger=None):
        """
        Initialize file integrity service.
        
        Args:
            config: Configuration dictionary with integrity settings
            logger: Optional logger for reporting
        """
        self.config = config or {}
        self.log = logger if logger else lambda msg, level="INFO": print(f"[{level}] {msg}")
        
        # Initialize components
        chunk_size_mb = self.config.get("large_file_settings", {}).get("hash_chunk_size_mb", 5)
        self.hash_calculator = FileHashCalculator(chunk_size_mb, self.log)
        self.disk_monitor = DiskSpaceMonitor(self.log)
        
        # Setup backup hash manager if enabled
        if self.config.get("safety_settings", {}).get("create_backup_hash", True):
            backup_dir = self.config.get("backup_hash_dir")
            self.backup_manager = BackupHashManager(backup_dir, self.log)
        else:
            self.backup_manager = None
        
        # Thread lock for concurrent operations
        self._lock = threading.Lock()
    
    def verify_file_integrity(self, file_path: str, original_info: Optional[Dict[str, Any]] = None,
                            progress_callback: Optional[Callable[[float], None]] = None) -> Tuple[bool, str]:
        """
        Comprehensive file integrity verification.
        
        This method performs complete integrity verification including:
        - File existence and accessibility
        - Hash verification against backup (if available)
        - Basic file format validation
        - Size and metadata consistency checks
        
        Args:
            file_path: Path to file for verification
            original_info: Optional original file metadata for comparison
            progress_callback: Optional progress callback for UI updates
            
        Returns:
            Tuple of (is_valid: bool, message: str)
        """
        with self._lock:
            self.log(f"🔍 Starting comprehensive integrity verification: {Path(file_path).name}", "INFO")
            
            try:
                # Basic file checks
                if not self._basic_file_checks(file_path):
                    return False, "Basic file validation failed"
                
                # Hash verification if backup available
                if self.backup_manager:
                    hash_result = self.backup_manager.verify_with_backup_hash(file_path)
                    if hash_result and not hash_result.is_valid:
                        return False, f"Hash verification failed: {hash_result.error_message}"
                    elif hash_result and hash_result.is_valid:
                        self.log("✅ Hash verification passed", "DEBUG")
                
                # Size comparison if original info available
                if original_info and not self._validate_size_consistency(file_path, original_info):
                    return False, "File size inconsistency detected"
                
                # Format validation (basic)
                if not self._basic_format_validation(file_path):
                    return False, "File format validation failed"
                
                self.log(f"✅ Integrity verification passed: {Path(file_path).name}", "INFO")
                return True, "File integrity verification successful"
                
            except Exception as e:
                error_msg = f"Integrity verification error: {e}"
                self.log(f"❌ {error_msg}", "ERROR")
                return False, error_msg
    
    def _basic_file_checks(self, file_path: str) -> bool:
        """Perform basic file existence and accessibility checks."""
        file_path_obj = Path(file_path)
        
        # Existence check
        if not file_path_obj.exists():
            self.log(f"❌ File does not exist: {file_path}", "ERROR")
            return False
        
        # Size check
        file_size = file_path_obj.stat().st_size
        if file_size < 1024:  # Less than 1KB is suspicious for video files
            self.log(f"⚠️ File suspiciously small: {file_size} bytes", "WARNING")
            return False
        
        # Read access check
        try:
            with open(file_path, 'rb') as f:
                f.read(1)  # Try to read first byte
        except PermissionError:
            self.log(f"❌ Cannot read file: permission denied", "ERROR")
            return False
        except Exception as e:
            self.log(f"❌ File read error: {e}", "ERROR")
            return False
        
        return True
    
    def _validate_size_consistency(self, file_path: str, original_info: Dict[str, Any]) -> bool:
        """Validate file size consistency with original metadata."""
        try:
            current_size = os.path.getsize(file_path)
            
            # Get original size from metadata
            original_size = original_info.get("format", {}).get("size")
            if not original_size:
                return True  # Can't validate without original size
            
            original_size = int(original_size)
            size_difference_percent = abs(current_size - original_size) / original_size * 100
            
            # Check against configured threshold
            threshold = self.config.get("segmentation_settings", {}).get("size_difference_warning_percent", 5)
            
            if size_difference_percent > threshold:
                self.log(
                    f"⚠️ Size difference: {size_difference_percent:.1f}% "
                    f"(current: {current_size}, original: {original_size})",
                    "WARNING"
                )
                return False
            
            return True
            
        except Exception as e:
            self.log(f"⚠️ Size validation error: {e}", "WARNING")
            return True  # Don't fail verification on size check error
    
    def _basic_format_validation(self, file_path: str) -> bool:
        """Perform basic file format validation."""
        try:
            # Check file has appropriate extension
            file_ext = Path(file_path).suffix.lower()
            video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.webm', '.flv', '.wmv'}
            
            if file_ext not in video_extensions:
                self.log(f"⚠️ Unexpected file extension: {file_ext}", "WARNING")
                return False
            
            # Basic header validation (first few bytes)
            with open(file_path, 'rb') as f:
                header = f.read(16)
                
            if len(header) < 4:
                self.log("❌ File too short to contain valid header", "ERROR")
                return False
            
            # Check for common video file signatures
            if file_ext == '.mp4':
                # MP4 files should have 'ftyp' box near beginning
                if b'ftyp' not in header:
                    # Read a bit more to check
                    with open(file_path, 'rb') as f:
                        larger_header = f.read(64)
                    if b'ftyp' not in larger_header:
                        self.log("⚠️ MP4 file missing expected signature", "WARNING")
                        return False
            
            return True
            
        except Exception as e:
            self.log(f"⚠️ Format validation error: {e}", "WARNING")
            return True  # Don't fail verification on format check error
    
    def create_file_backup_hash(self, file_path: str) -> Optional[str]:
        """
        Create backup hash for file if backup hashes are enabled.
        
        Args:
            file_path: Path to file for backup hash creation
            
        Returns:
            Path to backup hash file, or None if disabled or failed
        """
        if not self.backup_manager:
            return None
        
        return self.backup_manager.create_backup_hash(file_path)
    
    def check_available_space(self, file_path: str) -> DiskSpaceInfo:
        """
        Check available disk space for safe operation.
        
        Args:
            file_path: Path to file being processed
            
        Returns:
            DiskSpaceInfo with space analysis
        """
        safety_multiplier = self.config.get("safety_settings", {}).get("space_safety_multiplier", 2.5)
        return self.disk_monitor.check_disk_space(file_path, safety_multiplier)
    
    def cleanup_temp_files(self, temp_dirs: List[str]) -> None:
        """
        Clean up temporary files and directories.
        
        Args:
            temp_dirs: List of temporary directories to clean up
        """
        for temp_dir in temp_dirs:
            try:
                temp_path = Path(temp_dir)
                if temp_path.exists() and temp_path.is_dir():
                    shutil.rmtree(temp_path)
                    self.log(f"🧹 Cleaned up temp directory: {temp_path.name}", "DEBUG")
            except Exception as e:
                self.log(f"⚠️ Failed to cleanup temp directory {temp_dir}: {e}", "WARNING")
    
    def calculate_file_hash(self, file_path: str, algorithm: HashAlgorithm = HashAlgorithm.SHA256,
                          progress_callback: Optional[Callable[[float], None]] = None) -> FileIntegrityResult:
        """
        Calculate hash for file with progress tracking.
        
        Args:
            file_path: Path to file for hash calculation
            algorithm: Hash algorithm to use
            progress_callback: Optional progress callback
            
        Returns:
            FileIntegrityResult with hash and metadata
        """
        return self.hash_calculator.calculate_hash(file_path, algorithm, progress_callback)