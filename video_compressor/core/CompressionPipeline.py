#!/usr/bin/env python3
"""
CompressionPipeline - Parallel Video Processing Pipeline

Extracted from the monolith VideoCompression.py. Extends CompressorEngine
with parallel processing capabilities and provides the clean programmatic
API (compress_file) for library consumers like the Nook pipeline.
"""

import os
import time
import queue
import threading
from datetime import timedelta
from pathlib import Path
from multiprocessing import cpu_count
from concurrent.futures import ThreadPoolExecutor, as_completed

from .CompressorEngine import VideoCompressor
from ..concurrency.ProgressTracker import ProgressAggregator
from ..exceptions import (
    CompressionError,
    FFmpegError,
    DiskSpaceError,
    VideoAnalysisError,
    IntegrityError,
)
from ..models import CompressResult, VideoInfo


# ---------------------------------------------------------------------------
# Helper classes tightly coupled to the pipeline (from monolith)
# ---------------------------------------------------------------------------

class CompressionAnalytics:
    """Tracks compression metrics for analytics."""

    def __init__(self):
        self.file_metrics = []
        self.session_start = time.time()

    def record_file(self, original_size, compressed_size, duration, codec, hardware_accelerated):
        self.file_metrics.append({
            'original_size': original_size,
            'compressed_size': compressed_size,
            'duration': duration,
            'codec': codec,
            'hardware_accelerated': hardware_accelerated,
            'timestamp': time.time(),
        })

    def get_session_summary(self):
        if not self.file_metrics:
            return {}
        total_orig = sum(m['original_size'] for m in self.file_metrics)
        total_comp = sum(m['compressed_size'] for m in self.file_metrics)
        return {
            'files_processed': len(self.file_metrics),
            'total_original_size': total_orig,
            'total_compressed_size': total_comp,
            'overall_ratio': total_comp / total_orig if total_orig else 0,
            'session_duration': time.time() - self.session_start,
        }


class WorkerGenerator:
    """Generator-based worker for memory-efficient segment processing."""

    def __init__(self, compressor, worker_id):
        self.compressor = compressor
        self.worker_id = worker_id
        self.processed = 0
        self.failed = 0

    def segment_compression_generator(self, tasks, progress_callback=None):
        for task in tasks:
            segment_path = task['segment_path']
            segment_index = task['segment_index']
            total_segments = task['total_segments']

            try:
                segment_path_obj = Path(segment_path)
                output_path = segment_path_obj.parent / f"{segment_path_obj.stem}_compressed{segment_path_obj.suffix}"

                def seg_progress(p, _idx=segment_index, _total=total_segments):
                    if progress_callback:
                        overall = (_idx + p) / _total
                        progress_callback(overall)

                success, message = self.compressor.compress_single_segment(
                    segment_path, output_path, seg_progress)

                if success:
                    self.processed += 1
                    try:
                        Path(segment_path).unlink()
                    except Exception:
                        pass
                    yield {'success': True, 'output_path': str(output_path), 'segment_path': segment_path}
                else:
                    self.failed += 1
                    yield {'success': False, 'error': message, 'segment_path': segment_path}

            except Exception as e:
                self.failed += 1
                yield {'success': False, 'error': str(e), 'segment_path': segment_path}


class GeneratorWorkerManager:
    """Manages generator-based workers for parallel segment processing."""

    def __init__(self, compressor, max_workers):
        self.compressor = compressor
        self.max_workers = max_workers
        self.workers = []

    def process_segments_with_generators(self, segment_tasks, progress_callback=None):
        completed = []
        failed = []

        if len(segment_tasks) <= self.max_workers:
            worker = WorkerGenerator(self.compressor, "gen_worker_0")
            for result in worker.segment_compression_generator(segment_tasks, progress_callback):
                if result['success']:
                    completed.append(result['output_path'])
                else:
                    failed.append(result)
        else:
            chunks = [[] for _ in range(self.max_workers)]
            for i, task in enumerate(segment_tasks):
                chunks[i % self.max_workers].append(task)

            results_queue = queue.Queue()

            def worker_fn(chunk, worker_id):
                worker = WorkerGenerator(self.compressor, f"gen_worker_{worker_id}")
                for result in worker.segment_compression_generator(chunk, progress_callback):
                    results_queue.put(result)

            threads = []
            for i, chunk in enumerate(chunks):
                if chunk:
                    t = threading.Thread(target=worker_fn, args=(chunk, i), daemon=True)
                    threads.append(t)
                    t.start()

            for t in threads:
                t.join()

            while not results_queue.empty():
                result = results_queue.get_nowait()
                if result['success']:
                    completed.append(result['output_path'])
                else:
                    failed.append(result)

        return completed, failed

    def shutdown_all(self):
        self.workers.clear()


