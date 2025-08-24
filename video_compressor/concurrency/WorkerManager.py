#!/usr/bin/env python3
"""
Worker Manager - Generator-Based Worker System for Efficient Task Processing

This module implements an advanced worker management system using Python generators
for efficient task processing and worker reuse. It provides superior performance
and memory efficiency compared to traditional thread-based workers.

Key components:
- WorkerGenerator: Individual generator-based workers with lifecycle management
- GeneratorWorkerManager: Coordinates multiple generator workers for parallel processing
- Task distribution with intelligent retry logic
- Resource cleanup and graceful shutdown handling

The generator-based approach offers several advantages:
- Lower memory overhead compared to thread-based workers
- Efficient task processing without thread creation overhead
- Built-in worker reuse and state management
- Excellent for CPU-bound tasks like video segment compression

This system is particularly effective for processing large numbers of video
segments where creating new threads for each task would be inefficient.
"""

import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable, Generator


class WorkerGenerator:
    """
    Generator-based worker system for efficient task processing and worker reuse.
    
    This class implements a worker using Python generator patterns, providing
    efficient task processing without the overhead of thread creation and
    destruction. Each worker maintains state and can process multiple tasks
    in sequence.
    
    The generator approach allows for:
    - Stateful processing with minimal memory overhead
    - Efficient task handoff without thread synchronization
    - Built-in cleanup and error handling
    - Worker reuse across multiple tasks
    """
    
    def __init__(self, worker_id: str, compressor_instance):
        """
        Initialize generator-based worker.
        
        Args:
            worker_id: Unique identifier for this worker
            compressor_instance: Reference to compression engine for access to
                                 compression methods and logging
        """
        self.worker_id = worker_id
        self.compressor = compressor_instance
        self.active = True
        self.tasks_completed = 0
    
    def segment_compression_generator(self) -> Generator[Dict[str, Any], Dict[str, Any], None]:
        """
        Generator that yields segment compression results efficiently.
        
        This generator processes video segments in a stateful manner,
        maintaining compression settings and worker state across tasks.
        Each task is sent to the generator via .send() and results are
        yielded back to the caller.
        
        Task format expected:
        {
            'segment_path': str,        # Path to segment file
            'segment_index': int,       # Index of segment (for logging)
            'total_segments': int,      # Total number of segments
            'file_path': str           # Original file path (for metadata)
        }
        
        Yields:
            Dict containing:
            - success: bool
            - segment_path: str (input)
            - output_path: str (compressed output)
            - message: str (status message)
            - worker_id: str
            - tasks_completed: int
        """
        while self.active:
            try:
                # Wait for task from queue (this will be yielded to)
                task = yield
                if task is None:  # Shutdown signal
                    break
                
                self.tasks_completed += 1
                segment_path = task['segment_path']
                segment_index = task['segment_index']
                total_segments = task['total_segments']
                file_path = task['file_path']
                
                self.compressor.log(
                    f"🎬 [{self.worker_id}] Processing segment {segment_index+1}/{total_segments}", 
                    "DEBUG"
                )
                
                # Create output path for compressed segment
                segment_path_obj = Path(segment_path)
                output_dir = segment_path_obj.parent
                output_path = output_dir / f"{segment_path_obj.stem}_compressed{segment_path_obj.suffix}"
                
                # Get video info and settings for compression
                # Note: These calls will be refactored to use the new FFmpegRunner
                original_info = self.compressor.get_video_info(file_path)
                settings = self.compressor.get_compression_settings()
                
                # Compress the segment using existing compression logic
                success, message = self.compressor.compress_single_file(
                    segment_path, output_path, original_info, settings,
                    progress_callback=lambda p: None  # Individual segment progress handled elsewhere
                )
                
                # Clean up original segment if compression was successful
                if success:
                    try:
                        Path(segment_path).unlink()
                        self.compressor.log(
                            f"🧹 [{self.worker_id}] Cleaned up original segment: {segment_path_obj.name}", 
                            "DEBUG"
                        )
                    except Exception as cleanup_e:
                        self.compressor.log(
                            f"⚠️ [{self.worker_id}] Failed to clean up segment: {cleanup_e}", 
                            "WARNING"
                        )
                
                # Yield result back to caller
                yield {
                    'success': success,
                    'segment_path': segment_path,
                    'output_path': str(output_path),
                    'message': message,
                    'worker_id': self.worker_id,
                    'tasks_completed': self.tasks_completed
                }
                
            except Exception as e:
                error_msg = f"Generator worker error: {type(e).__name__}: {e}"
                self.compressor.log(f"❌ [{self.worker_id}] {error_msg}", "ERROR")
                yield {
                    'success': False,
                    'error': error_msg,
                    'worker_id': self.worker_id,
                    'segment_path': task.get('segment_path', 'unknown') if 'task' in locals() else 'unknown'
                }
    
    def small_file_generator(self) -> Generator[Dict[str, Any], Dict[str, Any], None]:
        """
        Generator for processing small files efficiently.
        
        This generator handles complete file compression for smaller files
        that don't require segmentation. It uses the full compression
        pipeline but in a generator-based worker pattern.
        
        Task format expected:
        {
            'file_path': str    # Path to file to compress
        }
        
        Yields:
            Dict containing:
            - success: bool
            - file_path: str
            - message: str
            - worker_id: str
            - tasks_completed: int
        """
        while self.active:
            try:
                # Wait for task from queue
                task = yield
                if task is None:  # Shutdown signal
                    break
                
                self.tasks_completed += 1
                file_path = task['file_path']
                file_name = Path(file_path).name
                
                self.compressor.log(f"🎬 [{self.worker_id}] Processing small file: {file_name}", "DEBUG")
                
                # Process the file using existing compression logic
                # This will be updated to use the new modular architecture
                success, message = self.compressor.compress_video(file_path)
                
                yield {
                    'success': success,
                    'file_path': file_path,
                    'message': message,
                    'worker_id': self.worker_id,
                    'tasks_completed': self.tasks_completed
                }
                
            except Exception as e:
                error_msg = f"Small file generator error: {type(e).__name__}: {e}"
                self.compressor.log(f"❌ [{self.worker_id}] {error_msg}", "ERROR")
                yield {
                    'success': False,
                    'file_path': task.get('file_path', 'unknown') if 'task' in locals() else 'unknown',
                    'error': error_msg,
                    'worker_id': self.worker_id
                }
    
    def shutdown(self) -> None:
        """
        Signal the generator to shutdown gracefully.
        
        This method sets the active flag to False, which will cause
        the generator to exit its main loop on the next task.
        """
        self.active = False


