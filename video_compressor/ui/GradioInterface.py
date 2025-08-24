#!/usr/bin/env python3
"""
Gradio Interface - Web-Based User Interface for Video Compression

This module provides a modern, user-friendly web interface for video compression
operations using Gradio. It offers real-time progress tracking, batch processing
capabilities, and comprehensive system monitoring.

Key features:
- Intuitive drag-and-drop file upload
- Real-time compression progress with detailed metrics
- Batch processing with queue management
- System status monitoring (FFmpeg, hardware acceleration)
- Configuration management through UI
- Detailed logging and error reporting
- Mobile-responsive design

The interface is designed to make video compression accessible to users of all
technical levels while providing advanced users with detailed control over
compression parameters and system behavior.
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable
import gradio as gr
import time
import threading

# Import from the new modular structure
from ..core.CompressionPipeline import ParallelVideoProcessor
from ..services.ConfigLoader import load_config
from ..services.LoggingService import setup_enhanced_logging


class GradioVideoInterface:
    """
    Main Gradio interface for video compression operations.
    
    This class provides a comprehensive web interface that integrates all
    aspects of the video compression system including file management,
    progress tracking, system monitoring, and configuration.
    """
    
    def __init__(self, compressor_instance=None):
        """
        Initialize Gradio interface.
        
        Args:
            compressor_instance: Optional pre-configured compressor instance
        """
        # Load configuration and setup components
        self.config = load_config()
        self.logger = setup_enhanced_logging(self.config)
        
        # Initialize compressor
        if compressor_instance:
            self.compressor = compressor_instance
        else:
            self.compressor = ParallelVideoProcessor(config_path="config.json")
        
        # UI state management
        self.current_progress = 0.0
        self.current_status = "Ready"
        self.processing_lock = threading.Lock()
        self.processing_active = False
        
        # Build interface
        self.interface = self._create_interface()
    
    def _create_interface(self) -> gr.Blocks:
        """Create the main Gradio interface."""
        with gr.Blocks(
            title="Video Compressor - High Performance Video Processing",
            theme=gr.themes.Soft(),
            css=self._get_custom_css()
        ) as interface:
            
            # Header
            gr.HTML("""
            <div style="text-align: center; padding: 20px; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; margin-bottom: 20px;">
                <h1>🎬 Video Compressor v2.0</h1>
                <p>High-performance video compression with parallel processing and intelligent optimization</p>
            </div>
            """)
            
            # Main tabs
            with gr.Tabs():
                
                # Compression tab
                with gr.TabItem("🎥 Video Compression", id="compression"):
                    self._create_compression_tab()
                
                # System Status tab  
                with gr.TabItem("🔧 System Status", id="system"):
                    self._create_system_status_tab()
                
                # Configuration tab
                with gr.TabItem("⚙️ Configuration", id="config"):
                    self._create_configuration_tab()
                
                # Analytics tab
                with gr.TabItem("📊 Analytics", id="analytics"):
                    self._create_analytics_tab()
            
            # Footer
            gr.HTML("""
            <div style="text-align: center; padding: 10px; margin-top: 20px; border-top: 1px solid #ddd; color: #666;">
                <small>Powered by FFmpeg • Built with Gradio • Advanced Parallel Processing</small>
            </div>
            """)
        
        return interface
    
    def _create_compression_tab(self) -> None:
        """Create the main compression interface tab."""
        with gr.Row():
            with gr.Column(scale=2):
                
                # File input section
                gr.HTML("<h3>📂 File Selection</h3>")
                
                file_input = gr.File(
                    label="Select Video Files",
                    file_count="multiple",
                    file_types=["video"],
                    height=200
                )
                
                # Alternative text input for file paths
                text_input = gr.Textbox(
                    label="Or enter file paths (one per line)",
                    placeholder="/path/to/video1.mp4\n/path/to/video2.mov",
                    lines=3,
                    info="You can also paste file paths directly"
                )
                
                # Compression settings
                gr.HTML("<h3>🎛️ Compression Settings</h3>")
                
                with gr.Row():
                    preset = gr.Dropdown(
                        choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
                        value=self.config.get("compression_settings", {}).get("preset", "medium"),
                        label="Encoding Preset",
                        info="Speed vs quality tradeoff"
                    )
                    
                    crf = gr.Slider(
                        minimum=0,
                        maximum=51,
                        value=self.config.get("compression_settings", {}).get("crf", 23),
                        step=1,
                        label="Quality (CRF)",
                        info="Lower = higher quality, larger files"
                    )
                
                with gr.Row():
                    codec = gr.Dropdown(
                        choices=["libx264", "libx265", "libvpx", "libvpx-vp9"],
                        value=self.config.get("compression_settings", {}).get("video_codec", "libx265"),
                        label="Video Codec",
                        info="H.264 (x264) for compatibility, H.265 (x265) for efficiency"
                    )
                    
                    hardware_accel = gr.Checkbox(
                        value=self.config.get("compression_settings", {}).get("enable_hardware_acceleration", True),
                        label="Hardware Acceleration",
                        info="Use VideoToolbox on Apple Silicon"
                    )
                
                # Processing controls
                with gr.Row():
                    compress_btn = gr.Button(
                        "🚀 Start Compression",
                        variant="primary",
                        size="lg"
                    )
                    
                    stop_btn = gr.Button(
                        "⏹️ Stop",
                        variant="stop",
                        size="lg"
                    )
            
            with gr.Column(scale=1):
                
                # Progress section
                gr.HTML("<h3>📈 Progress</h3>")
                
                progress_bar = gr.Progress()
                status_text = gr.Textbox(
                    value="Ready to process files",
                    label="Status",
                    interactive=False
                )
                
                # Real-time metrics
                with gr.Row():
                    throughput_display = gr.Textbox(
                        value="0 MB/s",
                        label="Throughput",
                        interactive=False
                    )
                    
                    eta_display = gr.Textbox(
                        value="--:--",
                        label="ETA",
                        interactive=False
                    )
                
                # Worker information
                workers_display = gr.Textbox(
                    value="0/0 workers",
                    label="Active Workers",
                    interactive=False
                )
                
                # Results section
                gr.HTML("<h3>✅ Results</h3>")
                
                results_display = gr.Textbox(
                    value="No files processed yet",
                    label="Compression Results",
                    lines=8,
                    interactive=False
                )
        
        # Event handlers
        compress_btn.click(
            fn=self._start_compression,
            inputs=[file_input, text_input, preset, crf, codec, hardware_accel],
            outputs=[status_text, results_display]
        )
        
        stop_btn.click(
            fn=self._stop_compression,
            outputs=[status_text]
        )
    
    def _create_system_status_tab(self) -> None:
        """Create system status monitoring tab."""
        gr.HTML("<h2>🔧 System Status & Diagnostics</h2>")
        
        # FFmpeg testing section
        with gr.Group():
            gr.HTML("<h3>🎬 FFmpeg Status</h3>")
            
            test_ffmpeg_btn = gr.Button("🧪 Test FFmpeg Connection", variant="secondary")
            ffmpeg_status = gr.Textbox(
                value="Click 'Test FFmpeg Connection' to check status",
                label="FFmpeg Test Results",
                lines=10,
                interactive=False
            )
        
        # Hardware acceleration status
        with gr.Group():
            gr.HTML("<h3>🚀 Hardware Acceleration</h3>")
            
            hw_accel_info = gr.Textbox(
                value="Loading hardware acceleration status...",
                label="Hardware Acceleration Status",
                lines=6,
                interactive=False
            )
        
        # System resources
        with gr.Group():
            gr.HTML("<h3>💾 System Resources</h3>")
            
            with gr.Row():
                cpu_usage = gr.Textbox(
                    value="--",
                    label="CPU Usage",
                    interactive=False
                )
                
                memory_usage = gr.Textbox(
                    value="--",
                    label="Memory Usage",
                    interactive=False
                )
                
                disk_space = gr.Textbox(
                    value="--",
                    label="Available Disk Space",
                    interactive=False
                )
        
        # Update system info on load
        self.interface.load(
            fn=self._get_hardware_status,
            outputs=[hw_accel_info]
        )
        
        # FFmpeg test handler
        test_ffmpeg_btn.click(
            fn=self._test_ffmpeg_connection,
            outputs=[ffmpeg_status]
        )
    
    def _create_configuration_tab(self) -> None:
        """Create configuration management tab."""
        gr.HTML("<h2>⚙️ Configuration Management</h2>")
        
        with gr.Row():
            with gr.Column():
                gr.HTML("<h3>📝 Current Configuration</h3>")
                
                config_display = gr.JSON(
                    value=self.config,
                    label="Configuration Settings",
                    show_label=True
                )
                
                with gr.Row():
                    reload_config_btn = gr.Button("🔄 Reload Configuration")
                    save_config_btn = gr.Button("💾 Save Configuration", variant="primary")
            
            with gr.Column():
                gr.HTML("<h3>🛠️ Quick Settings</h3>")
                
                # Key configuration options
                max_workers = gr.Slider(
                    minimum=1,
                    maximum=16,
                    value=self.config.get("parallel_processing", {}).get("max_workers", 4),
                    step=1,
                    label="Maximum Workers",
                    info="Number of parallel compression workers"
                )
                
                segment_duration = gr.Slider(
                    minimum=60,
                    maximum=600,
                    value=self.config.get("segmentation_settings", {}).get("segment_duration_seconds", 180),
                    step=30,
                    label="Segment Duration (seconds)",
                    info="Duration of segments for large file processing"
                )
                
                min_free_space = gr.Slider(
                    minimum=5,
                    maximum=50,
                    value=self.config.get("safety_settings", {}).get("min_free_space_gb", 15),
                    step=5,
                    label="Minimum Free Space (GB)",
                    info="Required free disk space for safe operation"
                )
                
                # Apply settings button
                apply_settings_btn = gr.Button(
                    "✅ Apply Settings",
                    variant="primary"
                )
        
        # Configuration event handlers
        reload_config_btn.click(
            fn=self._reload_configuration,
            outputs=[config_display]
        )
        
        apply_settings_btn.click(
            fn=self._apply_quick_settings,
            inputs=[max_workers, segment_duration, min_free_space],
            outputs=[config_display]
        )
    
    def _create_analytics_tab(self) -> None:
        """Create analytics and metrics tab."""
        gr.HTML("<h2>📊 Compression Analytics</h2>")
        
        with gr.Row():
            with gr.Column():
                gr.HTML("<h3>📈 Session Statistics</h3>")
                
                analytics_display = gr.JSON(
                    value={"message": "No compression data available yet"},
                    label="Analytics Summary"
                )
                
                refresh_analytics_btn = gr.Button("🔄 Refresh Analytics")
            
            with gr.Column():
                gr.HTML("<h3>💡 Optimization Recommendations</h3>")
                
                recommendations_display = gr.Textbox(
                    value="Complete some compressions to receive optimization recommendations",
                    label="Recommendations",
                    lines=8,
                    interactive=False
                )
        
        # Recent files processed
        with gr.Group():
            gr.HTML("<h3>📄 Recent Files</h3>")
            
            recent_files_display = gr.Dataframe(
                headers=["File", "Original Size", "Compressed Size", "Ratio", "Time", "Throughput"],
                datatype=["str", "str", "str", "str", "str", "str"],
                value=[],
                label="Recent Compressions"
            )
        
        # Analytics event handlers
        refresh_analytics_btn.click(
            fn=self._get_analytics_summary,
            outputs=[analytics_display, recommendations_display, recent_files_display]
        )
    
    def _get_custom_css(self) -> str:
        """Return custom CSS for interface styling."""
        return """
        .gradio-container {
            font-family: 'Segoe UI', system-ui, sans-serif;
        }
        
        .progress-bar {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
        }
        
        .status-success {
            color: #22c55e;
            font-weight: bold;
        }
        
        .status-error {
            color: #ef4444;
            font-weight: bold;
        }
        
        .status-warning {
            color: #f59e0b;
            font-weight: bold;
        }
        
        .metric-card {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 16px;
            margin: 8px;
        }
        """
    
    def _start_compression(self, files, text_input, preset, crf, codec, hardware_accel):
        """Start compression process with UI integration."""
        with self.processing_lock:
            if self.processing_active:
                return "❌ Compression already in progress", "Please wait for current operation to complete"
            
            self.processing_active = True
        
        try:
            # Parse file paths
            file_paths = self._parse_file_inputs(files, text_input)
            
            if not file_paths:
                self.processing_active = False
                return "❌ No valid files selected", "Please select video files to compress"
            
            # Update compression settings
            self._update_compression_settings(preset, crf, codec, hardware_accel)
            
            # Start compression in background thread
            threading.Thread(
                target=self._run_compression_batch,
                args=(file_paths,),
                daemon=True
            ).start()
            
            return f"🚀 Starting compression of {len(file_paths)} files...", "Compression initiated"
            
        except Exception as e:
            self.processing_active = False
            return f"❌ Error starting compression: {str(e)}", str(e)
    
    def _stop_compression(self):
        """Stop compression process."""
        # TODO: Implement proper cancellation mechanism
        self.processing_active = False
        return "⏹️ Stop requested (will complete current file)"
    
    def _parse_file_inputs(self, files, text_input):
        """Parse file inputs from both file upload and text input."""
        file_paths = []
        
        # Process uploaded files
        if files:
            for file in files:
                if hasattr(file, 'name'):
                    file_paths.append(file.name)
                else:
                    file_paths.append(str(file))
        
        # Process text input
        if text_input and text_input.strip():
            text_paths = [line.strip() for line in text_input.strip().split('\n') if line.strip()]
            file_paths.extend(text_paths)
        
        # Validate paths
        valid_paths = []
        for path in file_paths:
            if Path(path).exists():
                valid_paths.append(path)
            else:
                print(f"Warning: File not found: {path}")
        
        return valid_paths
    
    def _update_compression_settings(self, preset, crf, codec, hardware_accel):
        """Update compression settings based on UI inputs."""
        self.compressor.config["compression_settings"].update({
            "preset": preset,
            "crf": crf,
            "video_codec": codec,
            "enable_hardware_acceleration": hardware_accel
        })
    
    def _run_compression_batch(self, file_paths):
        """Run batch compression in background."""
        try:
            for i, file_path in enumerate(file_paths):
                if not self.processing_active:
                    break
                
                # Update progress
                self.current_status = f"Processing {i+1}/{len(file_paths)}: {Path(file_path).name}"
                
                # Run compression
                success, message = self.compressor.compress_video(file_path)
                
                # Log result
                if success:
                    print(f"✅ Completed: {Path(file_path).name}")
                else:
                    print(f"❌ Failed: {Path(file_path).name} - {message}")
            
        except Exception as e:
            print(f"❌ Batch compression error: {e}")
        finally:
            self.processing_active = False
            self.current_status = "Ready"
    
    def _test_ffmpeg_connection(self):
        """Test FFmpeg installation and hardware acceleration."""
        try:
            # Create a temporary compressor for testing
            compressor = ParallelVideoProcessor()
            
            # Test basic FFmpeg functionality
            ffmpeg_path = compressor.config["ffmpeg_path"]
            
            import subprocess
            result = subprocess.run([ffmpeg_path, "-version"], 
                                    capture_output=True, text=True, timeout=10)
            
            output = ""
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                output += f"✅ **FFmpeg Connection Successful!**\\n\\n"
                output += f"**Path:** {ffmpeg_path}\\n"
                output += f"**Version:** {version_line}\\n\\n"
                
                # Test hardware acceleration
                output += "## 🚀 Hardware Acceleration Test\\n\\n"
                hw_accel = compressor.detect_hardware_acceleration()
                
                if hw_accel:
                    output += f"✅ **VideoToolbox Hardware Acceleration Available!**\\n\\n"
                    output += f"**Type:** {hw_accel['type']}\\n"
                    output += f"**H.264 Encoder:** {hw_accel['h264_encoder']}\\n"
                    if hw_accel['hevc_encoder']:
                        output += f"**HEVC Encoder:** {hw_accel['hevc_encoder']}\\n"
                    output += f"**Quality Parameter:** {hw_accel['quality_param']}\\n"
                    output += f"\\n**Status:** 🚀 Hardware acceleration ready for use\\n"
                else:
                    import platform
                    processor = platform.processor().lower()
                    machine = platform.machine().lower()
                    is_apple_silicon = "arm" in processor or "arm64" in machine
                    
                    if is_apple_silicon:
                        output += f"⚠️ **Apple Silicon detected but VideoToolbox not available**\\n"
                        output += f"**Status:** Will use software encoding\\n"
                    else:
                        output += f"ℹ️ **Software encoding will be used**\\n"
                        output += f"**Processor:** {processor}\\n"
                
                return output
            else:
                return f"❌ **FFmpeg Test Failed**\\n\\n**Path:** {ffmpeg_path}\\n**Error:** {result.stderr}"
                
        except Exception as e:
            return f"❌ **FFmpeg Test Error**\\n\\n**Error:** {str(e)}"
    
    def _get_hardware_status(self):
        """Get hardware acceleration status."""
        try:
            hw_accel = self.compressor.detect_hardware_acceleration()
            
            if hw_accel:
                return f"""✅ Hardware Acceleration Available
