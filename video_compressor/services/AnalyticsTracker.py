#!/usr/bin/env python3
"""
Analytics Tracker - Compression Performance and Efficiency Monitoring

This module provides comprehensive analytics tracking for video compression operations.
It implements an observer pattern to collect metrics without tight coupling to the
compression engine, enabling detailed performance analysis and optimization insights.

Key features:
- Compression efficiency metrics (ratio, size reduction, throughput)
- Performance tracking (processing time, speed analysis)
- Session-level analytics with historical data
- Real-time efficiency scoring algorithms
- Export capabilities for analysis and reporting
- Observer pattern implementation for loose coupling

The analytics system is designed to be non-intrusive, collecting metrics
passively without impacting compression performance. All metrics are calculated
incrementally to minimize computational overhead during compression operations.
"""

import time
import statistics
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod


@dataclass
class FileCompressionMetric:
    """
    Data class for individual file compression metrics.
    
    This structure contains all relevant metrics for a single file compression
    operation, providing a standardized format for analysis and reporting.
    """
    file_path: str
    original_size: int          # Bytes
    compressed_size: int        # Bytes
    size_reduction: int         # Bytes saved
    compression_ratio: float    # compressed/original (lower is better)
    processing_time: float      # Seconds
    throughput_mbps: float      # Megabytes per second
    efficiency_score: float     # Composite efficiency metric
    timestamp: float           # Unix timestamp
    codec_used: str = "unknown"
    hardware_acceleration: bool = False
    segment_count: int = 1     # Number of segments if file was segmented


@dataclass 
class SessionAnalytics:
    """
    Session-level analytics aggregation.
    
    Contains aggregate metrics for an entire compression session,
    providing insights into overall performance and efficiency.
    """
    total_files_processed: int
    total_original_size: int     # Total bytes processed
    total_compressed_size: int   # Total bytes after compression
    total_size_reduction: int    # Total bytes saved
    average_compression_ratio: float
    processing_time_seconds: float
    throughput_mbps: float
    efficiency_score: float
    session_duration: float
    files_with_hw_accel: int
    average_file_size: float


class AnalyticsObserver(ABC):
    """
    Abstract base class for analytics observers.
    
    Implements the observer pattern for analytics collection,
    allowing multiple subscribers to receive compression metrics
    without tight coupling to the compression engine.
    """
    
    @abstractmethod
    def on_compression_complete(self, metric: FileCompressionMetric) -> None:
        """Called when a file compression operation completes."""
        pass
    
    @abstractmethod
    def on_session_start(self) -> None:
        """Called when a compression session begins."""
        pass
    
    @abstractmethod
    def on_session_end(self, session_analytics: SessionAnalytics) -> None:
        """Called when a compression session ends."""
        pass


