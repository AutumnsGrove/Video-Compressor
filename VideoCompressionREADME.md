# 🎬 Safe Video Compression Tool

A robust Python tool for safely compressing large video files while preserving quality, metadata, and 10-bit color science. Designed with comprehensive safety protocols to prevent data loss.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install gradio pathlib
```

### 2. Verify FFmpeg Installation
Make sure FFmpeg is installed and update the path in `config.json`:
```bash
# macOS with Homebrew
brew install ffmpeg

# Update config.json with correct path
"/opt/homebrew/bin/ffmpeg"  # or wherever your ffmpeg is located
```

### 3. Test with Dry Run (RECOMMENDED)
```bash
# Test a single file first
python VideoCompression.py --single "/path/to/test/video.mp4" --dry-run

# Test multiple files
python VideoCompression.py --dry-run video1.mp4 video2.mp4
```

### 4. Run Web Interface (EASIEST)
```bash
python GradioVideoCompression.py
```
Then open http://localhost:7869 in your browser.

## 📋 Usage Methods

### Method 1: Web Interface (Recommended)
```bash
python GradioVideoCompression.py
```
- User-friendly web interface
- Real-time progress tracking
- Visual settings configuration
- Built-in safety checks

### Method 2: Command Line
```bash
# Single file
python VideoCompression.py --single "/path/to/video.mp4"

# Multiple files as arguments
python VideoCompression.py video1.mp4 video2.mp4 video3.mp4

# From file list
echo "/path/to/video1.mp4" > files.txt
echo "/path/to/video2.mp4" >> files.txt
python VideoCompression.py --files files.txt

# Always test with dry run first
python VideoCompression.py --dry-run --files files.txt
```

## ⚙️ Configuration

### config.json Settings
```json
{
  "ffmpeg_path": "/opt/homebrew/bin/ffmpeg",
  "temp_dir": "/tmp/video_compression",
  "log_dir": "./logs",
  "compression_settings": {
    "target_bitrate_reduction": 0.5,
    "preserve_10bit": true,
    "preserve_metadata": true,
    "video_codec": "libx265",
    "preset": "medium",
    "crf": 23
  },
  "safety_settings": {
    "min_free_space_gb": 10,
    "verify_integrity": true,
    "create_backup_hash": true,
    "max_retries": 3
  }
}
```

### Key Settings Explained:
- **target_bitrate_reduction**: 0.5 = 50% smaller files
- **crf**: 18-28 range, lower = better quality
- **preset**: ultrafast to veryslow, slower = better compression
- **min_free_space_gb**: Safety buffer for disk space

## 🛡️ Safety Protocol

The tool follows a strict 7-step safety protocol:

1. **Pre-flight Checks**: Verify file exists, check disk space
2. **Hash Calculation**: Create integrity hash of original
3. **Compress to Temp**: Create compressed copy in temp location  
4. **Verify Compressed**: Test playability and metadata
5. **Move to Final**: Move compressed file to target location
6. **Final Verification**: Verify moved file integrity
7. **Delete Original**: Only after ALL verifications pass

### Safety Features:
- ✅ Never deletes original until compressed file is verified
- ✅ Comprehensive disk space checking  
- ✅ File integrity verification at multiple stages
- ✅ Detailed logging of all operations
- ✅ Rollback capability if anything fails
- ✅ User confirmation for destructive operations

## 📊 Expected Results

### Typical Compression Results:
- **Original**: 4GB, 260,000K bitrate
- **Compressed**: 2GB, 130,000K bitrate  
- **Space Saved**: 50% (2GB)
- **Quality Loss**: Minimal with CRF 23

### Processing Time Estimates:
- **Medium preset**: ~15 minutes per GB
- **Fast preset**: ~8 minutes per GB
- **Slow preset**: ~25 minutes per GB

## 🔧 Troubleshooting

### Common Issues:

**"FFmpeg not found"**
```bash
# Find your ffmpeg location
which ffmpeg
# Update config.json with the correct path
```

**"Insufficient disk space"**
- Need ~2.5x original file size in temp space
- Increase min_free_space_gb if needed
- Clean up temp directory: `/tmp/video_compression`

**"Verification failed"**
- Original file may be corrupted
- Try different codec settings
- Check disk space during processing

### Log Files:
Check `./logs/video_compression_YYYYMMDD_HHMMSS.log` for detailed information.

## 📁 File Structure

```
VideoCompression/
├── VideoCompression.py      # Main CLI script
├── GradioVideoCompression.py # Web interface  
├── config.json             # Configuration file
├── logs/                   # Processing logs
│   └── video_compression_*.log
└── VideoCompressionREADME.md # This file
```

## 🎯 Best Practices

### Before Processing:
1. **Always run dry-run first**: `--dry-run` flag
2. **Test on 1-2 files**: Verify settings work
3. **Check available space**: Need 2.5x file size free
4. **Backup important files**: External backup recommended

### During Processing:
- **Monitor progress**: Check logs for issues
- **Don't interrupt**: Let each file complete fully
- **Watch disk space**: Ensure sufficient space throughout

### After Processing:
- **Verify results**: Test compressed files play correctly
- **Check logs**: Review for any warnings or errors
- **Clean up**: Remove temp files if needed

## ⚡ Performance Tips

### For Speed:
- Use "fast" or "veryfast" preset
- Lower CRF value (18-20)
- Use libx264 instead of libx265

### For Quality:
- Use "slow" or "veryslow" preset  
- Higher CRF value (20-23)
- Keep libx265 codec
- Enable 10-bit preservation

### For Overnight Processing:
- Use "medium" preset (balanced)
- CRF 23 (good quality/size ratio)
- Enable all safety checks
- Set up in screen/tmux session

## 🔍 Monitoring Progress

### Command Line:
```bash
# Watch log file in real-time
tail -f logs/video_compression_*.log

# Check progress in another terminal
ls -la /tmp/video_compression/
```

### Web Interface:
- Real-time progress bars
- Live log updates
- File-by-file status

## ⚠️ Important Warnings

1. **ALWAYS TEST FIRST**: Use dry-run mode before processing valuable files
2. **BACKUP IMPORTANT FILES**: Have external backups of irreplaceable content
3. **MONITOR DISK SPACE**: Ensure sufficient space throughout processing
4. **CHECK RESULTS**: Verify compressed files work correctly
5. **READ LOGS**: Review processing logs for any issues

## 🆘 Emergency Recovery

If something goes wrong:

1. **Don't panic**: Original files are only deleted after verification
2. **Check temp directory**: `/tmp/video_compression/` may have copies
3. **Review logs**: Check what step failed
4. **Contact support**: Include log files when seeking help

## 📞 Support

For issues or improvements:
1. Check the logs first: `./logs/video_compression_*.log`
2. Try dry-run mode to diagnose issues
3. Test with a single small file first
4. Include log files when reporting problems

---

**Remember: Safety first! Always test with dry-run mode and verify you have backups before processing important files.**