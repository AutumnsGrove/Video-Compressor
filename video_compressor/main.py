#!/usr/bin/env python3
"""
Video Compressor - Main Entry Point

This module serves as the primary entry point for the video compression application.
It provides both command-line and web interface options for video compression.

Usage:
    python -m video_compressor.main [--cli] [files...]
    python video_compressor/main.py [--gradio] [--port 7860]

Examples:
    # Launch Gradio web interface (default)
    python -m video_compressor.main
    
    # Launch on specific port
    python -m video_compressor.main --port 8080
    
    # Command line interface
    python -m video_compressor.main --cli input.mp4 output.mp4
"""

import argparse
import sys
from pathlib import Path

def launch_gradio_interface(port=7860, share=False):
    """Launch the Gradio web interface."""
    try:
        from .ui import GradioInterface
        from .core import CompressionPipeline
        
        print(f"🚀 Launching Video Compressor Web Interface on port {port}...")
        
        # Create compression processor
        processor = CompressionPipeline()
        
        # Create and launch interface
        interface = GradioInterface(processor)
        interface.launch(server_port=port, share=share)
        
    except ImportError as e:
        print(f"❌ Failed to import required modules: {e}")
        print("Please ensure all dependencies are installed.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to launch interface: {e}")
        sys.exit(1)

def run_cli_compression(input_files, output_dir=None):
    """Run command line compression."""
    try:
        from .core import CompressionPipeline
        
        processor = CompressionPipeline()
        
        for input_file in input_files:
            if not Path(input_file).exists():
                print(f"❌ File not found: {input_file}")
                continue
                
            print(f"🎬 Compressing: {input_file}")
            
            # Simple CLI compression (basic implementation)
            # This would be expanded for full CLI functionality
            output_path = Path(input_file).with_suffix('.compressed.mp4')
            
            success, message = processor.compress_single_file(
                input_file, str(output_path)
            )
            
            if success:
                print(f"✅ Compressed successfully: {output_path}")
            else:
                print(f"❌ Compression failed: {message}")
                
    except ImportError as e:
        print(f"❌ Failed to import required modules: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ CLI compression error: {e}")
        sys.exit(1)

def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Video Compressor - High-performance parallel video compression",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Launch web interface
  %(prog)s --port 8080             # Launch on specific port
  %(prog)s --cli video.mp4         # Command line compression
  %(prog)s --share                 # Launch with public sharing
        """
    )
    
    parser.add_argument(
        '--cli', action='store_true',
        help='Run in command line mode instead of web interface'
    )
    parser.add_argument(
        '--port', type=int, default=7860,
        help='Port for web interface (default: 7860)'
    )
    parser.add_argument(
        '--share', action='store_true',
        help='Create shareable public link for web interface'
    )
    parser.add_argument(
        'files', nargs='*',
        help='Video files to compress (CLI mode only)'
    )
    
    args = parser.parse_args()
    
    # Print header
    print("🎬 Video Compressor v2.0.0")
    print("=" * 50)
    
    if args.cli:
        if not args.files:
            parser.error("CLI mode requires at least one input file")
        run_cli_compression(args.files)
    else:
        launch_gradio_interface(port=args.port, share=args.share)

if __name__ == "__main__":
    main()