Type: {hw_accel['type']}
H.264 Encoder: {hw_accel['h264_encoder']}
HEVC Encoder: {hw_accel.get('hevc_encoder', 'Not available')}
Status: Ready for high-performance compression"""
            else:
                return """ℹ️ Software Encoding Mode
Hardware acceleration not available
Will use CPU-based compression
Still provides excellent quality and reasonable speed"""
        except Exception as e:
            return f"❌ Error detecting hardware acceleration: {str(e)}"
    
    def _reload_configuration(self):
        """Reload configuration from file."""
        try:
            self.config = load_config()
            return self.config
        except Exception as e:
            return {"error": f"Failed to reload configuration: {str(e)}"}
    
    def _apply_quick_settings(self, max_workers, segment_duration, min_free_space):
        """Apply quick settings changes."""
        try:
            # Update configuration
            self.config["parallel_processing"]["max_workers"] = max_workers
            self.config["segmentation_settings"]["segment_duration_seconds"] = segment_duration
            self.config["safety_settings"]["min_free_space_gb"] = min_free_space
            
            # Apply to compressor
            self.compressor.config.update(self.config)
            
            return self.config
        except Exception as e:
            return {"error": f"Failed to apply settings: {str(e)}"}
    
    def _get_analytics_summary(self):
        """Get compression analytics summary."""
        try:
            # Get analytics from compressor
            analytics = self.compressor.analytics.get_summary() if hasattr(self.compressor, 'analytics') else {}
            
            # Format recommendations
            recommendations = analytics.get('recommendations', ['No recommendations available'])
            recommendations_text = "\\n".join(f"• {rec}" for rec in recommendations)
            
            # Format recent files
            recent_files = analytics.get('recent_files', [])
            recent_files_data = []
            
            for file_data in recent_files[-10:]:  # Last 10 files
                recent_files_data.append([
                    Path(file_data['file_path']).name,
                    f"{file_data['original_size'] / (1024*1024):.1f} MB",
                    f"{file_data['compressed_size'] / (1024*1024):.1f} MB", 
                    f"{file_data['compression_ratio']:.2f}",
                    f"{file_data['processing_time']:.1f}s",
                    f"{file_data['throughput_mbps']:.1f} MB/s"
                ])
            
            return analytics, recommendations_text, recent_files_data
            
        except Exception as e:
            return {"error": str(e)}, f"Error loading analytics: {str(e)}", []
    
    def launch(self, server_port=7860, share=False):
        """Launch the Gradio interface."""
        return self.interface.launch(
            server_port=server_port,
            share=share,
            show_error=True,
            quiet=False
        )


# Convenience function for backward compatibility
def create_interface():
    """Create and return Gradio interface (backward compatibility)."""
    interface = GradioVideoInterface()
    return interface.interface