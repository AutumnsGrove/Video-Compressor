# Video Compressor Configuration Reference

This document provides detailed explanations for all configuration settings in `config.json`. The configuration file controls every aspect of the video compression process, from codec settings to safety checks and large file handling.

## Quick Navigation

- [FFmpeg Settings](#ffmpeg-settings)
- [Compression Settings](#compression-settings)
- [Safety Settings](#safety-settings)
- [Large File Settings](#large-file-settings)
- [Segmentation Settings](#segmentation-settings)
- [Parallel Processing Settings](#parallel-processing-settings)
- [Logging Settings](#logging-settings)
- [Complete Example Config](#complete-example-config)

---

## FFmpeg Settings

### `ffmpeg_path`
**Type:** String  
**Default:** `"/opt/homebrew/bin/ffmpeg"`  
**Description:** Full path to the FFmpeg executable on your system.

**Common Values:**
- macOS (Homebrew): `/opt/homebrew/bin/ffmpeg`
- macOS (MacPorts): `/opt/local/bin/ffmpeg`
- Linux: `/usr/bin/ffmpeg`
- Windows: `C:\\ffmpeg\\bin\\ffmpeg.exe`

### `temp_dir`
**Type:** String  
**Default:** `"/tmp/video_compression"`  
**Description:** Directory for temporary files during compression. Only used when `use_same_filesystem` is false.

**Tips:**
- Choose a location with plenty of free space
- SSD storage recommended for better performance
- Will be overridden by `use_same_filesystem: true`

### `log_dir`
**Type:** String  
**Default:** `"./logs"`  
**Description:** Directory where compression logs are stored.

---

## Compression Settings

### `target_bitrate_reduction`
**Type:** Float (0.0 - 1.0)  
**Default:** `0.5`  
**Description:** Target bitrate as a fraction of original. Only applies to software encoding.

**Examples:**
- `0.5` = 50% of original bitrate
- `0.3` = 30% of original bitrate (more aggressive)
- `0.7` = 70% of original bitrate (more conservative)

### `preserve_10bit`
**Type:** Boolean  
**Default:** `true`  
**Description:** Maintain 10-bit color depth when present in source video.

**Impact:**
- `true`: Better quality for HDR/10-bit content, larger file sizes
- `false`: Convert to 8-bit, smaller files but quality loss on 10-bit sources

### `preserve_metadata`
**Type:** Boolean  
**Default:** `true`  
**Description:** Copy metadata from original file (creation date, camera info, etc.).

### `video_codec`
**Type:** String  
**Default:** `"libx265"`  
**Description:** Video codec for compression.

**Options:**
- `"libx265"`: H.265/HEVC - best compression, slower encoding
- `"libx264"`: H.264 - faster encoding, larger files
- Hardware acceleration will override this when available

### `preset`
**Type:** String  
**Default:** `"medium"`  
**Description:** Encoding speed/quality tradeoff for software encoding.

**Options (fastest to slowest):**
- `"ultrafast"`: Fastest encoding, largest files
- `"superfast"`: Very fast encoding
- `"veryfast"`: Fast encoding
- `"faster"`: Faster than medium
- `"fast"`: Fast encoding
- `"medium"`: Balanced (recommended)
- `"slow"`: Better compression
- `"slower"`: Even better compression
- `"veryslow"`: Best compression, very slow

### `crf`
**Type:** Integer (0-51)  
**Default:** `23`  
**Description:** Constant Rate Factor - quality setting for software encoding.

**Scale:**
- `0`: Lossless (huge files)
- `18`: Visually lossless (very large files)
- `23`: High quality (recommended)
- `28`: Medium quality
- `35`: Low quality (small files)
- `51`: Worst quality (tiny files)

### `enable_hardware_acceleration`
**Type:** Boolean  
**Default:** `true`  
**Description:** Use hardware encoders when available (VideoToolbox on Apple Silicon).

**Benefits:**
- Much faster encoding
- Lower CPU usage
- May produce different file sizes than software encoding

---

## Safety Settings

### `min_free_space_gb`
**Type:** Integer  
**Default:** `15`  
**Description:** Minimum free disk space required before starting compression (in GB).

**Recommendations:**
- At least 10GB for small files
- 50GB+ for 4K/large file processing
- Consider your largest video file size × 3

### `verify_integrity`
**Type:** Boolean  
**Default:** `true`  
**Description:** Run comprehensive integrity checks on compressed files.

**When enabled, performs:**
- Video metadata analysis
- Stream validation
- Playability testing (beginning, middle, end)
- Comparison with original file

### `create_backup_hash`
**Type:** Boolean  
**Default:** `true`  
**Description:** Calculate SHA-256 hash of original file for verification.

**Note:** Adds processing time but ensures file integrity.

### `max_retries`
**Type:** Integer  
**Default:** `3`  
**Description:** Maximum retry attempts for failed operations.

### `delete_original_after_compression`
**Type:** Boolean  
**Default:** `true`  
**Description:** Whether to delete original files after successful compression and verification.

**Safety considerations:**
- `true`: Saves disk space, standard behavior for compression tools
- `false`: Preserves originals for extra safety, requires manual cleanup
- **Recommendation:** Set to `false` for initial testing or irreplaceable files

---

## Large File Settings

### `threshold_gb`
**Type:** Integer  
**Default:** `10`  
**Description:** File size threshold (GB) that triggers enhanced large file processing features.

**Enhanced features include:**
- Extended timeouts
- More frequent progress updates
- Enhanced monitoring
- Optimized memory usage

### `segmentation_threshold_gb`
**Type:** Integer  
**Default:** `10`  
**Description:** File size threshold (GB) for segmentation eligibility. Must also exceed duration threshold.

### `enhanced_monitoring`
**Type:** Boolean  
**Default:** `true`  
**Description:** Enable detailed progress tracking for large files.

### `progress_update_interval`
**Type:** Integer  
**Default:** `10`  
**Description:** Progress update frequency in seconds for large files.

### `hash_chunk_size_mb`
**Type:** Integer  
**Default:** `5`  
**Description:** Chunk size (MB) for hash calculation on large files.

**Performance impact:**
- Smaller chunks: More frequent progress updates, slightly slower
- Larger chunks: Less frequent updates, faster processing

### `extended_timeouts`
**Type:** Boolean  
**Default:** `true`  
**Description:** Use longer timeouts for large file operations.

### `use_same_filesystem`
**Type:** Boolean  
**Default:** `true`  
**Description:** Create temporary files on same filesystem as source file.

**Benefits:**
- Faster file operations (no cross-filesystem copying)
- Avoids space issues on different drives
- **Recommended:** Keep this `true`

### `ui_callback_interval_seconds`
**Type:** Float  
**Default:** `0.5`  
**Description:** Minimum time interval (seconds) between UI progress updates to prevent callback spam.

**Recommendations:**
- `0.1` - Very responsive UI, may cause performance overhead
- `0.5` - Good balance of responsiveness and performance (recommended)
- `1.0` - Less frequent updates, lower overhead
- `2.0` - Minimal updates, best for slow systems

**Note:** This prevents excessive UI updates during rapid progress changes while maintaining responsive feedback.

---

## Segmentation Settings

Large files can be split into segments, compressed individually, then merged back together for better memory management and parallel processing.

### `segment_duration_seconds`
**Type:** Integer  
**Default:** `600` (10 minutes)  
**Description:** Duration of each segment in seconds.

**Considerations:**
- Shorter segments: More parallel processing, more overhead
- Longer segments: Less overhead, less parallelization
- 5-15 minutes (300-900 seconds) is usually optimal

### `duration_threshold_minutes`
**Type:** Integer  
**Default:** `15`  
**Description:** Minimum video duration (minutes) required for segmentation eligibility.

**Segmentation Logic:**
Files are segmented ONLY if:
1. File size > `segmentation_threshold_gb` AND
2. Duration > `duration_threshold_minutes`

### `segmentation_timeout_minutes_per_gb`
**Type:** Float  
**Default:** `1`  
**Description:** Additional timeout per GB of file size for segmentation operations.

### `min_segmentation_timeout_minutes`
**Type:** Integer  
**Default:** `5`  
**Description:** Minimum timeout for segmentation operations regardless of file size.

### `size_difference_warning_percent`
**Type:** Integer  
**Default:** `5`  
**Description:** Warning threshold for size differences during segmentation (%).

**Triggers warning if:**
Total segments size differs from original by more than this percentage.

### `merge_size_difference_warning_percent`
**Type:** Integer  
**Default:** `10`  
**Description:** Warning threshold for size differences during segment merging (%).

---

## Parallel Processing Settings

### `enabled`
**Type:** Boolean  
**Default:** `true`  
**Description:** Enable parallel processing of multiple files.

### `max_workers`
**Type:** Integer  
**Default:** `4`  
**Description:** Maximum number of simultaneous compression workers.

**Recommendations:**
- CPU cores - 1 (leave one core free)
- Consider memory usage (each worker uses RAM)
- Monitor system performance and adjust

### `max_workers_limit`
**Type:** Integer  
**Default:** `16`  
**Description:** Hard limit on worker count regardless of system specs.

### `segment_parallel`
**Type:** Boolean  
**Default:** `true`  
**Description:** Enable parallel processing of segments within large files.

### `small_file_timeout_hours`
**Type:** Integer  
**Default:** `2`  
**Description:** Timeout for small file compression operations (hours).

### `segment_timeout_hours`
**Type:** Integer  
**Default:** `1`  
**Description:** Timeout for individual segment compression (hours).

---

## Logging Settings

### `max_log_files`
**Type:** Integer  
**Default:** `5`  
**Description:** Maximum number of log files to keep (older files are deleted).

### `max_log_size_mb`
**Type:** Integer  
**Default:** `10`  
**Description:** Maximum size of each log file in MB before rotation.

### `console_level`
**Type:** String  
**Default:** `"INFO"`  
**Description:** Minimum log level displayed in console.

**Levels (least to most verbose):**
- `"CRITICAL"`: Only critical errors
- `"ERROR"`: Errors and critical issues
- `"WARNING"`: Warnings, errors, and critical issues
- `"INFO"`: General information (recommended)
- `"DEBUG"`: Detailed debugging information

### `file_level`
**Type:** String  
**Default:** `"DEBUG"`  
**Description:** Minimum log level written to log files.

**Recommendation:** Keep at `"DEBUG"` for troubleshooting.

---

## Complete Example Config

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
    "crf": 23,
    "enable_hardware_acceleration": true
  },
  "safety_settings": {
    "min_free_space_gb": 15,
    "verify_integrity": true,
    "create_backup_hash": true,
    "max_retries": 3,
    "delete_original_after_compression": true
  },
  "large_file_settings": {
    "threshold_gb": 10,
    "segmentation_threshold_gb": 10,
    "enhanced_monitoring": true,
    "progress_update_interval": 10,
    "hash_chunk_size_mb": 5,
    "extended_timeouts": true,
    "use_same_filesystem": true,
    "ui_callback_interval_seconds": 0.5
  },
  "logging_settings": {
    "max_log_files": 5,
    "max_log_size_mb": 10,
    "console_level": "INFO",
    "file_level": "DEBUG"
  },
  "parallel_processing": {
    "enabled": true,
    "max_workers": 4,
    "max_workers_limit": 16,
    "segment_parallel": true,
    "small_file_timeout_hours": 2,
    "segment_timeout_hours": 1
  },
  "segmentation_settings": {
    "segment_duration_seconds": 600,
    "duration_threshold_minutes": 15,
    "segmentation_timeout_minutes_per_gb": 1,
    "min_segmentation_timeout_minutes": 5,
    "size_difference_warning_percent": 5,
    "merge_size_difference_warning_percent": 10
  }
}
```

---

## Configuration Tips

### For Fast Processing
```json
"compression_settings": {
  "preset": "faster",
  "crf": 28,
  "enable_hardware_acceleration": true
}
```

### For Maximum Quality
```json
"compression_settings": {
  "preset": "slower",
  "crf": 18,
  "preserve_10bit": true
}
```

### For Maximum Compression
```json
"compression_settings": {
  "preset": "veryslow",
  "crf": 28,
  "target_bitrate_reduction": 0.3
}
```

### For Large File Processing
```json
"segmentation_settings": {
  "duration_threshold_minutes": 10,
  "segment_duration_seconds": 300
},
"parallel_processing": {
  "max_workers": 6,
  "segment_parallel": true
}
```

### For Safe Testing/Valuable Files
```json
"safety_settings": {
  "delete_original_after_compression": false,
  "verify_integrity": true,
  "create_backup_hash": true
}
```

---

## Troubleshooting Config Issues

**Problem:** "Config setting not found" errors  
**Solution:** Ensure all settings in this document exist in your config.json

**Problem:** Slow processing  
**Solution:** Increase `max_workers`, use `"faster"` preset, enable hardware acceleration

**Problem:** Large files failing  
**Solution:** Increase `min_free_space_gb`, enable segmentation, check `extended_timeouts`

**Problem:** Poor quality output  
**Solution:** Lower `crf` value, use `"slower"` preset, enable `preserve_10bit`

**Problem:** Large output files  
**Solution:** Lower `target_bitrate_reduction`, increase `crf` value

---

For more help, check the main documentation or examine the logs in your configured `log_dir`.