#!/usr/bin/env python3
"""
Progress Tracker - Thread-Safe Progress Aggregation System

This module provides robust progress tracking for complex multi-worker video processing
workflows. It handles thread-safe progress aggregation, callback throttling, and
comprehensive worker state management.

Key features:
- Thread-safe progress updates using RLock
- Intelligent callback throttling to prevent UI flooding  
- Robust type checking for all progress data
- Worker lifecycle management (starting, processing, completed)
- Throughput and ETA calculations
- Queue and thread pool monitoring integration

The ProgressAggregator is designed to handle various progress data formats including:
- Simple float values (0.0 to 1.0)
- Dictionary objects with progress keys
- Invalid or corrupted progress data (with fallback handling)

This centralized approach ensures consistent progress reporting across all
compression operations while maintaining thread safety and UI responsiveness.
"""

import time
import threading
from typing import Dict, Any, Optional, Callable, List
import traceback


class ProgressAggregator:
    """
    Thread-safe progress aggregator for complex video processing workflows.
    
    This class manages progress tracking across multiple concurrent workers,
    providing real-time aggregated progress data with callback throttling
    and comprehensive error handling.
    
    The aggregator uses weighted progress calculation based on file sizes
    to provide accurate overall progress when workers handle different
    sized files or segments.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize progress aggregator with thread-safe state management.
        
        Args:
            config: Optional configuration dictionary for callback intervals
                   and other behavioral settings
        """
        # Core thread safety - RLock allows re-entrant locking
        self._lock = threading.RLock()
        
        # Worker tracking state
        self._workers: Dict[str, Dict[str, Any]] = {}
        self._start_time = time.time()
        self._total_bytes = 0
        self._processed_bytes = 0
        
        # Callback management with throttling
        self._callback: Optional[Callable] = None
        self._notifying = False  # Prevent recursion in callback notifications
        self._last_callback_time = 0.0
        
        # Enhanced tracking for parallel processing systems
        self._active_thread_count = 0   # Actual active ThreadPoolExecutor workers
        self._total_thread_count = 0    # Total ThreadPoolExecutor workers
        self._queue_size = 0           # Remaining tasks in queue
        self._total_queue_size = 0     # Initial queue size
        self._current_file_index = 0   # Current file being processed
        self._total_files = 0          # Total files to process
        
        # Configure callback throttling interval
        self._callback_interval = self._extract_callback_interval(config)
    
    def _extract_callback_interval(self, config: Optional[Dict[str, Any]]) -> float:
        """Extract callback interval from config with sensible fallbacks."""
        if config and 'large_file_settings' in config:
            return config['large_file_settings'].get('ui_callback_interval_seconds', 0.5)
        return 0.5  # Default 500ms throttling
    
    def register_worker(self, worker_id: str, task_name: str, file_size_bytes: int = 0, 
                       segment_info: Optional[Dict[str, Any]] = None) -> None:
        """
        Register a new worker/task with the aggregator.
        
        Args:
            worker_id: Unique identifier for the worker
            task_name: Human-readable description of the task
            file_size_bytes: Size of file being processed (for weighted progress)
            segment_info: Optional dict with segment details
                         e.g., {'current': 1, 'total': 5, 'duration': 300}
        """
        with self._lock:
            self._workers[worker_id] = {
                'task_name': task_name,
                'file_size_bytes': file_size_bytes,
                'processed_bytes': 0,
                'progress_pct': 0.0,
                'fps': 0.0,
                'status': 'starting',
                'start_time': time.time(),
                'last_update': time.time(),
                'segment_info': segment_info,
                'throughput_mbps': 0.0,
                'eta_seconds': 0.0
            }
            self._total_bytes += file_size_bytes
    
    def update_worker_progress(self, worker_id: str, progress_pct: Any, 
                             fps: float = 0.0, processed_bytes: Optional[float] = None) -> None:
        """
        Update progress for a specific worker with robust type checking.
        
        This method handles various progress data formats and provides comprehensive
        error handling for corrupted or invalid progress data. It ensures thread
        safety and maintains progress data integrity.
        
        Args:
            worker_id: ID of worker to update
            progress_pct: Progress as float (0.0-1.0) or dict with progress keys
            fps: Processing speed in frames per second
            processed_bytes: Optional exact bytes processed
        """
        with self._lock:
            if worker_id not in self._workers:
                return
            
            worker = self._workers[worker_id]
            old_progress = worker['progress_pct']
            
            # Robust progress value extraction with type checking
            progress_value = self._extract_progress_value(progress_pct, old_progress, worker_id)
            
            # Update worker progress data
            worker['progress_pct'] = progress_value
            worker['fps'] = self._sanitize_fps(fps)
            worker['last_update'] = time.time()
            worker['status'] = 'processing' if progress_value < 1.0 else 'completed'
            
            # Update processed bytes calculation
            self._update_processed_bytes(worker, processed_bytes, progress_value)
            
            # Calculate performance metrics (throughput, ETA)
            self._calculate_performance_metrics(worker, progress_value)
            
            # Trigger callback notification (with throttling)
            self.notify_callback()
    
    def _extract_progress_value(self, progress_pct: Any, old_progress: float, worker_id: str) -> float:
        """
        Extract valid progress value from various input formats.
        
        Handles:
        - Dictionary objects with 'overall_progress', 'progress', or 'percent' keys
        - Numeric values (int, float)
        - Invalid or corrupted data (falls back to previous value)
        
        Args:
            progress_pct: Raw progress data in any format
            old_progress: Previous progress value as fallback
            worker_id: Worker ID for error logging
            
        Returns:
            Validated progress value between 0.0 and 1.0
        """
        if isinstance(progress_pct, dict):
            # Extract progress from dictionary with multiple key options
            for key in ['overall_progress', 'progress', 'percent']:
                if key in progress_pct:
                    progress_value = progress_pct[key]
                    break
            else:
                # No recognized progress key found
                self._log_warning(f"Progress data for {worker_id} is dict without progress field: {progress_pct}")
                return old_progress
        elif isinstance(progress_pct, (int, float)) and not isinstance(progress_pct, bool):
            progress_value = progress_pct
        else:
            # Invalid type - log and use fallback
            self._log_warning(f"Invalid progress type for {worker_id}: {type(progress_pct)} = {progress_pct}")
            return old_progress
        
        # Convert to float and clamp to valid range
        try:
            progress_value = float(progress_value) if progress_value is not None else 0.0
            return max(0.0, min(progress_value, 1.0))
        except (ValueError, TypeError):
            self._log_warning(f"Could not convert progress to float for {worker_id}, keeping previous: {old_progress}")
            return old_progress
    
    def _sanitize_fps(self, fps: Any) -> float:
        """Ensure FPS value is a valid non-negative float."""
        try:
            fps_value = float(fps) if isinstance(fps, (int, float)) and not isinstance(fps, bool) else 0.0
            return max(0.0, fps_value)
        except (ValueError, TypeError):
            return 0.0
    
    def _update_processed_bytes(self, worker: Dict[str, Any], processed_bytes: Optional[float], 
                               progress_value: float) -> None:
        """Update processed bytes calculation with validation."""
        if processed_bytes is not None:
            # Validate provided processed_bytes
            try:
                processed_value = float(processed_bytes) if isinstance(processed_bytes, (int, float)) else None
                if processed_value is not None and processed_value >= 0:
                    old_processed = worker['processed_bytes']
                    worker['processed_bytes'] = processed_value
                    self._processed_bytes += (processed_value - old_processed)
                    return
            except (ValueError, TypeError):
                pass  # Fall through to estimation
        
        # Estimate based on progress percentage
        new_processed = worker['file_size_bytes'] * progress_value
        old_processed = worker['processed_bytes']
        worker['processed_bytes'] = new_processed
        self._processed_bytes += (new_processed - old_processed)
    
    def _calculate_performance_metrics(self, worker: Dict[str, Any], progress_value: float) -> None:
        """Calculate throughput and ETA for worker."""
        elapsed = time.time() - worker['start_time']
        
        if elapsed > 0:
            # Calculate throughput in MB/s
            bytes_processed = worker['processed_bytes']
            worker['throughput_mbps'] = (bytes_processed / (1024 * 1024)) / elapsed
            
            # Calculate ETA if meaningful progress made
            if progress_value > 0.01:
                try:
                    total_time_est = elapsed / progress_value
                    calculated_eta = max(0, total_time_est - elapsed)
                    worker['eta_seconds'] = float(calculated_eta) if isinstance(calculated_eta, (int, float)) else 0.0
                except (TypeError, ValueError, ZeroDivisionError):
                    worker['eta_seconds'] = 0.0
    
    def get_aggregate_progress(self) -> Dict[str, Any]:
        """
        Get overall progress across all workers.
        
        Calculates weighted average progress based on file sizes to provide
        accurate overall progress when workers handle different sized files.
        
        Returns:
            Comprehensive progress dictionary with:
            - overall_progress: Weighted average progress (0.0-1.0)
            - active_workers: Number of workers currently processing
            - total_workers: Total number of registered workers
            - throughput_mbps: Combined throughput across all workers
            - eta_seconds: Estimated time to completion
            - workers: List of individual worker details
            - Various additional metrics for UI display
        """
        with self._lock:
            if self._total_bytes == 0:
                return self._get_empty_progress()
            
            # Calculate weighted average progress
            total_weighted_progress = 0.0
            active_workers = 0
            total_throughput = 0.0
            max_eta = 0.0
            worker_details = []
            
            for worker_id, worker in self._workers.items():
                # Calculate weight based on file size
                weight = (worker['file_size_bytes'] / self._total_bytes 
                         if self._total_bytes > 0 
                         else 1.0 / len(self._workers))
                
                total_weighted_progress += worker['progress_pct'] * weight
                
                if worker['status'] == 'processing':
                    active_workers += 1
                
                total_throughput += worker['throughput_mbps']
                
                # Safely handle ETA values with type checking
                worker_eta = self._sanitize_eta(worker, worker_id)
                max_eta = max(max_eta, worker_eta)
                
                # Collect worker details for UI display
                worker_details.append({
                    'id': worker_id,
                    'task_name': worker['task_name'],
                    'progress_pct': worker['progress_pct'],
                    'fps': worker['fps'],
                    'status': worker['status'],
                    'throughput_mbps': worker['throughput_mbps'],
                    'eta_seconds': worker['eta_seconds'],
                    'segment_info': worker['segment_info']
                })
            
            return {
                'overall_progress': total_weighted_progress,
                'active_workers': max(active_workers, self._active_thread_count),
                'total_workers': max(len(self._workers), self._total_thread_count),
                'throughput_mbps': total_throughput,
                'eta_seconds': max_eta,
                'workers': worker_details,
                'total_bytes': self._total_bytes,
                'processed_bytes': self._processed_bytes,
                'queue_size': self._queue_size,
                'total_queue_size': self._total_queue_size,
                'current_file': self._current_file_index,
                'total_files': self._total_files,
                'actual_thread_count': self._active_thread_count
            }
    
    def _get_empty_progress(self) -> Dict[str, Any]:
        """Return empty progress data structure."""
        return {
            'overall_progress': 0.0,
            'active_workers': 0,
            'total_workers': len(self._workers),
            'throughput_mbps': 0.0,
            'eta_seconds': 0,
            'workers': []
        }
    
    def _sanitize_eta(self, worker: Dict[str, Any], worker_id: str) -> float:
        """Sanitize ETA value with type checking and error handling."""
        worker_eta = worker['eta_seconds']
        
        if isinstance(worker_eta, (int, float)) and not isinstance(worker_eta, bool):
            return float(worker_eta)
        else:
            # Fix corrupted ETA data
            self._log_warning(f"Worker {worker_id} has invalid eta_seconds type: {type(worker_eta)} = {worker_eta}")
            worker['eta_seconds'] = 0.0
            return 0.0
    
    def set_callback(self, callback: Callable) -> None:
        """
        Set callback function for progress updates.
        
        Args:
            callback: Function to call with progress data
        """
        with self._lock:
            self._callback = callback
    
    def notify_callback(self) -> None:
        """
        Notify the callback with current progress, respecting throttling interval.
        
        This method implements callback throttling to prevent overwhelming
        the UI with progress updates. It ensures thread safety and provides
        comprehensive error handling for callback failures.
        """
        with self._lock:
            current_time = time.time()
            
            # Check throttling conditions
            if not (self._callback and not self._notifying and 
                   (current_time - self._last_callback_time) >= self._callback_interval):
                return
            
            self._notifying = True
            self._last_callback_time = current_time
            
            try:
                progress_data = self.get_aggregate_progress()
                self._callback(progress_data)
            except Exception as e:
                # Comprehensive error logging with stack trace
                error_msg = f"Progress callback error: {type(e).__name__}: {str(e)}"
                stack_trace = traceback.format_exc()
                self._log_error(f"{error_msg}\\nStack trace:\\n{stack_trace}")
            finally:
                self._notifying = False
    
    def set_thread_pool_info(self, active_count: int, total_count: int) -> None:
        """
        Update thread pool worker count information.
        
        Args:
            active_count: Number of currently active threads
            total_count: Total number of available threads
        """
        with self._lock:
            self._active_thread_count = active_count
            self._total_thread_count = total_count
    
    def set_queue_info(self, current_size: int, total_size: int) -> None:
        """
        Update queue size information.
        
        Args:
            current_size: Current number of tasks in queue
            total_size: Initial total number of tasks
        """
        with self._lock:
            self._queue_size = current_size
            self._total_queue_size = total_size
    
    def set_file_progress_info(self, current_file: int, total_files: int) -> None:
        """
        Update file processing progress information.
        
        Args:
            current_file: Index of currently processing file
            total_files: Total number of files to process
        """
        with self._lock:
            self._current_file_index = current_file
            self._total_files = total_files
    
    def complete_worker(self, worker_id: str) -> None:
        """
        Mark a worker as completed.
        
        Args:
            worker_id: ID of worker to mark as completed
        """
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id]['status'] = 'completed'
                self._workers[worker_id]['progress_pct'] = 1.0
                self.notify_callback()
    
    def fail_worker(self, worker_id: str, error_message: str) -> None:
        """
        Mark a worker as failed with error message.
        
        Args:
            worker_id: ID of worker that failed
            error_message: Description of the failure
        """
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id]['status'] = 'failed'
                self._workers[worker_id]['error_message'] = error_message
                self.notify_callback()
    
    def _log_warning(self, message: str) -> None:
        """Log warning message if logger available."""
        if hasattr(self, 'log'):
            self.log(message, "WARNING")
    
    def _log_error(self, message: str) -> None:
        """Log error message with fallback to console."""
        if hasattr(self, 'log'):
            self.log(message, "ERROR")
        else:
            print(f"ERROR: {message}")


class ProgressCallback:
    """
    Helper class for creating progress callbacks with proper type handling.
    
    This class provides a standard interface for progress callbacks that
    ensures consistent handling of different progress data formats.
    """
    
    def __init__(self, base_progress: float = 0.0, multiplier: float = 1.0, 
                 callback: Optional[Callable] = None):
        """
        Initialize progress callback wrapper.
        
        Args:
            base_progress: Base progress offset (0.0-1.0)
            multiplier: Progress scaling factor
            callback: Optional upstream callback to notify
        """
        self.base_progress = base_progress
        self.multiplier = multiplier
        self.callback = callback
    
    def __call__(self, progress_data: Any) -> None:
        """
        Handle progress update with type safety.
        
        Args:
            progress_data: Progress data in any supported format
        """
        # Extract progress value with type checking
        if isinstance(progress_data, dict):
            progress_value = progress_data.get('overall_progress', 0.0)
        else:
            progress_value = float(progress_data) if progress_data is not None else 0.0
        
        # Calculate adjusted progress
        calculated_progress = self.base_progress + (progress_value * self.multiplier)
        calculated_progress = max(0.0, min(1.0, calculated_progress))
        
        # Notify upstream callback if available
        if self.callback:
            self.callback(calculated_progress)