#!/usr/bin/env python3

import os
import json
import gradio as gr
from pathlib import Path
from VideoCompression import VideoCompressor
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
        """Test FFmpeg installation."""
        try:
            compressor = VideoCompressor()
            ffmpeg_path = compressor.config["ffmpeg_path"]
            
            # Test ffmpeg
            import subprocess
            result = subprocess.run([ffmpeg_path, "-version"], 
                                    capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                return f"✅ **FFmpeg Connection Successful!**\n\n**Path:** {ffmpeg_path}\n**Version:** {version_line}\n**Status:** Ready for compression"
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
                         video_codec, preset, crf, min_free_space_gb, progress=gr.Progress()):
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
            config["safety_settings"]["min_free_space_gb"] = min_free_space_gb
            
            # Save temporary config
            temp_config_path = "temp_config.json"
            with open(temp_config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Create compressor with temporary config
            compressor = VideoCompressor(temp_config_path)
            
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
                
                def log(self, message, level="INFO"):
                    self.lines.append(f"[{level}] {message}")
                    output_lines.append(f"[{level}] {message}")
            
            # Override compressor logging for UI
            ui_logger = UILogger()
            original_log = compressor.log
            compressor.log = ui_logger.log
            
            # Create batch progress callback
            def batch_progress_callback(overall_progress, status_message):
                # Map overall progress to 0.2 -> 0.95 range (leaving some room for final steps)
                mapped_progress = 0.2 + (overall_progress * 0.75)
                progress(mapped_progress, desc=status_message)
            
            try:
                # Process all files using batch processing with progress
                compressor.process_file_list(files_to_process, dry_run, batch_progress_callback)
                
                progress(1.0, desc="Processing complete!")
                
                # Generate summary
                summary = f"""
# Video Compression Results

**Files Processed:** {len(files_to_process)}
**Mode:** {'Dry Run' if dry_run else 'Live Processing'}
**Success:** {len(compressor.processed_files)}
**Failed:** {len(compressor.failed_files)}

## Settings Used:
- **Bitrate Reduction:** {target_bitrate_reduction*100}%
- **Codec:** {video_codec}
- **Preset:** {preset}
- **CRF:** {crf}
- **Preserve 10-bit:** {preserve_10bit}
- **Preserve Metadata:** {preserve_metadata}

## Processing Log:
"""
                
                summary += "\n".join(output_lines[-50:])  # Last 50 log lines
                
                return summary
                
            finally:
                # Restore original logging
                compressor.log = original_log
                # Clean up temp config
                if os.path.exists(temp_config_path):
                    os.remove(temp_config_path)
                
        except Exception as e:
            return f"❌ **Processing Error**\n\n{str(e)}"
    
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
                - **Never deletes originals** until compressed file is verified
                - **Disk space checking** before each operation  
                - **File integrity verification** after compression
                - **Comprehensive logging** of all operations
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
                video_codec, preset, crf, min_free_space_gb
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
        
        ### ⚠️ Important Safety Notes:
        
        - **Always run a dry run first** to preview operations
        - **Ensure you have backups** of important files
        - **Monitor disk space** - compression requires temporary storage
        - **Check the logs** in the results for any issues
        - **Original files are only deleted** after successful verification
        
        ### 🎯 Recommended Settings:
        
        - **Bitrate Reduction**: 0.5 (50% smaller files)
        - **CRF**: 23 for balanced quality/size, 20 for higher quality
        - **Codec**: libx265 for best compression efficiency  
        - **Preset**: medium for good balance of speed/compression
        """)
    
    return interface


def main():
    """Launch the Gradio interface."""
    interface = create_interface()
    interface.launch(
        server_name="0.0.0.0",
        server_port=7862,
        share=False,
        show_error=True
    )


if __name__ == "__main__":
    main()