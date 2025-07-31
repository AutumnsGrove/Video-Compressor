#!/usr/bin/env python3

import os
import sys
import json
import subprocess
import shutil
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import argparse

class VideoCompressor:
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.log_file = None
        self.setup_logging()
        self.processed_files = []
        self.failed_files = []
        
    def load_config(self, config_path):
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            print(f"Config file {config_path} not found. Creating default config...")
            default_config = {
                "ffmpeg_path": "/opt/homebrew/bin/ffmpeg",
                "temp_dir": "/tmp/video_compression",
                "log_dir": "./logs",
                "compression_settings": {
                    "target_bitrate_reduction": 0.5,
                    "preserve_10bit": True,
                    "preserve_metadata": True,
                    "video_codec": "libx265",
                    "preset": "medium",
                    "crf": 23
                },
                "safety_settings": {
                    "min_free_space_gb": 10,
                    "verify_integrity": True,
                    "create_backup_hash": True,
                    "max_retries": 3
                }
            }
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
        except json.JSONDecodeError as e:
            print(f"Error parsing config file: {e}")
            sys.exit(1)
    
    def setup_logging(self):
        """Setup comprehensive logging system."""
        log_dir = Path(self.config["log_dir"])
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"video_compression_{timestamp}.log"
        
        self.log_file = open(log_file, 'w')
        self.log(f"=== Video Compression Session Started ===")
        self.log(f"Timestamp: {datetime.now()}")
        self.log(f"Config: {json.dumps(self.config, indent=2)}")
        
    def log(self, message, level="INFO"):
        """Log message to both console and file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        if self.log_file:
            self.log_file.write(log_message + "\n")
            self.log_file.flush()
    
    def check_disk_space(self, file_path, safety_multiplier=2.5):
        """Check if there's enough disk space for safe compression."""
        file_size = os.path.getsize(file_path)
        temp_dir = Path(self.config["temp_dir"])
        
        # Get available space on temp directory filesystem
        statvfs = os.statvfs(temp_dir.parent)
        available_bytes = statvfs.f_frsize * statvfs.f_bavail
        available_gb = available_bytes / (1024**3)
        
        # Required space: original file size * safety multiplier
        required_bytes = file_size * safety_multiplier
        required_gb = required_bytes / (1024**3)
        
        min_free_space = self.config["safety_settings"]["min_free_space_gb"]
        
        self.log(f"Disk space check:")
        self.log(f"  Available: {available_gb:.2f}GB")
        self.log(f"  Required: {required_gb:.2f}GB")
        self.log(f"  File size: {file_size / (1024**3):.2f}GB")
        self.log(f"  Min free space: {min_free_space}GB")
        
        if available_gb < (required_gb + min_free_space):
            return False, f"Insufficient disk space. Need {required_gb + min_free_space:.2f}GB, have {available_gb:.2f}GB"
        
        return True, "Sufficient disk space available"
    
    def calculate_file_hash(self, file_path, chunk_size=8192):
        """Calculate SHA-256 hash of file for integrity verification."""
        self.log(f"Calculating hash for {file_path}")
        hash_sha256 = hashlib.sha256()
        
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            self.log(f"Error calculating hash: {e}", "ERROR")
            return None
    
    def get_video_info(self, file_path):
        """Get detailed video information using ffprobe."""
        cmd = [
            self.config["ffmpeg_path"].replace("ffmpeg", "ffprobe"),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                self.log(f"ffprobe error: {result.stderr}", "ERROR")
                return None
        except Exception as e:
            self.log(f"Error getting video info: {e}", "ERROR")
            return None
    
    def verify_file_integrity(self, file_path):
        """Verify file can be opened and basic properties match expectations."""
        self.log(f"Verifying integrity of {file_path}")
        
        # Check if file exists and has reasonable size
        if not os.path.exists(file_path):
            return False, "File does not exist"
        
        file_size = os.path.getsize(file_path)
        if file_size < 1024:  # Less than 1KB is suspicious
            return False, f"File too small: {file_size} bytes"
        
        # Try to get video info
        video_info = self.get_video_info(file_path)
        if not video_info:
            return False, "Cannot read video information"
        
        # Check if video has streams
        streams = video_info.get("streams", [])
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        
        if not video_streams:
            return False, "No video streams found"
        
        # Basic playability test - try to decode first few seconds
        cmd = [
            self.config["ffmpeg_path"],
            "-v", "error",
            "-i", file_path,
            "-t", "5",  # Test first 5 seconds
            "-f", "null",
            "-"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                return False, f"Playback test failed: {result.stderr}"
        except Exception as e:
            return False, f"Playback test error: {e}"
        
        return True, "File verification successful"
    
    def estimate_compression_time(self, file_path):
        """Estimate compression time based on file size and system performance."""
        file_size_gb = os.path.getsize(file_path) / (1024**3)
        
        # Rough estimates: ~1GB per 10-20 minutes depending on settings
        # These are conservative estimates
        if self.config["compression_settings"]["preset"] == "ultrafast":
            minutes_per_gb = 5
        elif self.config["compression_settings"]["preset"] == "fast":
            minutes_per_gb = 8
        elif self.config["compression_settings"]["preset"] == "medium":
            minutes_per_gb = 15
        elif self.config["compression_settings"]["preset"] == "slow":
            minutes_per_gb = 25
        else:
            minutes_per_gb = 15
        
        estimated_minutes = file_size_gb * minutes_per_gb
        return timedelta(minutes=estimated_minutes)
    
    def compress_video(self, input_path, output_path, dry_run=False):
        """Compress video file with safety checks."""
        self.log(f"{'[DRY RUN] ' if dry_run else ''}Starting compression: {input_path}")
        
        if dry_run:
            self.log("[DRY RUN] Would compress with settings:")
            compression_settings = self.config["compression_settings"]
            for key, value in compression_settings.items():
                self.log(f"[DRY RUN]   {key}: {value}")
            return True, "Dry run completed"
        
        # Get original video info
        original_info = self.get_video_info(input_path)
        if not original_info:
            return False, "Cannot read original video information"
        
        # Build ffmpeg command
        cmd = self.build_ffmpeg_command(input_path, output_path, original_info)
        
        self.log(f"FFmpeg command: {' '.join(cmd)}")
        
        # Start compression with progress monitoring
        start_time = time.time()
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Monitor progress
            for line in process.stdout:
                if "time=" in line:
                    # Extract time information for progress
                    self.log(f"Progress: {line.strip()}")
            
            process.wait()
            
            if process.returncode != 0:
                return False, f"FFmpeg failed with return code {process.returncode}"
            
            end_time = time.time()
            duration = timedelta(seconds=int(end_time - start_time))
            self.log(f"Compression completed in {duration}")
            
            return True, "Compression successful"
            
        except Exception as e:
            return False, f"Compression error: {e}"
    
    def build_ffmpeg_command(self, input_path, output_path, original_info):
        """Build FFmpeg command based on configuration and video properties."""
        cmd = [self.config["ffmpeg_path"], "-y", "-i", input_path]
        
        settings = self.config["compression_settings"]
        
        # Video codec settings
        cmd.extend(["-c:v", settings["video_codec"]])
        cmd.extend(["-preset", settings["preset"]])
        cmd.extend(["-crf", str(settings["crf"])])
        
        # Preserve 10-bit if specified
        if settings["preserve_10bit"]:
            # Check if original is 10-bit
            video_stream = next((s for s in original_info["streams"] if s["codec_type"] == "video"), None)
            if video_stream and "pix_fmt" in video_stream:
                if "10" in video_stream["pix_fmt"]:
                    cmd.extend(["-pix_fmt", "yuv420p10le"])
        
        # Audio - copy without reencoding to preserve quality
        cmd.extend(["-c:a", "copy"])
        
        # Preserve metadata
        if settings["preserve_metadata"]:
            cmd.extend(["-map_metadata", "0"])
            cmd.extend(["-movflags", "+faststart"])
        
        # Calculate target bitrate if specified
        if "target_bitrate_reduction" in settings:
            original_bitrate = self.get_original_bitrate(original_info)
            if original_bitrate:
                target_bitrate = int(original_bitrate * settings["target_bitrate_reduction"])
                cmd.extend(["-b:v", f"{target_bitrate}k"])
                self.log(f"Target bitrate: {target_bitrate}k (reduced from {original_bitrate}k)")
        
        cmd.append(output_path)
        return cmd
    
    def get_original_bitrate(self, video_info):
        """Extract original video bitrate from video info."""
        try:
            video_stream = next((s for s in video_info["streams"] if s["codec_type"] == "video"), None)
            if video_stream and "bit_rate" in video_stream:
                return int(video_stream["bit_rate"]) // 1000  # Convert to kbps
            
            # Fallback: calculate from format
            format_info = video_info.get("format", {})
            if "bit_rate" in format_info and "duration" in format_info:
                total_bitrate = int(format_info["bit_rate"]) // 1000
                # Assume ~10% is audio, rest is video (rough estimate)
                return int(total_bitrate * 0.9)
        except:
            pass
        return None
    
    def process_file(self, file_path, dry_run=False):
        """Process a single file with full safety protocol."""
        file_path = Path(file_path)
        self.log(f"\n{'='*50}")
        self.log(f"Processing: {file_path.name}")
        self.log(f"Full path: {file_path}")
        
        # Safety checks
        if not file_path.exists():
            error = f"File does not exist: {file_path}"
            self.log(error, "ERROR")
            return False, error
        
        # Check disk space
        space_ok, space_msg = self.check_disk_space(file_path)
        if not space_ok:
            self.log(space_msg, "ERROR")
            return False, space_msg
        
        # Create temp directory
        temp_dir = Path(self.config["temp_dir"])
        temp_dir.mkdir(exist_ok=True)
        
        # Generate temporary output path
        output_name = f"{file_path.stem}_compressed{file_path.suffix}"
        temp_output = temp_dir / output_name
        
        if dry_run:
            self.log(f"[DRY RUN] Would create: {temp_output}")
            estimated_time = self.estimate_compression_time(file_path)
            self.log(f"[DRY RUN] Estimated compression time: {estimated_time}")
            return True, "Dry run successful"
        
        # Step 1: Create original file hash for verification
        if self.config["safety_settings"]["create_backup_hash"]:
            original_hash = self.calculate_file_hash(file_path)
            if not original_hash:
                return False, "Failed to calculate original file hash"
        
        # Step 2: Compress to temporary location
        self.log("Step 1: Compressing video...")
        success, message = self.compress_video(file_path, temp_output, dry_run)
        if not success:
            self.cleanup_temp_files(temp_output)
            return False, f"Compression failed: {message}"
        
        # Step 3: Verify compressed file integrity
        self.log("Step 2: Verifying compressed file...")
        if self.config["safety_settings"]["verify_integrity"]:
            integrity_ok, integrity_msg = self.verify_file_integrity(temp_output)
            if not integrity_ok:
                self.cleanup_temp_files(temp_output)
                return False, f"Compressed file verification failed: {integrity_msg}"
        
        # Step 4: Compare file sizes and show compression results
        original_size = file_path.stat().st_size
        compressed_size = temp_output.stat().st_size
        compression_ratio = compressed_size / original_size
        space_saved = original_size - compressed_size
        
        self.log(f"Compression results:")
        self.log(f"  Original size: {original_size / (1024**3):.2f}GB")
        self.log(f"  Compressed size: {compressed_size / (1024**3):.2f}GB")
        self.log(f"  Compression ratio: {compression_ratio:.2%}")
        self.log(f"  Space saved: {space_saved / (1024**3):.2f}GB")
        
        # Step 5: Move compressed file to final location (same directory as original)
        final_output = file_path.parent / output_name
        self.log(f"Step 3: Moving to final location: {final_output}")
        
        try:
            shutil.move(str(temp_output), str(final_output))
        except Exception as e:
            self.cleanup_temp_files(temp_output)
            return False, f"Failed to move compressed file: {e}"
        
        # Step 6: Final verification of moved file
        self.log("Step 4: Final verification...")
        final_integrity_ok, final_integrity_msg = self.verify_file_integrity(final_output)
        if not final_integrity_ok:
            self.log(f"Final verification failed: {final_integrity_msg}", "ERROR")
            # Don't delete original - something went wrong
            return False, f"Final verification failed: {final_integrity_msg}"
        
        # Step 7: ONLY NOW delete original file
        self.log("Step 5: Deleting original file...")
        try:
            file_path.unlink()
            self.log(f"Original file deleted: {file_path}")
        except Exception as e:
            self.log(f"Failed to delete original file: {e}", "ERROR")
            return False, f"Failed to delete original file: {e}"
        
        # Step 8: Log success
        self.log(f"✅ SUCCESS: {file_path.name} compressed successfully")
        self.log(f"   New file: {final_output}")
        self.log(f"   Space saved: {space_saved / (1024**3):.2f}GB")
        
        return True, f"File processed successfully. Saved {space_saved / (1024**3):.2f}GB"
    
    def cleanup_temp_files(self, *temp_files):
        """Clean up temporary files."""
        for temp_file in temp_files:
            try:
                if temp_file and Path(temp_file).exists():
                    Path(temp_file).unlink()
                    self.log(f"Cleaned up temp file: {temp_file}")
            except Exception as e:
                self.log(f"Failed to clean up {temp_file}: {e}", "WARNING")
    
    def process_file_list(self, file_list, dry_run=False):
        """Process a list of files with comprehensive reporting."""
        self.log(f"\n{'='*60}")
        self.log(f"BATCH PROCESSING {'(DRY RUN)' if dry_run else ''}")
        self.log(f"Files to process: {len(file_list)}")
        
        # Estimate total time
        total_estimated_time = timedelta()
        total_original_size = 0
        
        for file_path in file_list:
            if Path(file_path).exists():
                size = os.path.getsize(file_path)
                total_original_size += size
                if not dry_run:
                    estimated_time = self.estimate_compression_time(file_path)
                    total_estimated_time += estimated_time
        
        self.log(f"Total data to process: {total_original_size / (1024**3):.2f}GB")
        if not dry_run:
            self.log(f"Estimated total time: {total_estimated_time}")
            estimated_completion = datetime.now() + total_estimated_time
            self.log(f"Estimated completion: {estimated_completion.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Process each file
        start_time = time.time()
        total_space_saved = 0
        
        for i, file_path in enumerate(file_list, 1):
            self.log(f"\n[{i}/{len(file_list)}] Processing: {Path(file_path).name}")
            
            original_size = 0
            if Path(file_path).exists():
                original_size = os.path.getsize(file_path)
            
            success, message = self.process_file(file_path, dry_run)
            
            if success:
                self.processed_files.append(file_path)
                if not dry_run and Path(file_path).parent.exists():
                    # Calculate space saved
                    compressed_files = list(Path(file_path).parent.glob(f"{Path(file_path).stem}_compressed*"))
                    if compressed_files:
                        compressed_size = compressed_files[0].stat().st_size
                        space_saved = original_size - compressed_size
                        total_space_saved += space_saved
            else:
                self.failed_files.append((file_path, message))
                self.log(f"❌ FAILED: {message}", "ERROR")
                
                # Ask user if they want to continue on failure
                if not dry_run:
                    response = input("\nFile processing failed. Continue with remaining files? (y/n): ")
                    if response.lower() != 'y':
                        self.log("User chose to stop processing.", "INFO")
                        break
        
        # Final summary
        end_time = time.time()
        total_time = timedelta(seconds=int(end_time - start_time))
        
        self.log(f"\n{'='*60}")
        self.log(f"BATCH PROCESSING COMPLETE {'(DRY RUN)' if dry_run else ''}")
        self.log(f"Total time: {total_time}")
        self.log(f"Successfully processed: {len(self.processed_files)}")
        self.log(f"Failed: {len(self.failed_files)}")
        
        if not dry_run and total_space_saved > 0:
            self.log(f"Total space saved: {total_space_saved / (1024**3):.2f}GB")
        
        if self.failed_files:
            self.log(f"\nFailed files:")
            for file_path, error in self.failed_files:
                self.log(f"  - {file_path}: {error}")
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        if self.log_file:
            self.log("=== Video Compression Session Ended ===")
            self.log_file.close()


def main():
    parser = argparse.ArgumentParser(description="Safe Video Compression Tool")
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--files", help="Text file containing video file paths (one per line)")
    parser.add_argument("--dry-run", action="store_true", help="Preview operations without executing")
    parser.add_argument("--single", help="Process a single video file")
    parser.add_argument("files_list", nargs="*", help="Video files to process")
    
    args = parser.parse_args()
    
    # Create compressor instance
    compressor = VideoCompressor(args.config)
    
    # Collect files to process
    files_to_process = []
    
    if args.single:
        files_to_process = [args.single]
    elif args.files:
        # Read from file
        try:
            with open(args.files, 'r') as f:
                files_to_process = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"File list not found: {args.files}")
            sys.exit(1)
    elif args.files_list:
        files_to_process = args.files_list
    else:
        print("No files specified. Use --files, --single, or provide file paths as arguments.")
        parser.print_help()
        sys.exit(1)
    
    if not files_to_process:
        print("No files to process.")
        sys.exit(1)
    
    # Safety prompt for non-dry-run operations
    if not args.dry_run:
        print(f"\n⚠️  VIDEO COMPRESSION SAFETY WARNING ⚠️")
        print(f"You are about to compress {len(files_to_process)} video files.")
        print(f"This will:")
        print(f"1. Create compressed copies of your videos")
        print(f"2. Verify the compressed files work correctly") 
        print(f"3. DELETE the original files after verification")
        print(f"")
        print(f"Make sure you have backups of important files!")
        print(f"")
        response = input("Are you sure you want to continue? Type 'YES' to proceed: ")
        
        if response != "YES":
            print("Operation cancelled.")
            sys.exit(0)
    
    # Process files
    compressor.process_file_list(files_to_process, args.dry_run)
    
    print(f"\nProcessing complete. Check the log file for detailed information.")


if __name__ == "__main__":
    main()