class CompressionAnalytics:
    """
    Comprehensive compression analytics tracker with observer pattern support.
    
    This class tracks detailed compression metrics and provides real-time
    performance analysis. It uses an observer pattern to decouple analytics
    collection from the core compression logic.
    
    The analytics system calculates:
    - Individual file compression metrics
    - Session-level aggregate statistics  
    - Efficiency scores combining compression ratio and processing speed
    - Hardware acceleration utilization
    - Throughput analysis and optimization recommendations
    """
    
    def __init__(self):
        """Initialize analytics tracker with empty metrics."""
        self.compression_stats = {
            'total_files_processed': 0,
            'total_original_size': 0,
            'total_compressed_size': 0, 
            'total_size_reduction': 0,
            'average_compression_ratio': 0.0,
            'processing_time_seconds': 0.0,
            'throughput_mbps': 0.0,
            'efficiency_score': 0.0,
            'files_with_hw_accel': 0
        }
        
        self.session_start_time = time.time()
        self.file_metrics: List[FileCompressionMetric] = []
        self.observers: List[AnalyticsObserver] = []
        self._efficiency_weights = {
            'compression_ratio': 0.7,  # 70% weight on compression efficiency
            'processing_speed': 0.3    # 30% weight on processing speed
        }
    
    def add_observer(self, observer: AnalyticsObserver) -> None:
        """
        Add an analytics observer.
        
        Args:
            observer: Observer instance to receive analytics events
        """
        self.observers.append(observer)
        observer.on_session_start()
    
    def remove_observer(self, observer: AnalyticsObserver) -> None:
        """
        Remove an analytics observer.
        
        Args:
            observer: Observer instance to remove
        """
        if observer in self.observers:
            self.observers.remove(observer)
    
    def track_compression(self, original_size: int, compressed_size: int, 
                         processing_time: float, file_path: str,
                         codec_used: str = "unknown", 
                         hardware_acceleration: bool = False,
                         segment_count: int = 1) -> FileCompressionMetric:
        """
        Track comprehensive metrics for a single file compression.
        
        This method calculates all relevant metrics for a compression operation
        and updates session-level statistics. It uses incremental calculation
        to minimize performance impact.
        
        Args:
            original_size: Original file size in bytes
            compressed_size: Compressed file size in bytes
            processing_time: Time taken for compression in seconds
            file_path: Path to the compressed file
            codec_used: Video codec used for compression
            hardware_acceleration: Whether hardware acceleration was used
            segment_count: Number of segments if file was segmented
            
        Returns:
            FileCompressionMetric containing all calculated metrics
        """
        # Calculate basic metrics
        size_reduction = original_size - compressed_size
        compression_ratio = compressed_size / original_size if original_size > 0 else 1.0
        throughput = (original_size / (1024 * 1024)) / max(processing_time, 0.001)  # MB/s
        
        # Calculate efficiency score (0.0 to 1.0, higher is better)
        efficiency_score = self._calculate_efficiency_score(
            compression_ratio, throughput, hardware_acceleration
        )
        
        # Create metric object
        file_metric = FileCompressionMetric(
            file_path=str(file_path),
            original_size=original_size,
            compressed_size=compressed_size,
            size_reduction=size_reduction,
            compression_ratio=compression_ratio,
            processing_time=processing_time,
            throughput_mbps=throughput,
            efficiency_score=efficiency_score,
            timestamp=time.time(),
            codec_used=codec_used,
            hardware_acceleration=hardware_acceleration,
            segment_count=segment_count
        )
        
        # Update session statistics
        self._update_session_stats(file_metric)
        
        # Store metric and notify observers
        self.file_metrics.append(file_metric)
        self._notify_observers_compression_complete(file_metric)
        
        return file_metric
    
    def _calculate_efficiency_score(self, compression_ratio: float, 
                                   throughput: float, hardware_accel: bool) -> float:
        """
        Calculate composite efficiency score.
        
        Combines compression effectiveness with processing speed to provide
        a single metric for overall compression efficiency.
        
        Args:
            compression_ratio: Size ratio (compressed/original)
            throughput: Processing throughput in MB/s
            hardware_accel: Whether hardware acceleration was used
            
        Returns:
            Efficiency score between 0.0 and 1.0 (higher is better)
        """
        # Compression effectiveness (1.0 - ratio, so lower ratios give higher scores)
        compression_effectiveness = max(0.0, min(1.0, 1.0 - compression_ratio))
        
        # Processing speed score (normalized, with diminishing returns)
        # Assume 20 MB/s is excellent throughput for reference
        speed_score = min(1.0, throughput / 20.0)
        
        # Hardware acceleration bonus
        hw_bonus = 0.1 if hardware_accel else 0.0
        
        # Weighted combination
        efficiency = (
            compression_effectiveness * self._efficiency_weights['compression_ratio'] +
            speed_score * self._efficiency_weights['processing_speed'] +
            hw_bonus
        )
        
        return min(1.0, efficiency)  # Cap at 1.0
    
    def _update_session_stats(self, metric: FileCompressionMetric) -> None:
        """Update session-level statistics with new metric."""
        stats = self.compression_stats
        
        # Update counters
        stats['total_files_processed'] += 1
        stats['total_original_size'] += metric.original_size
        stats['total_compressed_size'] += metric.compressed_size
        stats['total_size_reduction'] += metric.size_reduction
        stats['processing_time_seconds'] += metric.processing_time
        
        if metric.hardware_acceleration:
            stats['files_with_hw_accel'] += 1
        
        # Recalculate averages incrementally
        total_files = stats['total_files_processed']
        
        # Average compression ratio
        if self.file_metrics:  # Include current metric
            ratios = [m.compression_ratio for m in self.file_metrics] + [metric.compression_ratio]
            stats['average_compression_ratio'] = statistics.mean(ratios)
        else:
            stats['average_compression_ratio'] = metric.compression_ratio
        
        # Overall session throughput
        session_duration = time.time() - self.session_start_time
        total_size_mb = stats['total_original_size'] / (1024 * 1024)
        stats['throughput_mbps'] = total_size_mb / max(session_duration, 0.001)
        
        # Average efficiency score
        if self.file_metrics:
            efficiency_scores = [m.efficiency_score for m in self.file_metrics] + [metric.efficiency_score]
            stats['efficiency_score'] = statistics.mean(efficiency_scores)
        else:
            stats['efficiency_score'] = metric.efficiency_score
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive analytics summary.
        
        Returns:
            Dictionary containing session statistics, recent files, and analysis
        """
        session_duration = time.time() - self.session_start_time
        
        # Create session analytics object
        session_analytics = SessionAnalytics(
            total_files_processed=self.compression_stats['total_files_processed'],
            total_original_size=self.compression_stats['total_original_size'],
            total_compressed_size=self.compression_stats['total_compressed_size'],
            total_size_reduction=self.compression_stats['total_size_reduction'],
            average_compression_ratio=self.compression_stats['average_compression_ratio'],
            processing_time_seconds=self.compression_stats['processing_time_seconds'],
            throughput_mbps=self.compression_stats['throughput_mbps'],
            efficiency_score=self.compression_stats['efficiency_score'],
            session_duration=session_duration,
            files_with_hw_accel=self.compression_stats['files_with_hw_accel'],
            average_file_size=self._calculate_average_file_size()
        )
        
        return {
            'session_analytics': asdict(session_analytics),
            'stats': self.compression_stats.copy(),
            'recent_files': [asdict(m) for m in self.file_metrics[-5:]] if self.file_metrics else [],
            'session_duration': session_duration,
            'recommendations': self._generate_recommendations()
        }
    
    def _calculate_average_file_size(self) -> float:
        """Calculate average original file size in MB."""
        if not self.file_metrics:
            return 0.0
        
        total_size = sum(m.original_size for m in self.file_metrics)
        return (total_size / len(self.file_metrics)) / (1024 * 1024)
    
    def _generate_recommendations(self) -> List[str]:
        """
        Generate optimization recommendations based on collected metrics.
        
        Returns:
            List of actionable recommendations for improving compression efficiency
        """
        recommendations = []
        
        if not self.file_metrics:
            return ["No compression data available for analysis."]
        
        # Analyze compression ratios
        avg_ratio = self.compression_stats['average_compression_ratio']
        if avg_ratio > 0.8:
            recommendations.append(
                "Consider using a lower CRF value or higher compression preset for better size reduction."
            )
        
        # Analyze throughput
        avg_throughput = self.compression_stats['throughput_mbps']
        if avg_throughput < 5.0:
            recommendations.append(
                "Consider enabling hardware acceleration or using a faster preset to improve processing speed."
            )
        
        # Hardware acceleration analysis
        hw_usage = self.compression_stats['files_with_hw_accel'] / self.compression_stats['total_files_processed']
        if hw_usage < 0.5:
            recommendations.append(
                "Hardware acceleration is underutilized. Check codec and platform compatibility."
            )
        
        # File size analysis
        avg_file_size = self._calculate_average_file_size()
        if avg_file_size > 2000:  # >2GB files
            recommendations.append(
                "Large files detected. Consider using segmentation for improved parallel processing."
            )
        
        # Efficiency analysis
        avg_efficiency = self.compression_stats['efficiency_score']
        if avg_efficiency < 0.6:
            recommendations.append(
                "Overall efficiency is low. Balance compression ratio and processing speed settings."
            )
        
        return recommendations if recommendations else ["Compression performance is optimal."]
    
    def export_metrics(self, format: str = "dict") -> Any:
        """
        Export metrics in various formats for external analysis.
        
        Args:
            format: Export format ("dict", "json", "csv")
            
        Returns:
            Metrics in requested format
        """
        if format == "dict":
            return {
                'session_stats': self.compression_stats,
                'file_metrics': [asdict(m) for m in self.file_metrics]
            }
        elif format == "json":
            import json
            return json.dumps({
                'session_stats': self.compression_stats,
                'file_metrics': [asdict(m) for m in self.file_metrics]
            }, indent=2)
        elif format == "csv":
            # Return CSV-formatted string
            import io
            import csv
            
            output = io.StringIO()
            if self.file_metrics:
                writer = csv.DictWriter(output, fieldnames=asdict(self.file_metrics[0]).keys())
                writer.writeheader()
                for metric in self.file_metrics:
                    writer.writerow(asdict(metric))
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def reset_session(self) -> None:
        """Reset all metrics and start a new session."""
        # Notify observers of session end
        session_analytics = SessionAnalytics(
            total_files_processed=self.compression_stats['total_files_processed'],
            total_original_size=self.compression_stats['total_original_size'], 
            total_compressed_size=self.compression_stats['total_compressed_size'],
            total_size_reduction=self.compression_stats['total_size_reduction'],
            average_compression_ratio=self.compression_stats['average_compression_ratio'],
            processing_time_seconds=self.compression_stats['processing_time_seconds'],
            throughput_mbps=self.compression_stats['throughput_mbps'],
            efficiency_score=self.compression_stats['efficiency_score'],
            session_duration=time.time() - self.session_start_time,
            files_with_hw_accel=self.compression_stats['files_with_hw_accel'],
            average_file_size=self._calculate_average_file_size()
        )
        
        self._notify_observers_session_end(session_analytics)
        
        # Reset all metrics
        self.compression_stats = {
            'total_files_processed': 0,
            'total_original_size': 0,
            'total_compressed_size': 0,
            'total_size_reduction': 0, 
            'average_compression_ratio': 0.0,
            'processing_time_seconds': 0.0,
            'throughput_mbps': 0.0,
            'efficiency_score': 0.0,
            'files_with_hw_accel': 0
        }
        
        self.session_start_time = time.time()
        self.file_metrics.clear()
        
        # Notify observers of new session
        for observer in self.observers:
            observer.on_session_start()
    
    def _notify_observers_compression_complete(self, metric: FileCompressionMetric) -> None:
        """Notify all observers of compression completion."""
        for observer in self.observers:
            try:
                observer.on_compression_complete(metric)
            except Exception as e:
                # Log error but don't interrupt analytics collection
                print(f"Warning: Analytics observer error: {e}")
    
    def _notify_observers_session_end(self, session_analytics: SessionAnalytics) -> None:
        """Notify all observers of session end."""
        for observer in self.observers:
            try:
                observer.on_session_end(session_analytics)
            except Exception as e:
                print(f"Warning: Analytics observer error during session end: {e}")


class LoggingAnalyticsObserver(AnalyticsObserver):
    """
    Analytics observer that logs metrics to file or console.
    
    This observer provides detailed logging of compression metrics
    for debugging and performance analysis purposes.
    """
    
    def __init__(self, log_file: Optional[str] = None, logger=None):
        """
        Initialize logging observer.
        
        Args:
            log_file: Optional file path for metric logging
            logger: Optional logger instance for output
        """
        self.log_file = log_file
        self.logger = logger
    
    def on_compression_complete(self, metric: FileCompressionMetric) -> None:
        """Log completion of file compression."""
        message = (
            f"📊 Compression Complete: {Path(metric.file_path).name} | "
            f"Ratio: {metric.compression_ratio:.3f} | "
            f"Speed: {metric.throughput_mbps:.1f} MB/s | "
            f"Efficiency: {metric.efficiency_score:.3f}"
        )
        self._log_message(message)
    
    def on_session_start(self) -> None:
        """Log session start."""
        self._log_message("🎬 Analytics session started")
    
    def on_session_end(self, session_analytics: SessionAnalytics) -> None:
        """Log session end with summary."""
        message = (
            f"🏁 Session Complete | "
            f"Files: {session_analytics.total_files_processed} | "
            f"Avg Ratio: {session_analytics.average_compression_ratio:.3f} | "
            f"Throughput: {session_analytics.throughput_mbps:.1f} MB/s"
        )
        self._log_message(message)
    
    def _log_message(self, message: str) -> None:
        """Log message to configured output."""
        if self.logger:
            self.logger(message, "INFO")
        elif self.log_file:
            with open(self.log_file, 'a') as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\\n")
        else:
            print(message)