# Safe Video Compression Tool - Developer Guide

## Project Overview
A robust Python video compression tool designed for safe, high-quality compression of large video files with comprehensive progress tracking, parallel processing, and integrity verification.

## Core Components

### Primary Files
- **VideoCompression.py**: Core compression engine with segmentation, parallel processing, and safety protocols
- **GradioVideoCompression.py**: Web interface for user-friendly operation
- **config.json**: Configuration settings for compression parameters and safety protocols

### Key Classes
- **VideoCompressionProcessor**: Main compression engine
- **ProgressAggregator**: Thread-safe progress tracking with callback throttling
- **Logging System**: Comprehensive logging with file and console output

## Development Guidelines

### Code Quality Standards

#### Type Safety and Error Handling
- **MANDATORY**: All progress callbacks must handle both `dict` and `float` input types
- **MANDATORY**: Use isinstance() checks before performing arithmetic operations on callback parameters
- **MANDATORY**: Add comprehensive error handling with detailed logging
- **MANDATORY**: Use try-catch blocks around all subprocess operations

#### Progress Callback Pattern
```python
def progress_callback_handler(progress_data):
    # Always handle both dict (from ProgressAggregator) and float formats
    if isinstance(progress_data, dict):
        progress_value = progress_data.get('overall_progress', 0.0)
    else:
        progress_value = float(progress_data) if progress_data is not None else 0.0
    
    # Perform calculations with validated float value
    calculated_progress = base_progress + (progress_value * multiplier)
    
    # Ensure progress is within valid range
    calculated_progress = max(0.0, min(1.0, calculated_progress))
    
    if callback:
        callback(calculated_progress)
```

#### Threading and Parallel Processing
- **Use existing parallel processing infrastructure**: `process_segments_parallel()` with automatic fallback
- **Thread safety**: All progress updates must be thread-safe
- **Resource management**: Proper cleanup of threads and subprocess handles
- **Timeout handling**: All subprocess operations must have appropriate timeouts

### Architecture Patterns

#### Segmentation Workflow
1. **Analysis Phase** (0-10%): Video analysis and segmentation decision
2. **Segmentation Phase** (10-25%): Video splitting with progress monitoring
3. **Compression Phase** (25-90%): Parallel segment compression
4. **Merge Phase** (90-100%): Segment reassembly and verification

#### Error Recovery
- **Graceful degradation**: Parallel → Sequential fallback
- **Cleanup protocols**: Temporary file management
- **State preservation**: Progress tracking across failures
- **User feedback**: Clear error messages with actionable solutions

### Testing Requirements

#### Required Test Coverage
- **Unit Tests**: Individual component functionality
- **Integration Tests**: End-to-end compression workflows
- **Parallel Processing Tests**: Multi-threading and resource management
- **Progress Tracking Tests**: Callback handling and UI updates
- **Error Handling Tests**: Failure scenarios and recovery

#### Test Files Structure
```
tests/
├── test_compression.py      # Core compression functionality
├── test_parallel.py         # Parallel processing and threading
├── test_gradio_*.py        # UI and progress tracking
└── run_all_tests.py        # Test suite runner
```

### Configuration Management

#### Development Configuration
```json
{
  "development_settings": {
    "enable_debug_logging": true,
    "preserve_temp_files": true,
    "verbose_progress_logging": true,
    "parallel_processing_enabled": true,
    "max_concurrent_jobs": 4
  },
  "safety_settings": {
    "verify_integrity": true,
    "create_backup_hash": true,
    "min_free_space_gb": 10
  }
}
```

#### Key Configuration Areas
- **FFmpeg Integration**: Path validation and version compatibility
- **Progress Throttling**: Callback frequency and UI update rates
- **Parallel Processing**: Worker limits and fallback conditions
- **Safety Protocols**: Verification and backup strategies

## Common Issues and Solutions

### TypeError in Progress Callbacks
**Issue**: `TypeError: unsupported operand types for *: 'dict' and 'float'`