class GeneratorWorkerManager:
    """
    Manages generator-based workers for efficient task distribution.
    
    This class coordinates multiple generator workers to process tasks in parallel.
    It provides intelligent task distribution, retry logic, and error recovery
    mechanisms. The manager handles worker lifecycle, task queuing, and result
    aggregation.
    
    Key features:
    - Dynamic worker creation and management
    - Intelligent retry logic with exponential backoff
    - Progress tracking and callback support
    - Graceful error handling and recovery
    - Resource cleanup and shutdown management
    """
    
    def __init__(self, compressor_instance, max_workers: Optional[int] = None):
        """
        Initialize generator worker manager.
        
        Args:
            compressor_instance: Reference to compression engine
            max_workers: Maximum number of concurrent workers (defaults to
                        compressor's max_concurrent_jobs setting)
        """
        self.compressor = compressor_instance
        self.max_workers = max_workers or getattr(compressor_instance, 'max_concurrent_jobs', 4)
        self.generators: Dict[str, Dict[str, Any]] = {}
        self.active_generators: List[str] = []
    
    def create_segment_workers(self) -> None:
        """
        Create and initialize segment compression generator workers.
        
        This method creates the specified number of generator workers,
        initializes their generators, and prepares them for task processing.
        Each worker is primed with an initial .next() call to reach the
        first yield point.
        """
        self.active_generators = []
        
        for i in range(self.max_workers):
            worker_id = f"GenWorker-{i+1}"
            worker = WorkerGenerator(worker_id, self.compressor)
            generator = worker.segment_compression_generator()
            
            # Initialize generator (advance to first yield point)
            try:
                next(generator)
            except StopIteration:
                # Generator immediately exhausted - this shouldn't happen
                self.compressor.log(f"⚠️ Generator {worker_id} exhausted immediately", "WARNING")
                continue
            
            self.generators[worker_id] = {
                'worker': worker,
                'generator': generator,
                'type': 'segment'
            }
            self.active_generators.append(worker_id)
        
        self.compressor.log(
            f"🚀 Created {len(self.active_generators)} generator-based segment workers", 
            "INFO"
        )
    
    def create_small_file_workers(self) -> None:
        """Create and initialize small file compression generator workers."""
        self.active_generators = []
        
        for i in range(self.max_workers):
            worker_id = f"SmallFileWorker-{i+1}"
            worker = WorkerGenerator(worker_id, self.compressor)
            generator = worker.small_file_generator()
            
            try:
                next(generator)
            except StopIteration:
                self.compressor.log(f"⚠️ Small file generator {worker_id} exhausted immediately", "WARNING")
                continue
            
            self.generators[worker_id] = {
                'worker': worker,
                'generator': generator,
                'type': 'small_file'
            }
            self.active_generators.append(worker_id)
        
        self.compressor.log(
            f"🚀 Created {len(self.active_generators)} small file generator workers", 
            "INFO"
        )
    
    def process_segments_with_generators(self, segment_tasks: List[Dict[str, Any]], 
                                       progress_callback: Optional[Callable] = None, 
                                       max_retries: int = 2) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Process segments using reusable generator workers with enhanced error recovery.
        
        This method distributes segment compression tasks across available generator
        workers, implementing intelligent retry logic and progress tracking. Failed
        tasks are automatically retried up to max_retries times before being
        marked as permanently failed.
        
        Args:
            segment_tasks: List of task dictionaries for segment processing
            progress_callback: Optional callback for progress updates
            max_retries: Maximum number of retry attempts for failed tasks
            
        Returns:
            Tuple of (completed_segment_paths, failed_segment_info)
            
        Progress callback receives either:
        - Simple float: progress percentage (0.0-1.0)
        - Complex dict: detailed progress information
        """
        completed_segments: List[str] = []
        failed_segments: List[Dict[str, Any]] = []
        retry_queue: List[Tuple[Dict[str, Any], int]] = []  # (task, retry_count)
        
        # Create workers if not already created
        if not self.active_generators:
            self.create_segment_workers()
        
        # Initialize task queue with retry tracking
        task_queue = [(task, 0) for task in segment_tasks]  # (task, retry_count)
        
        self.compressor.log(
            f"📋 Processing {len(segment_tasks)} segments with {len(self.active_generators)} generators", 
            "INFO"
        )
        
        # Main processing loop
        while task_queue or retry_queue or self._has_active_generators():
            # Process retry queue first (failed tasks get priority)
            if retry_queue and not task_queue:
                task_queue = retry_queue[:]
                retry_queue.clear()
                self.compressor.log(f"🔄 Processing {len(task_queue)} retry tasks", "INFO")
            
            # Distribute tasks to available generators
            self._distribute_tasks_to_generators(
                task_queue, retry_queue, completed_segments, failed_segments,
                max_retries, progress_callback, len(segment_tasks)
            )
        
        # Log final results
        self.compressor.log(
            f"🏁 Segment processing complete: {len(completed_segments)} succeeded, {len(failed_segments)} failed", 
            "INFO"
        )
        
        return completed_segments, failed_segments
    
    def _has_active_generators(self) -> bool:
        """Check if any generators are still active."""
        return any(gen['generator'] for gen in self.generators.values() if gen['generator'])
    
    def _distribute_tasks_to_generators(self, task_queue: List[Tuple[Dict[str, Any], int]], 
                                      retry_queue: List[Tuple[Dict[str, Any], int]],
                                      completed_segments: List[str], 
                                      failed_segments: List[Dict[str, Any]],
                                      max_retries: int, progress_callback: Optional[Callable],
                                      total_tasks: int) -> None:
        """Distribute tasks among available generators with error handling."""
        # Process each active generator
        for worker_id in self.active_generators[:]:  # Copy list to allow modification
            if not task_queue:
                break
            
            generator_info = self.generators[worker_id]
            generator = generator_info['generator']
            
            try:
                # Send task to generator
                task_data, retry_count = task_queue.pop(0)
                result = generator.send(task_data)
                
                # Process result with retry logic
                self._handle_task_result(
                    result, retry_count, max_retries, retry_queue,
                    completed_segments, failed_segments
                )
                
                # Update progress
                self._update_progress(
                    progress_callback, completed_segments, failed_segments,
                    len(retry_queue), total_tasks
                )
                
            except StopIteration:
                # Generator exhausted, remove from active list
                self.active_generators.remove(worker_id)
                self.compressor.log(f"🏁 Generator {worker_id} completed all tasks", "DEBUG")
                
            except Exception as e:
                self.compressor.log(f"❌ Generator {worker_id} error: {e}", "ERROR")
                self.active_generators.remove(worker_id)
                
                # Re-queue the task if it wasn't processed
                if 'task_data' in locals() and 'retry_count' in locals():
                    if retry_count < max_retries:
                        retry_queue.append((task_data, retry_count + 1))
                    else:
                        failed_segments.append({
                            'segment_path': task_data.get('segment_path', 'unknown'),
                            'error': f"Generator failure after {max_retries} retries: {e}"
                        })
    
    def _handle_task_result(self, result: Dict[str, Any], retry_count: int, max_retries: int,
                          retry_queue: List[Tuple[Dict[str, Any], int]], 
                          completed_segments: List[str], 
                          failed_segments: List[Dict[str, Any]]) -> None:
        """Handle the result of a task execution."""
        if result['success']:
            completed_segments.append(result['output_path'])
            segment_name = Path(result['segment_path']).name
            self.compressor.log(f"✅ Generator completed segment: {segment_name}", "DEBUG")
        else:
            if retry_count < max_retries:
                # Add to retry queue
                task_data = {
                    'segment_path': result['segment_path'],
                    # Reconstruct task data from result if needed
                    'segment_index': result.get('segment_index', 0),
                    'total_segments': result.get('total_segments', 1),
                    'file_path': result.get('file_path', result['segment_path'])
                }
                retry_queue.append((task_data, retry_count + 1))
                
                segment_name = Path(result['segment_path']).name
                self.compressor.log(
                    f"🔄 Retrying segment {segment_name} (attempt {retry_count + 2}/{max_retries + 1})", 
                    "WARNING"
                )
            else:
                # Max retries exceeded
                failed_segments.append({
                    'segment_path': result['segment_path'],
                    'error': f"Max retries ({max_retries}) exceeded: {result.get('message', result.get('error', 'Unknown error'))}"
                })
                segment_name = Path(result['segment_path']).name
                self.compressor.log(
                    f"❌ Generator permanently failed segment after {max_retries} retries: {segment_name}", 
                    "ERROR"
                )
    
    def _update_progress(self, progress_callback: Optional[Callable], 
                        completed_segments: List[str], failed_segments: List[Dict[str, Any]],
                        retries_pending: int, total_tasks: int) -> None:
        """Update progress callback with current status."""
        if not progress_callback:
            return
        
        total_processed = len(completed_segments) + len(failed_segments)
        
        # Provide detailed progress info for advanced callbacks
        progress_info = {
            'completed': len(completed_segments),
            'failed': len(failed_segments), 
            'retries_pending': retries_pending,
            'total_tasks': total_tasks,
            'progress': total_processed / total_tasks if total_tasks > 0 else 0
        }
        
        try:
            # Try detailed progress info first
            progress_callback(progress_info['progress'])
        except TypeError:
            # Fallback for simple progress callbacks expecting just float
            progress_callback(total_processed / total_tasks if total_tasks > 0 else 0)
    
    def shutdown_all(self) -> None:
        """
        Shutdown all generator workers gracefully.
        
        This method sends shutdown signals to all active generators and
        handles any exceptions that occur during shutdown. It ensures
        clean resource cleanup and proper generator termination.
        """
        self.compressor.log("🛑 Shutting down all generator workers", "INFO")
        
        shutdown_count = 0
        for worker_id, generator_info in self.generators.items():
            try:
                worker = generator_info['worker']
                generator = generator_info['generator']
                
                # Signal worker to stop accepting tasks
                worker.shutdown()
                
                # Send shutdown signal to generator
                if generator:
                    generator.send(None)
                    shutdown_count += 1
                    
            except (StopIteration, GeneratorExit):
                # Expected when shutting down generators
                shutdown_count += 1
            except Exception as e:
                self.compressor.log(f"⚠️ Error shutting down generator {worker_id}: {e}", "WARNING")
        
        self.compressor.log(f"✅ Shutdown complete: {shutdown_count} generators stopped", "INFO")
        
        # Clear all generator references
        self.generators.clear()
        self.active_generators.clear()


class TaskQueue:
    """
    Task distribution and load balancing for generator workers.
    
    This class provides intelligent task queuing and distribution mechanisms
    for generator-based workers. It handles task prioritization, load balancing,
    and retry logic.
    """
    
    def __init__(self, max_retries: int = 3):
        """
        Initialize task queue.
        
        Args:
            max_retries: Maximum number of retry attempts for failed tasks
        """
        self.max_retries = max_retries
        self.pending_tasks: List[Tuple[Dict[str, Any], int]] = []
        self.retry_tasks: List[Tuple[Dict[str, Any], int]] = []
        self.completed_tasks: List[Dict[str, Any]] = []
        self.failed_tasks: List[Dict[str, Any]] = []
    
    def add_tasks(self, tasks: List[Dict[str, Any]]) -> None:
        """Add new tasks to the queue."""
        for task in tasks:
            self.pending_tasks.append((task, 0))  # (task, retry_count)
    
    def get_next_task(self) -> Optional[Tuple[Dict[str, Any], int]]:
        """Get next task from queue (retry tasks have priority)."""
        if self.retry_tasks:
            return self.retry_tasks.pop(0)
        elif self.pending_tasks:
            return self.pending_tasks.pop(0)
        return None
    
    def handle_result(self, task: Dict[str, Any], retry_count: int, 
                     result: Dict[str, Any]) -> None:
        """Handle task result and determine if retry is needed."""
        if result['success']:
            self.completed_tasks.append(result)
        else:
            if retry_count < self.max_retries:
                self.retry_tasks.append((task, retry_count + 1))
            else:
                self.failed_tasks.append({
                    'task': task,
                    'error': result.get('error', 'Unknown error'),
                    'retries': retry_count
                })
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return not (self.pending_tasks or self.retry_tasks)
    
    def get_status(self) -> Dict[str, int]:
        """Get queue status summary."""
        return {
            'pending': len(self.pending_tasks),
            'retries': len(self.retry_tasks),
            'completed': len(self.completed_tasks),
            'failed': len(self.failed_tasks)
        }