# ---------------------------------------------------------------------------
# ParallelVideoProcessor - the main pipeline class
# ---------------------------------------------------------------------------

class ParallelVideoProcessor(VideoCompressor):
    """
    Enhanced video processor with parallel processing capabilities.

    Extends VideoCompressor with multi-threaded segment processing,
    intelligent file categorization, and the clean compress_file() API
    for programmatic library usage.

    Can be initialized with either a config file path or a config dict:
        pipeline = ParallelVideoProcessor(config_path="config.json")
        pipeline = ParallelVideoProcessor(config={"ffmpeg_path": "...", ...})
    """

    def __init__(self, config_path="config.json", config=None):
        super().__init__(config_path=config_path, config=config)

        parallel_config = self.config.get("parallel_processing", {})
        self.parallel_enabled = parallel_config.get("enabled", True)
        max_workers_config = parallel_config.get("max_workers", 4)

        cpu_cores = cpu_count()
        self.max_concurrent_jobs = min(max_workers_config, cpu_cores)

        self.generator_manager = GeneratorWorkerManager(self, self.max_concurrent_jobs)
        self.analytics = CompressionAnalytics()

        max_workers_limit = parallel_config.get("max_workers_limit", 16)
        self.max_concurrent_jobs = max(1, min(self.max_concurrent_jobs, max_workers_limit))
        self.segment_parallel = parallel_config.get("segment_parallel", True)

        self.log(f"🚀 ParallelVideoProcessor initialized", "INFO")
        self.log(f"   Parallel: {'✅' if self.parallel_enabled else '❌'} | "
                 f"Workers: {self.max_concurrent_jobs} (cores: {cpu_cores}) | "
                 f"Segment parallel: {'✅' if self.segment_parallel else '❌'}", "INFO")

    # ------------------------------------------------------------------
    # Clean programmatic API for library consumers (Nook pipeline)
    # ------------------------------------------------------------------

    def compress_file(self, input_path, output_dir=None, progress_callback=None):
        """
        Compress a single video file programmatically.

        This is the primary entry point for library consumers. It handles
        segmentation, parallel compression, merging, and verification
        internally and returns a typed result object.

        Args:
            input_path: Path to the input video file.
            output_dir: Directory for the output file. If None, uses the
                        same directory as the input file.
            progress_callback: Optional callable receiving a dict with at
                               minimum: percent, stage, eta_seconds.

        Returns:
            CompressResult with compression metadata.

        Raises:
            CompressionError: Base class for all compression failures.
            FFmpegError: FFmpeg process failure.
            DiskSpaceError: Insufficient disk space.
            VideoAnalysisError: Cannot analyse the input video.
            IntegrityError: Compressed file fails verification.
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise CompressionError(f"Input file does not exist: {input_path}")

        # Determine output path
        if output_dir is not None:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = input_path.parent

        output_name = f"{input_path.stem}_compressed{input_path.suffix}"
        final_output = output_dir / output_name

        # Disk space check
        space_ok, space_msg = self.check_disk_space(input_path)
        if not space_ok:
            raise DiskSpaceError(space_msg)

        # Get original video info
        original_info = self.get_video_info(input_path)
        if not original_info:
            raise VideoAnalysisError(f"Cannot read video information: {input_path}")

        original_size = input_path.stat().st_size
        video_duration = self.get_video_duration(original_info)

        # Detect hardware acceleration for result metadata
        hw_accel = self.detect_hardware_acceleration()
        hardware_accelerated = hw_accel is not None

        # Determine codec being used
        settings = self.get_compression_settings()
        codec = settings.get("video_codec", "libx265")
        if hw_accel and hw_accel.get("hevc_encoder") and codec == "libx265":
            codec = "h265"
        elif hw_accel and hw_accel.get("h264_encoder"):
            codec = "h264"

        # Get resolution from original info
        video_stream = next(
            (s for s in original_info.get("streams", []) if s.get("codec_type") == "video"), None)
        resolution = (0, 0)
        if video_stream:
            resolution = (video_stream.get("width", 0), video_stream.get("height", 0))

        # Progress wrapper to translate internal progress into the API format
        start_time = time.time()
        segments_used = [1]  # mutable container so inner fn can update
        current_stage = ["analyzing"]

        def _api_progress_callback(raw_progress):
            if not progress_callback:
                return

            # Handle both dict and float progress data (per CLAUDE.md requirement)
            if isinstance(raw_progress, dict):
                percent = raw_progress.get('overall_progress', 0.0)
            else:
                percent = float(raw_progress) if raw_progress is not None else 0.0

            percent = max(0.0, min(1.0, percent))

            # Determine stage from percent ranges
            if percent < 0.10:
                stage = "analyzing"
            elif percent < 0.25:
                stage = "segmenting"
            elif percent < 0.90:
                stage = "compressing"
            elif percent < 0.98:
                stage = "merging"
            else:
                stage = "verifying"

            current_stage[0] = stage

            # Calculate ETA
            elapsed = time.time() - start_time
            if percent > 0.01:
                total_estimated = elapsed / percent
                eta_seconds = max(0, total_estimated - elapsed)
            else:
                eta_seconds = 0

            # Calculate throughput
            throughput_mbps = 0.0
            if elapsed > 0:
                processed_bytes = original_size * percent
                throughput_mbps = (processed_bytes / (1024 * 1024)) / elapsed

            progress_data = {
                "percent": percent,
                "throughput_mbps": round(throughput_mbps, 1),
                "eta_seconds": int(eta_seconds),
                "stage": stage,
                "current_segment": 0,
                "total_segments": segments_used[0],
            }

            progress_callback(progress_data)

        # Determine if segmentation is needed and count segments
        will_segment = self.should_segment_file(input_path)
        if will_segment:
            seg_dur = self.config.get("segmentation_settings", {}).get("segment_duration_seconds", 600)
            if video_duration > 0:
                segments_used[0] = max(1, int(video_duration / seg_dur))

        # Create temp directory
        temp_dir = input_path.parent / ".video_compression_temp"
        temp_dir.mkdir(exist_ok=True)
        temp_output = temp_dir / output_name

        try:
            # Run compression
            success, message = self.compress_video(
                input_path, temp_output, dry_run=False,
                progress_callback=_api_progress_callback
            )

            if not success:
                raise FFmpegError(message)

            # Verify integrity
            integrity_ok, integrity_msg = self.verify_file_integrity(temp_output, original_info)
            if not integrity_ok:
                raise IntegrityError(f"Compressed file verification failed: {integrity_msg}")

            # Move to final location
            if final_output.exists():
                final_output.unlink()
            import shutil
            shutil.move(str(temp_output), str(final_output))

            # Final verification
            final_ok, final_msg = self.verify_file_integrity(final_output, original_info)
            if not final_ok:
                raise IntegrityError(f"Final verification failed: {final_msg}")

            compressed_size = final_output.stat().st_size
            processing_time = time.time() - start_time

            # Record analytics
            self.analytics.record_file(
                original_size, compressed_size, processing_time,
                codec, hardware_accelerated
            )

            # Send final progress
            if progress_callback:
                progress_callback({
                    "percent": 1.0,
                    "throughput_mbps": round(
                        (original_size / (1024 * 1024)) / processing_time, 1
                    ) if processing_time > 0 else 0.0,
                    "eta_seconds": 0,
                    "stage": "complete",
                    "current_segment": segments_used[0],
                    "total_segments": segments_used[0],
                })

            return CompressResult(
                output_path=str(final_output),
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=round(compressed_size / original_size, 4) if original_size else 0,
                duration_seconds=video_duration,
                codec=codec,
                resolution=resolution,
                processing_time_seconds=round(processing_time, 1),
                segments_used=segments_used[0],
                hardware_accelerated=hardware_accelerated,
            )

        except (CompressionError, FFmpegError, DiskSpaceError,
                VideoAnalysisError, IntegrityError):
            raise
        except Exception as e:
            raise CompressionError(f"Unexpected compression error: {type(e).__name__}: {e}") from e
        finally:
            # Clean up temp dir
            self.cleanup_temp_files(temp_output)
            try:
                if temp_dir.exists() and temp_dir.name == ".video_compression_temp":
                    if not any(temp_dir.iterdir()):
                        temp_dir.rmdir()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Generator-based parallel segment processing
    # ------------------------------------------------------------------

    def process_segments_with_generators(self, segments, output_dir, progress_callback=None):
        """Process segments using generator-based workers."""
        if not segments:
            return [], "No segments provided"

        self.log(f"🔄 GENERATOR-BASED SEGMENT PROCESSING", "INFO")

        segment_tasks = []
        for i, segment_path in enumerate(segments):
            segment_tasks.append({
                'segment_path': segment_path,
                'segment_index': i,
                'total_segments': len(segments),
                'file_path': Path(segment_path).parent,
            })

        try:
            completed, failed = self.generator_manager.process_segments_with_generators(
                segment_tasks, progress_callback)

            if failed:
                return completed, f"Generator processing completed with {len(failed)} failures"
            return completed, "All segments processed successfully with generator workers"

        except Exception as e:
            self.log(f"❌ Generator processing error: {e}, falling back", "ERROR")
            return self.process_segments_parallel_traditional(segments, output_dir, progress_callback)
        finally:
            self.generator_manager.shutdown_all()

    def process_segments_parallel(self, segments, output_dir, progress_callback=None):
        """Smart dispatcher: Choose between generator-based or ThreadPoolExecutor processing."""
        if not segments:
            return [], "No segments provided"

        use_generators = len(segments) > 10 and self.max_concurrent_jobs >= 4

        if use_generators:
            self.log(f"🧠 Using generator-based processing for {len(segments)} segments", "INFO")
            return self.process_segments_with_generators(segments, output_dir, progress_callback)
        else:
            self.log(f"🧠 Using ThreadPoolExecutor processing for {len(segments)} segments", "INFO")
            return self.process_segments_parallel_traditional(segments, output_dir, progress_callback)

    def process_segments_parallel_traditional(self, segments, output_dir, progress_callback=None):
        """Traditional ThreadPoolExecutor-based segment processing."""
        if not segments:
            return [], "No segments provided"

        if not self.parallel_enabled or len(segments) == 1:
            return self._process_segments_sequential(segments, output_dir, progress_callback)

        self.log(f"🔄 PARALLEL SEGMENT PROCESSING: {len(segments)} segments", "INFO")

        self.progress_aggregator = ProgressAggregator()
        if progress_callback:
            self.progress_aggregator.set_callback(progress_callback)

        for i, segment_path in enumerate(segments):
            segment_size = os.path.getsize(segment_path)
            worker_id = f"parallel_segment_{i + 1}"
            task_name = f"Parallel Segment {i + 1}/{len(segments)}: {Path(segment_path).name}"
            segment_info = {'current': i + 1, 'total': len(segments), 'duration': None}
            self.progress_aggregator.register_worker(worker_id, task_name, segment_size, segment_info)

        progress_queue_local = queue.Queue()
        completed_segments = []
        failed_segments = []

        def compress_segment_worker(segment_path, segment_index, total_segments):
            worker_id = threading.current_thread().name
            segment_name = Path(segment_path).name
            try:
                segment_path_obj = Path(segment_path)
                output_path = Path(output_dir) / f"{segment_path_obj.stem}_compressed{segment_path_obj.suffix}"

                def segment_progress(seg_progress):
                    progress_worker_id = f"parallel_segment_{segment_index + 1}"
                    self.progress_aggregator.update_worker_progress(progress_worker_id, seg_progress)

                success, message = self.compress_single_segment(segment_path, output_path, segment_progress)

                progress_worker_id = f"parallel_segment_{segment_index + 1}"
                if success:
                    self.progress_aggregator.complete_worker(progress_worker_id)
                    try:
                        Path(segment_path).unlink()
                    except Exception:
                        pass
                    result = {
                        'segment_index': segment_index, 'input_path': segment_path,
                        'output_path': str(output_path), 'success': True,
                        'message': message, 'worker_id': worker_id,
                    }
                else:
                    self.progress_aggregator.fail_worker(progress_worker_id, message)
                    result = {
                        'segment_index': segment_index, 'input_path': segment_path,
                        'output_path': None, 'success': False,
                        'message': message, 'worker_id': worker_id,
                    }

                try:
                    progress_queue_local.put(result, timeout=1.0)
                except queue.Full:
                    pass
                return result

            except Exception as e:
                error_msg = f"Worker exception in segment {segment_index + 1}: {type(e).__name__}: {e}"
                self.log(f"❌ [{worker_id}] {error_msg}", "ERROR")
                progress_worker_id = f"parallel_segment_{segment_index + 1}"
                self.progress_aggregator.fail_worker(progress_worker_id, error_msg)
                result = {
                    'segment_index': segment_index, 'input_path': segment_path,
                    'output_path': None, 'success': False,
                    'message': error_msg, 'worker_id': worker_id,
                }
                try:
                    progress_queue_local.put(result, timeout=1.0)
                except queue.Full:
                    pass
                return result

        actual_workers = min(self.max_concurrent_jobs, len(segments))
        start_time = time.time()

        try:
            with ThreadPoolExecutor(max_workers=actual_workers, thread_name_prefix="SegmentWorker") as executor:
                futures = {
                    executor.submit(compress_segment_worker, seg, i, len(segments)): i
                    for i, seg in enumerate(segments)
                }

                completed_count = 0
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=3600)
                        if result['success']:
                            completed_segments.append(result['output_path'])
                        else:
                            failed_segments.append((result['input_path'], result['message']))
                        completed_count += 1
                    except Exception as e:
                        idx = futures[future]
                        failed_segments.append((segments[idx], str(e)))
                        completed_count += 1

                if progress_callback:
                    progress_callback(1.0)

        except Exception as e:
            self.log(f"❌ Parallel segment processing error: {e}", "ERROR")
            return [], str(e)

        total_time = time.time() - start_time
        self.log(f"🏁 PARALLEL COMPLETE: {len(completed_segments)} ok, "
                 f"{len(failed_segments)} failed in {timedelta(seconds=int(total_time))}", "INFO")

        if failed_segments:
            return completed_segments, f"Completed with {len(failed_segments)} failures"
        return completed_segments, "All segments processed successfully in parallel"

    def _process_segments_sequential(self, segments, output_dir, progress_callback=None):
        """Fall back to sequential segment processing."""
        completed_segments = []
        failed_segments = []

        for i, segment_path in enumerate(segments):
            segment_path_obj = Path(segment_path)
            output_path = Path(output_dir) / f"{segment_path_obj.stem}_compressed{segment_path_obj.suffix}"

            def segment_progress(seg_progress, _i=i):
                if progress_callback:
                    progress_callback((_i + seg_progress) / len(segments))

            success, message = self.compress_single_segment(segment_path, output_path, segment_progress)
            if success:
                completed_segments.append(str(output_path))
            else:
                failed_segments.append((segment_path, message))

        if progress_callback:
            progress_callback(1.0)

        if failed_segments:
            return completed_segments, f"Sequential processing completed with {len(failed_segments)} failures"
        return completed_segments, "All segments processed successfully sequentially"

    # ------------------------------------------------------------------
    # Multi-file parallel processing
    # ------------------------------------------------------------------

    def process_files_parallel(self, file_list, dry_run=False, progress_callback=None):
        """Process multiple files with intelligent parallel processing."""
        if not file_list:
            self.log("No files provided for processing", "WARNING")
            return

        self.log(f"\n🚀 PARALLEL FILE PROCESSING {'(DRY RUN)' if dry_run else ''}", "INFO")

        if not self.parallel_enabled:
            return self.process_file_list(file_list, dry_run, progress_callback)

        large_file_threshold = self.config.get("large_file_settings", {}).get("threshold_gb", 10) * (1024 ** 3)
        small_files = []
        large_files = []
        for file_path in file_list:
            if Path(file_path).exists():
                if os.path.getsize(file_path) >= large_file_threshold:
                    large_files.append(file_path)
                else:
                    small_files.append(file_path)

        if dry_run:
            self.log(f"[DRY RUN] Small: {len(small_files)}, Large: {len(large_files)}", "INFO")
            return

        start_time = time.time()
        total_processed = 0
        total_failed = 0

        try:
            if small_files:
                p, f_ = self._process_small_files_parallel(
                    small_files,
                    lambda p: progress_callback(p * 0.5) if progress_callback else None)
                total_processed += p
                total_failed += f_

            if large_files:
                p, f_ = self._process_large_files_with_segmentation(
                    large_files,
                    lambda p: progress_callback(0.5 + p * 0.5) if progress_callback else None)
                total_processed += p
                total_failed += f_

        except KeyboardInterrupt:
            self.cleanup_all_temp_directories()
            raise

        if progress_callback:
            progress_callback(1.0)

        self.log(f"🏁 DONE: {total_processed} processed, {total_failed} failed "
                 f"in {timedelta(seconds=int(time.time() - start_time))}", "INFO")
        self.cleanup_all_temp_directories()

    def _process_small_files_parallel(self, small_files, progress_callback=None):
        """Process small files in parallel with load balancing."""
        if not small_files:
            return 0, 0

        actual_workers = min(self.max_concurrent_jobs, len(small_files))
        processed_count = 0
        failed_count = 0

        def worker(file_path):
            worker_id = threading.current_thread().name
            try:
                success, message = self.process_file(file_path, dry_run=False)
                return {'file_path': file_path, 'success': success, 'message': message}
            except Exception as e:
                return {'file_path': file_path, 'success': False, 'message': str(e)}

        try:
            with ThreadPoolExecutor(max_workers=actual_workers, thread_name_prefix="SmallFileWorker") as executor:
                futures = {executor.submit(worker, fp): fp for fp in small_files}
                for i, future in enumerate(as_completed(futures), 1):
                    try:
                        result = future.result(timeout=7200)
                        if result['success']:
                            processed_count += 1
                            self.processed_files.append(result['file_path'])
                        else:
                            failed_count += 1
                            self.failed_files.append((result['file_path'], result['message']))
                        if progress_callback:
                            progress_callback(i / len(small_files))
                    except Exception as e:
                        fp = futures[future]
                        failed_count += 1
                        self.failed_files.append((fp, str(e)))
        except Exception:
            failed_count += len(small_files) - processed_count

        return processed_count, failed_count

    def _process_large_files_with_segmentation(self, large_files, progress_callback=None):
        """Process large files using segmentation with optional pipeline parallelism."""
        if not large_files:
            return 0, 0

        pipeline_enabled = (
            self.segment_parallel and len(large_files) > 1 and self.max_concurrent_jobs > 1)

        if pipeline_enabled:
            return self._process_large_files_pipeline(large_files, progress_callback)
        return self._process_large_files_sequential(large_files, progress_callback)

    def _process_large_files_sequential(self, large_files, progress_callback=None):
        """Sequential processing for large files."""
        processed = 0
        failed = 0
        for i, file_path in enumerate(large_files):
            try:
                if self.segment_parallel:
                    success, msg = self._process_large_file_with_parallel_segments(file_path)
                else:
                    success, msg = self.process_file(file_path, dry_run=False)
                if success:
                    processed += 1
                    self.processed_files.append(file_path)
                else:
                    failed += 1
                    self.failed_files.append((file_path, msg))
                if progress_callback:
                    progress_callback((i + 1) / len(large_files))
            except Exception as e:
                failed += 1
                self.failed_files.append((file_path, str(e)))
        return processed, failed

    def _process_large_files_pipeline(self, large_files, progress_callback=None):
        """Pipeline parallelism: overlap segmentation and compression across files."""
        processed_count = 0
        failed_count = 0

        queue_size = min(50, max(10, len(large_files) * 5))
        segment_queue = queue.Queue(maxsize=queue_size)
        file_status = {}
        pipeline_lock = threading.RLock()
        pipeline_progress = {
            'total_files': len(large_files), 'files_segmented': 0,
            'total_segments': 0, 'segments_compressed': 0, 'files_completed': 0,
        }

        for fp in large_files:
            file_status[fp] = {
                'status': 'pending', 'segments': [],
                'compressed_segments': [], 'error': None,
            }

        def segmentation_producer():
            try:
                for i, fp in enumerate(large_files):
                    with pipeline_lock:
                        file_status[fp]['status'] = 'segmenting'
                    try:
                        segs = self.segment_video(fp)
                        if segs:
                            with pipeline_lock:
                                file_status[fp]['segments'] = segs
                                file_status[fp]['status'] = 'segments_ready'
                                pipeline_progress['files_segmented'] += 1
                                pipeline_progress['total_segments'] += len(segs)
                            for j, seg in enumerate(segs):
                                segment_queue.put({
                                    'file_path': fp, 'segment_path': seg,
                                    'segment_index': j, 'total_segments': len(segs),
                                })
                        else:
                            with pipeline_lock:
                                file_status[fp]['status'] = 'failed'
                                file_status[fp]['error'] = 'Segmentation failed'
                    except Exception as e:
                        with pipeline_lock:
                            file_status[fp]['status'] = 'failed'
                            file_status[fp]['error'] = str(e)
                for _ in range(self.max_concurrent_jobs):
                    segment_queue.put(None)
            except Exception:
                for _ in range(self.max_concurrent_jobs):
                    try:
                        segment_queue.put(None, timeout=1)
                    except Exception:
                        pass

        def consumer():
            while True:
                try:
                    job = segment_queue.get(timeout=30)
                except queue.Empty:
                    break
                if job is None:
                    segment_queue.task_done()
                    break
                try:
                    seg_obj = Path(job['segment_path'])
                    out = seg_obj.parent / f"{seg_obj.stem}_compressed{seg_obj.suffix}"
                    ok, _ = self.compress_single_segment(job['segment_path'], out)
                    if ok:
                        with pipeline_lock:
                            file_status[job['file_path']]['compressed_segments'].append(str(out))
                            pipeline_progress['segments_compressed'] += 1
                        try:
                            Path(job['segment_path']).unlink()
                        except Exception:
                            pass
                except Exception:
                    pass
                finally:
                    segment_queue.task_done()

        producer_thread = threading.Thread(target=segmentation_producer, name="Producer", daemon=True)
        producer_thread.start()

        with ThreadPoolExecutor(max_workers=self.max_concurrent_jobs, thread_name_prefix="Consumer") as executor:
            consumer_futures = [executor.submit(consumer) for _ in range(self.max_concurrent_jobs)]
            producer_thread.join()
            for f in as_completed(consumer_futures):
                try:
                    f.result()
                except Exception:
                    pass

        segment_queue.join()

        # Merge phase
        for fp in large_files:
            status = file_status[fp]
            if status['status'] == 'failed' or not status['compressed_segments']:
                failed_count += 1
                self.failed_files.append((fp, status.get('error', 'No compressed segments')))
                continue
            try:
                fp_obj = Path(fp)
                out = fp_obj.parent / f"{fp_obj.stem}_compressed{fp_obj.suffix}"
                ok, msg = self.merge_compressed_segments(status['compressed_segments'], out)
                if ok:
                    original_info = self.get_video_info(fp)
                    int_ok, _ = self.verify_file_integrity(out, original_info)
                    if int_ok:
                        processed_count += 1
                        self.processed_files.append(fp)
                        if self.config.get("safety_settings", {}).get("delete_original_after_compression", True):
                            try:
                                Path(fp).unlink()
                            except Exception:
                                pass
                    else:
                        failed_count += 1
                else:
                    failed_count += 1
            except Exception:
                failed_count += 1
            finally:
                for cs in status['compressed_segments']:
                    try:
                        if Path(cs).exists():
                            Path(cs).unlink()
                    except Exception:
                        pass

        if progress_callback:
            progress_callback(1.0)

        return processed_count, failed_count

    def _process_large_file_with_parallel_segments(self, file_path):
        """Process a single large file using parallel segment compression."""
        file_path = Path(file_path)
        if not file_path.exists():
            return False, f"File does not exist: {file_path}"

        space_ok, space_msg = self.check_disk_space(file_path)
        if not space_ok:
            return False, space_msg

        try:
            # Check for existing segments
            existing_segments, _ = self.check_existing_segments(file_path)
            _, existing_compressed, total_expected = self.check_existing_compressed_segments(file_path)

            if not existing_segments and existing_compressed:
                compressed_numbers = []
                for cp in existing_compressed:
                    parts = Path(cp).stem.split('_')
                    compressed_numbers.append(int(parts[2]))

                missing = self.get_missing_segment_numbers(compressed_numbers, total_expected)
                if missing:
                    new_segs = self.create_specific_segments(file_path, missing)
                    all_segments = new_segs or []
                else:
                    all_segments = []
                use_smart_resume = True
            else:
                use_smart_resume = False
                if not existing_segments:
                    segs = self.segment_video(file_path)
                    if not segs:
                        return False, "Failed to create segments"
                    all_segments = segs
                else:
                    all_segments = existing_segments

            all_segments.sort()

            if use_smart_resume:
                segments_to_process = all_segments
                existing_comp = existing_compressed
            else:
                segments_to_process, existing_comp = self.filter_segments_for_processing(all_segments)

            if segments_to_process:
                seg_dir = Path(segments_to_process[0]).parent
                newly_compressed, msg = self.process_segments_parallel(segments_to_process, seg_dir)
                if not newly_compressed and not existing_comp:
                    self.cleanup_segment_files(all_segments)
                    return False, f"No segments compressed: {msg}"
                compressed_segments = (existing_comp or []) + (newly_compressed or [])
            else:
                compressed_segments = existing_comp or []

            if not compressed_segments:
                return False, "No compressed segments available"

            def extract_seg_num(path):
                try:
                    parts = Path(path).stem.split('_')
                    idx = parts.index('segment')
                    return int(parts[idx + 1])
                except (ValueError, IndexError):
                    return Path(path).name

            compressed_segments.sort(key=extract_seg_num)

            output_name = f"{file_path.stem}_compressed{file_path.suffix}"
            final_output = file_path.parent / output_name

            ok, merge_msg = self.merge_compressed_segments(compressed_segments, final_output)
            if not ok:
                return False, f"Merge failed: {merge_msg}"

            original_info = self.get_video_info(file_path)
            int_ok, int_msg = self.verify_file_integrity(final_output, original_info)
            if not int_ok:
                return False, f"Verification failed: {int_msg}"

            original_size = file_path.stat().st_size
            compressed_size = final_output.stat().st_size
            space_saved = original_size - compressed_size

            if self.config.get("safety_settings", {}).get("delete_original_after_compression", True):
                file_path.unlink()

            self.cleanup_segment_files(all_segments, compressed_segments)
            self._cleanup_segment_directories(file_path)

            return True, f"Large file processed. Saved {space_saved / (1024 ** 3):.2f}GB"

        except Exception as e:
            return False, f"Parallel large file error: {type(e).__name__}: {e}"

    # ------------------------------------------------------------------
    # Resume / segment management helpers
    # ------------------------------------------------------------------

    def check_existing_segments(self, source_file):
        """Check for existing segment files."""
        source_path = Path(source_file)
        segments_dir = source_path.parent / f"{source_path.stem}_segments"

        if not segments_dir.exists():
            return [], []

        segment_pattern = f"{source_path.stem}_segment_*.mov"
        existing_files = sorted(
            segments_dir.glob(segment_pattern),
            key=lambda x: int(x.stem.split('_')[-1]) if x.stem.split('_')[-1].isdigit() else 0
        )
        return [str(f) for f in existing_files], []

    def check_existing_compressed_segments(self, source_file):
        """Check for existing compressed segment files for smart resume."""
        source_path = Path(source_file)
        segments_dir = source_path.parent / f"{source_path.stem}_segments"

        if not segments_dir.exists():
            return [], [], 0

        compressed_pattern = f"{source_path.stem}_segment_*_compressed{source_path.suffix}"
        compressed_files = sorted(
            segments_dir.glob(compressed_pattern),
            key=lambda x: int(x.stem.split('_')[2]) if len(x.stem.split('_')) > 2 and x.stem.split('_')[2].isdigit() else 0
        )

        if not compressed_files:
            return [], [], 0

        existing_compressed = [str(f) for f in compressed_files]
        segment_numbers = []
        inferred_raw = []

        for cf in compressed_files:
            parts = cf.stem.split('_')
            if len(parts) > 2 and parts[2].isdigit():
                seg_num = int(parts[2])
                segment_numbers.append(seg_num)
                raw_name = f"{source_path.stem}_segment_{parts[2]}{source_path.suffix}"
                inferred_raw.append(str(segments_dir / raw_name))

        # Estimate total expected segments
        try:
            info = self.get_video_info(source_file)
            if info:
                dur = float(info.get("format", {}).get("duration", 0))
                seg_dur = self.config.get("segmentation_settings", {}).get("segment_duration_seconds", 600)
                total_expected = max(1, int((dur + seg_dur - 1) // seg_dur))
            else:
                total_expected = max(segment_numbers) if segment_numbers else 0
        except Exception:
            total_expected = max(segment_numbers) if segment_numbers else 0

        return inferred_raw, existing_compressed, total_expected

    def get_missing_segment_numbers(self, existing_segment_numbers, total_expected):
        """Determine which segment numbers are missing."""
        if total_expected <= 0:
            return []
        expected = set(range(1, total_expected + 1))
        existing = set(existing_segment_numbers)
        return sorted(expected - existing)

    def create_specific_segments(self, input_path, segment_numbers):
        """Create only specific segments by number."""
        if not segment_numbers:
            return []

        import subprocess
        input_path = Path(input_path)

        if self.config.get("large_file_settings", {}).get("use_same_filesystem", True):
            segments_dir = input_path.parent / f"{input_path.stem}_segments"
        else:
            segments_dir = Path(self.config.get("temp_dir", "/tmp")) / f"{input_path.stem}_segments"

        segments_dir.mkdir(exist_ok=True)
        segment_duration = self.config.get("segmentation_settings", {}).get("segment_duration_seconds", 600)
        created = []

        for seg_num in segment_numbers:
            start_time_val = (seg_num - 1) * segment_duration
            seg_filename = f"{input_path.stem}_segment_{seg_num:03d}{input_path.suffix}"
            seg_path = segments_dir / seg_filename

            cmd = [
                self.config["ffmpeg_path"],
                "-i", str(input_path),
                "-ss", str(start_time_val), "-t", str(segment_duration),
                "-c", "copy", "-map", "0", "-avoid_negative_ts", "make_zero",
                str(seg_path)
            ]

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0 and seg_path.exists() and seg_path.stat().st_size > 0:
                    created.append(str(seg_path))
            except Exception:
                pass

        return created

    def filter_segments_for_processing(self, segment_paths):
        """Filter segments: which need compression vs already compressed."""
        to_process = []
        existing_compressed = []

        for seg_path in segment_paths:
            seg_file = Path(seg_path)
            compressed_path = seg_file.parent / f"{seg_file.stem}_compressed{seg_file.suffix}"
            if compressed_path.exists() and compressed_path.stat().st_size > 0:
                try:
                    info = self.get_video_info(compressed_path)
                    if info and float(info.get("format", {}).get("duration", 0)) > 0:
                        existing_compressed.append(str(compressed_path))
                        continue
                except Exception:
                    pass
            to_process.append(seg_path)

        return to_process, existing_compressed

    def verify_segment_completeness(self, source_file, segment_paths):
        """Verify segments are complete and valid."""
        if not segment_paths:
            return [], []
        try:
            source_info = self.get_video_info(source_file)
            if not source_info:
                return segment_paths, []

            valid = []
            invalid = []
            for seg_path in segment_paths:
                seg_file = Path(seg_path)
                if not seg_file.exists() or seg_file.stat().st_size == 0:
                    invalid.append(seg_path)
                    continue
                seg_info = self.get_video_info(seg_path)
                if not seg_info:
                    invalid.append(seg_path)
                    continue
                dur = float(seg_info.get("format", {}).get("duration", 0))
                if dur <= 0:
                    invalid.append(seg_path)
                    continue
                valid.append(seg_path)
            return valid, invalid
        except Exception:
            return segment_paths, []