**Solution**: Always validate progress data type before arithmetic operations:
```python
if isinstance(progress_data, dict):
    progress_value = progress_data.get('overall_progress', 0.0)
else:
    progress_value = float(progress_data) if progress_data is not None else 0.0
```

### Segmentation Failures
**Issue**: FFmpeg segmentation fails with timecode track errors

**Solution**: Use selective stream mapping:
```bash
-map 0:v -map 0:a?  # Video and audio only, exclude data streams
```

### Progress UI Freezing
**Issue**: UI appears stuck during long operations

**Solution**: Implement proper progress flow through all phases with threaded monitoring

### Parallel Processing Not Utilized
**Issue**: CPU cores underutilized during processing

**Solution**: Ensure `process_segments_parallel()` is used instead of sequential loops

## Performance Optimization

### Recommended Settings
- **Development**: `fast` preset, CRF 23, parallel enabled
- **Production**: `medium` preset, CRF 20-23, all safety checks enabled
- **Bulk Processing**: `veryfast` preset, higher CRF values for speed

### Memory Management
- **Large Files**: Automatic segmentation above 10GB threshold
- **Temp Storage**: Same filesystem as source for efficiency
- **Buffer Management**: Appropriate timeouts and resource limits

## Logging and Debugging

### Log Levels
- **DEBUG**: Detailed operation steps and variable states
- **INFO**: Major workflow phases and progress milestones
- **WARNING**: Non-fatal issues and fallback operations
- **ERROR**: Failures requiring user attention or intervention

### Debug Information to Include
- **Progress Values**: Before and after transformations
- **Thread States**: Active workers and completion status
- **File Operations**: Paths, sizes, and verification results
- **Configuration**: Active settings and their sources

## Deployment Considerations

### Environment Setup
- **FFmpeg Version**: 7.1+ recommended for best codec support
- **Python Dependencies**: gradio, pathlib (minimal external dependencies)
- **Disk Space**: 2.5x source file size for safe operation
- **System Resources**: 4+ CPU cores recommended for parallel processing

### Production Deployment
- **Configuration Validation**: Verify all paths and settings
- **Resource Monitoring**: Disk space and CPU utilization
- **Log Rotation**: Prevent log directory growth
- **Safety Protocols**: Enable all verification and backup features

## Future Development

### Planned Enhancements
- **GPU Acceleration**: Hardware-accelerated encoding support
- **Cloud Integration**: Remote storage and processing capabilities
- **Advanced Analytics**: Compression efficiency metrics and reporting
- **API Development**: RESTful API for programmatic access

### Code Quality Improvements
- **Type Hints**: Add comprehensive type annotations
- **Error Recovery**: Enhanced failure handling and retry logic
- **Performance Profiling**: Identify and optimize bottlenecks
- **Documentation**: API documentation and code comments

---

## Important Notes for Claude Code Development

### MANDATORY Requirements
1. **Always** validate progress callback data types before arithmetic operations
2. **Always** use the existing `process_segments_parallel()` function for segment processing
3. **Always** implement proper error handling with detailed logging
4. **Always** ensure thread safety in progress tracking operations
5. **Always** provide fallback mechanisms for critical operations

### Code Review Checklist
- [ ] Progress callbacks handle both dict and float inputs
- [ ] All subprocess operations have appropriate timeouts
- [ ] Error handling includes user-actionable messages
- [ ] Parallel processing used where applicable
- [ ] Thread safety maintained in shared resources
- [ ] Temporary files properly cleaned up
- [ ] Configuration parameters validated

### Testing Protocol
1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Full workflow testing with various file types
3. **Stress Tests**: Large files and resource-constrained environments
4. **UI Tests**: Progress tracking and user interaction flows
5. **Error Tests**: Failure scenarios and recovery mechanisms

This project prioritizes data safety, user experience, and robust error handling. All development should maintain these core principles while implementing new features or optimizations.