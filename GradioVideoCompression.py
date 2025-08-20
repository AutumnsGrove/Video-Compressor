#!/usr/bin/env python3

import os
import json
import gradio as gr
from pathlib import Path
from VideoCompression import VideoCompressor, ParallelVideoProcessor
import tempfile

def create_interface():
    """Create Gradio interface for video compression."""
    
    def load_config_for_ui():
        """Load config for UI display."""
        try:
            with open("config.json", 'r') as f:
                config = json.load(f)
            return config
        except:
            return {}
    
    def test_ffmpeg_connection():
        """Test FFmpeg installation and hardware acceleration."""
        try:
            compressor = ParallelVideoProcessor()
            ffmpeg_path = compressor.config["ffmpeg_path"]
            
            # Test ffmpeg
            import subprocess
            result = subprocess.run([ffmpeg_path, "-version"], 
                                    capture_output=True, text=True, timeout=10)
            
            output = ""
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                output += f"✅ **FFmpeg Connection Successful!**\n\n**Path:** {ffmpeg_path}\n**Version:** {version_line}\n"
                
                # Test hardware acceleration
                output += "\n## 🚀 Hardware Acceleration Test\n\n"
                hw_accel = compressor.detect_hardware_acceleration()
                
                if hw_accel:
                    output += f"✅ **VideoToolbox Hardware Acceleration Available!**\n\n"
                    output += f"**Type:** {hw_accel['type']}\n"
                    output += f"**H.264 Encoder:** {hw_accel['h264_encoder']}\n"
                    if hw_accel['hevc_encoder']:
                        output += f"**HEVC Encoder:** {hw_accel['hevc_encoder']}\n"
                    else:
                        output += f"**HEVC Encoder:** ❌ Not available\n"
                    output += f"**Quality Parameter:** {hw_accel['quality_param']}\n"
                    output += f"**10-bit Format:** {hw_accel['pixel_format_10bit']}\n"
                    output += f"\n**Status:** 🚀 Hardware acceleration will be used automatically when available\n"
                else:
                    import platform
                    processor = platform.processor().lower()
                    machine = platform.machine().lower()
                    is_apple_silicon = "arm" in processor or "arm64" in machine
                    
                    if is_apple_silicon:
                        output += f"⚠️ **Apple Silicon detected but VideoToolbox not available**\n\n"
                        output += f"**Processor:** {processor}\n"
                        output += f"**Machine:** {machine}\n"
                        output += f"**Status:** Will fall back to software encoding\n"
                    else:
                        output += f"ℹ️ **Software encoding will be used**\n\n"
                        output += f"**Processor:** {processor}\n"
                        output += f"**Machine:** {machine}\n"
                        output += f"**Reason:** Not Apple Silicon or hardware acceleration disabled\n"
                
                # Check configuration
                enable_hw = compressor.config.get("compression_settings", {}).get("enable_hardware_acceleration", True)
                output += f"\n**Hardware Acceleration Config:** {'✅ Enabled' if enable_hw else '❌ Disabled'}\n"
                
                output += f"\n**Overall Status:** Ready for compression"
                return output
            else:
                return f"❌ **FFmpeg Test Failed**\n\n**Path:** {ffmpeg_path}\n**Error:** {result.stderr}"
                
        except Exception as e:
            return f"❌ **FFmpeg Test Error**\n\n**Error:** {str(e)}"
    
    def parse_file_paths(input_text):
        """Parse file paths from input text, handling both space-separated and line-separated formats."""
        if not input_text or not input_text.strip():
            return []
        
        # Clean input text
        input_text = input_text.strip()
        
        # First, try to split by newlines (original format)
        lines = [line.strip() for line in input_text.split('\n') if line.strip()]
        
        # If we have multiple lines, return them as is
        if len(lines) > 1:
            return lines
        
        # If we only have one line, check if it contains multiple paths
        single_line = lines[0]
        video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.m4v', '.webm', '.flv', '.wmv']
        
        # Count potential file paths by looking for extensions
        extension_count = sum(single_line.lower().count(ext) for ext in video_extensions)
        
        # If only one extension found, treat as single path
        if extension_count <= 1:
            return [single_line]
        
        # Multiple extensions found - try to parse space-separated paths
        # Use shlex to properly handle quoted paths with spaces
        import shlex
        try:
            paths = shlex.split(single_line)
            # Filter to only include paths that look like video files
            video_paths = [path for path in paths if any(path.lower().endswith(ext) for ext in video_extensions)]
            return video_paths if video_paths else [single_line]
        except ValueError:
            # If shlex fails, fall back to simple space splitting
            parts = single_line.split()
            paths = []
            current_path = ""
            
            for part in parts:
                if current_path:
                    current_path += " " + part
                else:
                    current_path = part
                
                # Check if this looks like a complete path (ends with video extension)
                if any(current_path.lower().endswith(ext) for ext in video_extensions):
                    paths.append(current_path)
                    current_path = ""
            
            # Add any remaining path
            if current_path:
                paths.append(current_path)
            
            return paths if paths else [single_line]
    
    def process_videos_ui(file_paths_input, video_files, dry_run, 
                         target_bitrate_reduction, preserve_10bit, preserve_metadata,
                         video_codec, preset, crf, enable_hardware_acceleration, min_free_space_gb, 
                         delete_original, progress=gr.Progress()):
        """Process videos through UI."""
        
        try:
            # Create temporary config with UI settings
            config = load_config_for_ui()
            config["compression_settings"]["target_bitrate_reduction"] = target_bitrate_reduction
            config["compression_settings"]["preserve_10bit"] = preserve_10bit
            config["compression_settings"]["preserve_metadata"] = preserve_metadata
            config["compression_settings"]["video_codec"] = video_codec
            config["compression_settings"]["preset"] = preset
            config["compression_settings"]["crf"] = int(crf)
            config["compression_settings"]["enable_hardware_acceleration"] = enable_hardware_acceleration
            config["safety_settings"]["min_free_space_gb"] = min_free_space_gb
            config["safety_settings"]["delete_original_after_compression"] = delete_original
            
            # Save temporary config
            temp_config_path = "temp_config.json"
            with open(temp_config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Create parallel compressor with temporary config for enhanced progress tracking
            compressor = ParallelVideoProcessor(temp_config_path)
            
            # Collect files to process
            files_to_process = []
            
            # Handle file paths input
            if file_paths_input and file_paths_input.strip():
                progress(0.1, desc="Parsing file paths...")
                file_paths = parse_file_paths(file_paths_input)
                
                # Validate files exist and convert to strings
                missing_files = []
                for file_path in file_paths:
                    # Ensure path is a string
                    file_path_str = str(file_path).strip()
                    if os.path.exists(file_path_str):
                        files_to_process.append(file_path_str)
                    else:
                        missing_files.append(file_path_str)
                
                if missing_files:
                    return f"❌ Files not found:\n" + "\n".join(f"- {path}" for path in missing_files)
            
            # Handle uploaded files
            elif video_files and len(video_files) > 0:
                progress(0.1, desc="Processing uploaded files...")
                # Ensure uploaded file paths are strings
                files_to_process = [str(video_file.name) for video_file in video_files]
            
            if not files_to_process:
                return "No files provided. Please upload files or provide file paths."
            
            # Process files with progress tracking
            progress(0.1, desc=f"Analyzing {len(files_to_process)} files...")
            
            # Capture output
            output_lines = []
            
            class UILogger:
                def __init__(self):
                    self.lines = []
                    self.important_lines = []
                
                def log(self, message, level="INFO"):
                    formatted_msg = f"[{level}] {message}"
                    self.lines.append(formatted_msg)
                    output_lines.append(formatted_msg)
                    
                    # Keep track of important messages for summary
                    if level in ["WARNING", "ERROR", "CRITICAL"] or "Progress:" in message:
                        self.important_lines.append(formatted_msg)
            
            # Override compressor logging for UI
            ui_logger = UILogger()
            original_log = compressor.log
            compressor.log = ui_logger.log
            
            # Create enhanced batch progress callback
            def batch_progress_callback(progress_data):
                # Handle both old-style callbacks and new enhanced progress data
                if isinstance(progress_data, dict):
                    # New enhanced progress data from ProgressAggregator
                    overall_progress = progress_data.get('overall_progress', 0.0)
                    active_workers = progress_data.get('active_workers', 0)
                    total_workers = progress_data.get('total_workers', 0)
                    throughput_mbps = progress_data.get('throughput_mbps', 0.0)
                    eta_seconds = progress_data.get('eta_seconds', 0)
                    
                    # Create enhanced status message
                    if active_workers > 0:
                        if eta_seconds > 0:
                            eta_str = f"{int(eta_seconds//3600):02d}:{int((eta_seconds%3600)//60):02d}:{int(eta_seconds%60):02d}"
                            status_message = f"Processing: {active_workers}/{total_workers} workers active | {throughput_mbps:.1f}MB/s | ETA: {eta_str}"
                        else:
                            status_message = f"Processing: {active_workers}/{total_workers} workers active | {throughput_mbps:.1f}MB/s"
                    else:
                        status_message = f"Processing complete | Total throughput: {throughput_mbps:.1f}MB/s"
                    
                    # Map overall progress to 0.2 -> 0.95 range 
                    mapped_progress = 0.2 + (overall_progress * 0.75)
                    progress(mapped_progress, desc=status_message)
                    
                else:
                    # Handle old-style callback (for backwards compatibility)
                    overall_progress = progress_data if isinstance(progress_data, (int, float)) else 0.0
                    mapped_progress = 0.2 + (overall_progress * 0.75)
                    progress(mapped_progress, desc="Processing files...")
            
            try:
                # Process all files using batch processing with progress
                compressor.process_file_list(files_to_process, dry_run, batch_progress_callback)
                
                progress(1.0, desc="Processing complete!")
                
                # Generate enhanced summary with file analysis for dry runs
                large_files = [f for f in files_to_process if os.path.exists(f) and os.path.getsize(f) > 10*1024**3]
                
                summary = f"""
# 🎬 Video Compression Results

**Files Processed:** {len(files_to_process)} {'🔥 (' + str(len(large_files)) + ' large files >10GB)' if large_files else ''}
**Mode:** {'🧪 Dry Run' if dry_run else '⚡ Live Processing'}
**Success:** ✅ {len(compressor.processed_files)}
**Failed:** ❌ {len(compressor.failed_files)}

## ⚙️ Settings Used:
- **Bitrate Reduction:** {target_bitrate_reduction*100}%
- **Codec:** {video_codec}
- **Preset:** {preset}
- **CRF:** {crf}
- **Hardware Acceleration:** {'🚀 Enabled' if enable_hardware_acceleration else '❌ Disabled'}
- **Preserve 10-bit:** {'✅' if preserve_10bit else '❌'}
- **Preserve Metadata:** {'✅' if preserve_metadata else '❌'}

## 🚀 Parallel Processing Info:
- **Parallel Processing:** {'✅ Enabled' if compressor.parallel_enabled else '❌ Disabled'}
- **Max Concurrent Jobs:** {compressor.max_concurrent_jobs}
- **Segment Parallel:** {'✅ Enabled' if compressor.segment_parallel else '❌ Disabled'}
"""
                
                # Add file-by-file analysis for dry runs
                if dry_run and len(files_to_process) <= 5:  # Show detailed analysis for up to 5 files
                    summary += "\n## 📊 File Size Analysis:\n"
                    for file_path in files_to_process:
                        if os.path.exists(file_path):
                            try:
                                # Get video info and analyze
                                video_info = compressor.get_video_info(file_path)
                                if video_info:
                                    breakdown = compressor.analyze_file_size_breakdown(file_path, video_info)
                                    if breakdown:
                                        file_name = os.path.basename(file_path)
                                        file_size_gb = os.path.getsize(file_path) / (1024**3)
                                        
                                        summary += f"\n### 📁 {file_name}\n"
                                        summary += f"- **Size:** {file_size_gb:.2f}GB | **Duration:** {breakdown['duration_formatted']}\n"
                                        
                                        if breakdown['total_bitrate_kbps']:
                                            summary += f"- **Bitrate:** {breakdown['total_bitrate_kbps']//1000:.1f}Mbps\n"
                                        
                                        # Only show contribution if we have real data
                                        if breakdown['video_contribution'] is not None:
                                            summary += f"- **Contribution:** 📹 Video {breakdown['video_contribution']:.1f}% | 🔊 Audio {breakdown['audio_contribution']:.1f}% | 📦 Other {breakdown['other_contribution']:.1f}%\n"
                                        else:
                                            summary += f"- **Contribution:** No bitrate data available\n"
                                        
                                        # Show what's driving file size
                                        size_drivers = []
                                        for detail in breakdown['details']:
                                            if detail['size_factors']:
                                                stream_type = "📹" if detail['type'] == 'video' else "🔊"
                                                size_drivers.extend([f"{stream_type} {factor}" for factor in detail['size_factors']])
                                        
                                        if size_drivers:
                                            summary += f"- **Size Drivers:** {', '.join(size_drivers[:3])}{'...' if len(size_drivers) > 3 else ''}\n"
                                        
                                        # Show compression estimate - only if reliable
                                        if breakdown['total_bitrate_kbps'] and breakdown['total_bitrate_kbps'] > 0:
                                            target_reduction = target_bitrate_reduction
                                            crf_factor = max(0.3, 1.0 - (crf - 18) * 0.05)  # Account for quality settings
                                            realistic_reduction = target_reduction * crf_factor
                                            
                                            estimated_new_bitrate = breakdown['total_bitrate_kbps'] * realistic_reduction
                                            estimated_new_size = (estimated_new_bitrate * breakdown['duration_seconds']) / 8 / 1024 / 1024  # GB
                                            potential_savings = file_size_gb - estimated_new_size
                                            savings_percent = (potential_savings / file_size_gb) * 100
                                            
                                            # Only show if estimate seems reasonable
                                            if 10 <= savings_percent <= 95:
                                                summary += f"- **Estimated Result:** {estimated_new_size:.2f}GB (Save {potential_savings:.2f}GB / {savings_percent:.1f}%)\n"
                                            else:
                                                summary += f"- **Estimated Result:** Unable to calculate reliable estimate\n"
                                        else:
                                            summary += f"- **Estimated Result:** No bitrate data for estimation\n"
                            except Exception as e:
                                summary += f"\n### ❌ {os.path.basename(file_path)}\n- Error analyzing: {str(e)}\n"
                elif dry_run and len(files_to_process) > 5:
                    summary += f"\n## 📊 Batch Analysis:\n*File-by-file analysis available for batches of 5 or fewer files*\n"
                
                summary += "\n## 📋 Processing Details:\n"
                
                # Show important messages first, then recent activity
                important_msgs = ui_logger.important_lines[-20:] if hasattr(ui_logger, 'important_lines') else []
                recent_msgs = output_lines[-30:]
                
                if important_msgs:
                    summary += "\n### 🎯 Key Messages:\n"
                    summary += "\n".join(important_msgs)
                    summary += "\n\n### 📋 Recent Activity:\n"
                
                summary += "\n".join(recent_msgs)
                
                return summary
                
            finally:
                # Restore original logging
                compressor.log = original_log
                # Clean up temp config
                if os.path.exists(temp_config_path):
                    os.remove(temp_config_path)
                
        except Exception as e:
            # Enhanced error reporting with log file reference
            error_msg = f"❌ **Processing Error**\n\n**Error Type:** {type(e).__name__}\n**Details:** {str(e)}"
            
            # Show the most recent log file for debugging
            try:
                log_dir = Path("./logs")
                if log_dir.exists():
                    log_files = sorted(log_dir.glob("video_compression_*.log"), key=lambda x: x.stat().st_mtime)
                    if log_files:
                        latest_log = log_files[-1]
                        error_msg += f"\n\n📄 **Check detailed log:** `{latest_log}`"
                        
                        # Try to read the last few lines of the log for immediate context
                        try:
                            with open(latest_log, 'r') as f:
                                lines = f.readlines()
                                if lines:
                                    recent_lines = lines[-10:]  # Last 10 lines
                                    error_msg += "\n\n🔍 **Recent log entries:**\n```\n"
                                    error_msg += "".join(recent_lines)
                                    error_msg += "\n```"
                        except:
                            pass
            except:
                pass
            
            # Add troubleshooting hints for common large file issues
            if "disk space" in str(e).lower() or "no space left" in str(e).lower():
                error_msg += "\n\n💡 **Tip:** Large files require significant temporary space. The system now uses same-filesystem temp directories to avoid cross-drive issues."
            elif "timeout" in str(e).lower():
                error_msg += "\n\n💡 **Tip:** Large files may require extended processing time. This is normal for files >10GB."
            elif "memory" in str(e).lower():
                error_msg += "\n\n💡 **Tip:** Very large files may hit system memory limits. Try processing files individually."
            elif "cross-device" in str(e).lower() or "filesystem" in str(e).lower():
                error_msg += "\n\n💡 **Tip:** Cross-filesystem issue detected. The system should now create temp files on the same drive as your video."
            elif "permission" in str(e).lower():
                error_msg += "\n\n💡 **Tip:** Permission denied. Check that you have write access to the video file directory."
            
            return error_msg
    
    # Load default config for UI
    default_config = load_config_for_ui()
    compression_settings = default_config.get("compression_settings", {})
    safety_settings = default_config.get("safety_settings", {})
    
    with gr.Blocks(theme=gr.themes.Base(), title="Safe Video Compression Tool") as interface:
        gr.Markdown("# 🎬 Safe Video Compression Tool")
        gr.Markdown("Safely compress large video files while preserving quality and metadata with comprehensive safety checks.")
        
        with gr.Row():
            with gr.Column(scale=2):
                with gr.Tabs():
                    with gr.TabItem("📁 File Paths"):
                        file_paths_input = gr.Textbox(
                            label="Video File Paths",
                            lines=8,
                            placeholder="Paste file paths here:\n\nOne per line:\n/path/to/video1.mp4\n/path/to/video2.mov\n\nOr space-separated:\n/path/to/video1.mp4 /path/to/video2.mov /path/to/video3.mkv",
                            info="Enter full paths to your video files (supports both line-separated and space-separated formats)"
                        )
                    
                    with gr.TabItem("📤 Upload Files"):
                        video_input = gr.File(
                            file_types=["video"],
                            label="Upload Video Files",
                            file_count="multiple",
                            height=200
                        )
            
            with gr.Column(scale=1):
                dry_run = gr.Checkbox(
                    value=True, 
                    label="🧪 Dry Run Mode",
                    info="Preview operations without actually processing files"
                )
                
                gr.Markdown("### ⚠️ Safety Features")
                gr.Markdown("""
                - **Configurable file deletion** - Choose to preserve or delete originals
                - **Enhanced disk space checking** with cross-filesystem support  
                - **Comprehensive file integrity verification** after compression
                - **Structured logging** with automatic cleanup and rotation
                - **Large file optimization** (>10GB) with extended timeouts
                - **Progress monitoring** with ETA calculations
                - **Rollback capability** if anything fails
                """)
        
        with gr.Accordion("🎛️ Compression Settings", open=True):
            with gr.Row():
                target_bitrate_reduction = gr.Slider(
                    minimum=0.1, maximum=0.9, value=compression_settings.get("target_bitrate_reduction", 0.5),
                    label="Bitrate Reduction",
                    info="Target reduction (0.5 = 50% smaller files)"
                )
                
                crf = gr.Slider(
                    minimum=15, maximum=35, value=compression_settings.get("crf", 23), step=1,
                    label="CRF Quality",
                    info="Lower = better quality, higher file size (18-28 recommended)"
                )
            
            with gr.Row():
                video_codec = gr.Dropdown(
                    choices=["libx265", "libx264", "libvpx-vp9"],
                    value=compression_settings.get("video_codec", "libx265"),
                    label="Video Codec",
                    info="libx265 recommended for best compression"
                )
                
                preset = gr.Dropdown(
                    choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
                    value=compression_settings.get("preset", "medium"),
                    label="Encoding Preset",
                    info="Slower = better compression (medium recommended)"
                )
            
            with gr.Row():
                enable_hardware_acceleration = gr.Checkbox(
                    value=compression_settings.get("enable_hardware_acceleration", True),
                    label="🚀 Hardware Acceleration",
                    info="Use VideoToolbox on Apple Silicon (automatically detected)"
                )
                
                preserve_10bit = gr.Checkbox(
                    value=compression_settings.get("preserve_10bit", True),
                    label="Preserve 10-bit Color",
                    info="Maintain 10-bit color science"
                )
                
                preserve_metadata = gr.Checkbox(
                    value=compression_settings.get("preserve_metadata", True),
                    label="Preserve Metadata",
                    info="Keep all video metadata and thumbnails"
                )
        
        with gr.Accordion("🛡️ Safety Settings", open=False):
            min_free_space_gb = gr.Slider(
                minimum=1, maximum=50, value=safety_settings.get("min_free_space_gb", 10),
                label="Minimum Free Space (GB)",
                info="Required free space before processing"
            )
            
            delete_original = gr.Checkbox(
                value=safety_settings.get("delete_original_after_compression", True),
                label="🗑️ Delete Original Files",
                info="Delete original files after successful compression (CAUTION: Disable to preserve originals)"
            )
            
            # Test FFmpeg connection
            with gr.Row():
                test_ffmpeg_btn = gr.Button("🔧 Test FFmpeg Connection", variant="secondary")
            
            test_output = gr.Markdown(
                label="FFmpeg Test Results",
                value="",
                visible=False
            )
        
        with gr.Row():
            process_btn = gr.Button("🚀 Process Videos", variant="primary", size="lg")
        
        # Results
        with gr.Accordion("📊 Processing Results", open=True):
            results_output = gr.Textbox(
                label="Processing Output",
                lines=25,
                max_lines=50,
                show_copy_button=True,
                placeholder="Processing results will appear here..."
            )
        
        # Test FFmpeg function
        def test_ffmpeg_and_show_result():
            message = test_ffmpeg_connection()
            return {
                test_output: gr.Markdown(value=message, visible=True)
            }
        
        test_ffmpeg_btn.click(
            fn=test_ffmpeg_and_show_result,
            outputs=[test_output]
        )
        
        # Process videos function
        process_btn.click(
            fn=process_videos_ui,
            inputs=[
                file_paths_input, video_input, dry_run,
                target_bitrate_reduction, preserve_10bit, preserve_metadata,
                video_codec, preset, crf, enable_hardware_acceleration, min_free_space_gb,
                delete_original
            ],
            outputs=[results_output]
        )
        
        gr.Markdown("""
        ### 📋 Usage Instructions:
        
        1. **Test Setup**: Click "Test FFmpeg Connection" to verify your system is ready
        2. **Add Files**: Either upload files or paste file paths  
        3. **Configure Settings**: Adjust compression settings as needed
        4. **Dry Run First**: Always test with dry run mode enabled initially
        5. **Process**: Run actual compression after verifying dry run results
        
        ### 🧪 Enhanced Dry Run Analysis:
        
        - **File Size Breakdown**: Shows what percentage is video, audio, and container overhead
        - **Size Driver Detection**: Identifies factors making files large (4K resolution, high bitrate, 10-bit color, etc.)
        - **Compression Estimates**: Predicts file size reduction and space savings
        - **Stream Analysis**: Detailed codec, resolution, and quality information
        - **Batch Support**: Analyzes up to 5 files individually, summarizes larger batches
        
        ### ⚠️ Important Safety Notes:
        
        - **Always run a dry run first** to preview operations and understand what's driving file size
        - **Ensure you have backups** of important files
        - **Monitor disk space** - compression requires temporary storage
        - **Check the logs** in the results for any issues
        - **Original files are only deleted** after successful verification
        
        ### 🎯 Recommended Settings:
        
        - **Bitrate Reduction**: 0.5 (50% smaller files)
        - **CRF**: 23 for balanced quality/size, 20 for higher quality
        - **Codec**: libx265 for best compression efficiency  
        - **Preset**: medium for good balance of speed/compression
        
        ### 🔥 Large File Support (>10GB):
        
        - **Enhanced Progress Monitoring**: Real-time FPS, size, and ETA
        - **Extended Timeouts**: Automatic scaling based on file size
        - **Optimized Hashing**: 5MB chunks for faster verification
        - **Memory Management**: Prevents queue overflow during processing
        - **Detailed Analysis**: Comprehensive breakdown of what makes large files so large
        """)
    
    return interface


def main():
    """Launch the Gradio interface."""
    interface = create_interface()
    interface.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get('GRADIO_SERVER_PORT', 7863)),
        share=False,
        show_error=True
    )


if __name__ == "__main__":
    main()