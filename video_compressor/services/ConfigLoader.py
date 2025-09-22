#!/usr/bin/env python3
"""
Configuration Loader - Enhanced Configuration Management with Validation

This module provides robust configuration loading with schema validation,
environment variable support, and intelligent defaults. It implements
a comprehensive configuration management system that ensures all settings
are properly validated and provide meaningful error messages for invalid
configurations.

Key features:
- JSON schema validation for configuration files
- Environment variable override support
- Intelligent default configuration generation
- Configuration merging and inheritance
- Validation error reporting with suggestions
- Platform-specific path handling
- Runtime configuration validation

The configuration system supports multiple sources with the following priority:
1. Environment variables (highest priority)
2. Configuration file values
3. Default values (lowest priority)

This allows for flexible deployment scenarios while maintaining configuration
integrity through comprehensive validation.
"""

import os
import sys
import json
import platform
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
import logging

# Schema validation (optional dependency)
try:
    import jsonschema
    SCHEMA_VALIDATION_AVAILABLE = True
except ImportError:
    SCHEMA_VALIDATION_AVAILABLE = False


@dataclass
class ConfigValidationError:
    """Container for configuration validation errors."""
    path: str
    message: str
    suggestion: str
    severity: str = "error"  # error, warning, info


class ConfigurationSchema:
    """
    JSON Schema definition for video compressor configuration.
    
    This class defines the complete schema for validating configuration files,
    ensuring all required fields are present and values are within acceptable ranges.
    """
    
    @staticmethod
    def get_schema() -> Dict[str, Any]:
        """
        Get the JSON schema for configuration validation.
        
        Returns:
            Complete JSON schema dictionary for configuration validation
        """
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["ffmpeg_path"],
            "properties": {
                "ffmpeg_path": {
                    "type": "string",
                    "description": "Path to FFmpeg executable"
                },
                "temp_dir": {
                    "type": "string",
                    "description": "Temporary directory for processing files"
                },
                "log_dir": {
                    "type": "string",
                    "description": "Directory for log files"
                },
                "compression_settings": {
                    "type": "object",
                    "properties": {
                        "target_bitrate_reduction": {
                            "type": "number",
                            "minimum": 0.1,
                            "maximum": 0.9,
                            "description": "Target bitrate reduction ratio"
                        },
                        "preserve_10bit": {"type": "boolean"},
                        "preserve_metadata": {"type": "boolean"},
                        "video_codec": {
                            "type": "string",
                            "enum": ["libx264", "libx265", "libvpx", "libvpx-vp9"],
                            "description": "Video codec for compression"
                        },
                        "preset": {
                            "type": "string", 
                            "enum": ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
                            "description": "FFmpeg encoding preset"
                        },
                        "crf": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 51,
                            "description": "Constant Rate Factor (lower = higher quality)"
                        },
                        "enable_hardware_acceleration": {"type": "boolean"}
                    },
                    "additionalProperties": False
                },
                "safety_settings": {
                    "type": "object",
                    "properties": {
                        "min_free_space_gb": {
                            "type": "number",
                            "minimum": 1,
                            "description": "Minimum free disk space in GB"
                        },
                        "verify_integrity": {"type": "boolean"},
                        "create_backup_hash": {"type": "boolean"},
                        "max_retries": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 10
                        },
                        "delete_original_after_compression": {"type": "boolean"}
                    },
                    "additionalProperties": False
                },
                "large_file_settings": {
                    "type": "object",
                    "properties": {
                        "threshold_gb": {"type": "number", "minimum": 0.1},
                        "segmentation_threshold_gb": {"type": "number", "minimum": 0.5},
                        "enhanced_monitoring": {"type": "boolean"},
                        "progress_update_interval": {"type": "integer", "minimum": 1},
                        "hash_chunk_size_mb": {"type": "number", "minimum": 1},
                        "extended_timeouts": {"type": "boolean"},
                        "use_same_filesystem": {"type": "boolean"},
                        "ui_callback_interval_seconds": {"type": "number", "minimum": 0.1}
                    },
                    "additionalProperties": False
                },
                "segmentation_settings": {
                    "type": "object",
                    "properties": {
                        "segment_duration_seconds": {"type": "integer", "minimum": 60},
                        "duration_threshold_minutes": {"type": "integer", "minimum": 5},
                        "segmentation_timeout_minutes_per_gb": {"type": "number", "minimum": 0.5},
                        "min_segmentation_timeout_minutes": {"type": "integer", "minimum": 1},
                        "size_difference_warning_percent": {"type": "number", "minimum": 1},
                        "merge_size_difference_warning_percent": {"type": "number", "minimum": 1}
                    },
                    "additionalProperties": False
                },
                "logging_settings": {
                    "type": "object", 
                    "properties": {
                        "max_log_files": {"type": "integer", "minimum": 1, "maximum": 100},
                        "max_log_size_mb": {"type": "number", "minimum": 1, "maximum": 1000},
                        "console_level": {
                            "type": "string",
                            "enum": ["DEBUG", "INFO", "WARNING", "ERROR"]
                        },
                        "file_level": {
                            "type": "string", 
                            "enum": ["DEBUG", "INFO", "WARNING", "ERROR"]
                        }
                    },
                    "additionalProperties": False
                },
                "parallel_processing": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "max_workers": {"type": "integer", "minimum": 1, "maximum": 32},
                        "max_workers_limit": {"type": "integer", "minimum": 1, "maximum": 64},
                        "segment_parallel": {"type": "boolean"},
                        "small_file_timeout_hours": {"type": "number", "minimum": 0.5},
                        "segment_timeout_hours": {"type": "number", "minimum": 0.5}
                    },
                    "additionalProperties": False
                }
            },
            "additionalProperties": False
        }


class ConfigurationValidator:
    """
    Configuration validation with detailed error reporting.
    
    This class provides comprehensive validation of configuration files
    using JSON Schema and custom validation rules specific to video
    compression requirements.
    """
    
    def __init__(self):
        """Initialize validator with schema."""
        self.schema = ConfigurationSchema.get_schema()
        self.validation_errors: List[ConfigValidationError] = []
    
    def validate(self, config: Dict[str, Any]) -> List[ConfigValidationError]:
        """
        Validate configuration against schema and custom rules.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        self.validation_errors.clear()
        
        # Schema validation if available
        if SCHEMA_VALIDATION_AVAILABLE:
            self._validate_with_schema(config)
        
        # Custom validation rules
        self._validate_paths(config)
        self._validate_codec_settings(config)
        self._validate_parallel_settings(config)
        self._validate_safety_settings(config)
        
        return self.validation_errors.copy()
    
    def _validate_with_schema(self, config: Dict[str, Any]) -> None:
        """Validate using JSON Schema."""
        try:
            jsonschema.validate(config, self.schema)
        except jsonschema.ValidationError as e:
            self.validation_errors.append(ConfigValidationError(
                path=".".join(str(p) for p in e.absolute_path),
                message=e.message,
                suggestion=self._get_suggestion_for_schema_error(e),
                severity="error"
            ))
    
    def _validate_paths(self, config: Dict[str, Any]) -> None:
        """Validate file paths and directories."""
        # FFmpeg path validation
        ffmpeg_path = config.get("ffmpeg_path", "")
        if ffmpeg_path and not Path(ffmpeg_path).exists():
            self.validation_errors.append(ConfigValidationError(
                path="ffmpeg_path",
                message=f"FFmpeg executable not found at: {ffmpeg_path}",
                suggestion=self._suggest_ffmpeg_path(),
                severity="error"
            ))
        
        # Directory validation
        for dir_key in ["temp_dir", "log_dir"]:
            dir_path = config.get(dir_key, "")
            if dir_path:
                try:
                    Path(dir_path).mkdir(parents=True, exist_ok=True)
                except PermissionError:
                    self.validation_errors.append(ConfigValidationError(
                        path=dir_key,
                        message=f"Cannot create directory: {dir_path} (permission denied)",
                        suggestion=f"Choose a directory with write permissions or run as appropriate user",
                        severity="error"
                    ))
    
    def _validate_codec_settings(self, config: Dict[str, Any]) -> None:
        """Validate codec and compression settings."""
        compression = config.get("compression_settings", {})
        
        # CRF and preset combination validation
        crf = compression.get("crf", 23)
        preset = compression.get("preset", "medium")
        
        if crf < 18 and preset in ["ultrafast", "superfast"]:
            self.validation_errors.append(ConfigValidationError(
                path="compression_settings.crf",
                message=f"CRF {crf} with preset '{preset}' may not provide expected quality improvement",
                suggestion="Consider using 'fast' or 'medium' preset with low CRF values",
                severity="warning"
            ))
    
    def _validate_parallel_settings(self, config: Dict[str, Any]) -> None:
        """Validate parallel processing settings."""
        parallel = config.get("parallel_processing", {})
        max_workers = parallel.get("max_workers", 4)
        
        # Check against CPU count
        import multiprocessing
        cpu_count = multiprocessing.cpu_count()
        
        if max_workers > cpu_count * 2:
            self.validation_errors.append(ConfigValidationError(
                path="parallel_processing.max_workers",
                message=f"max_workers ({max_workers}) significantly exceeds CPU count ({cpu_count})",
                suggestion=f"Consider using {cpu_count} to {cpu_count * 2} workers for optimal performance",
                severity="warning"
            ))
    
    def _validate_safety_settings(self, config: Dict[str, Any]) -> None:
        """Validate safety and threshold settings."""
        safety = config.get("safety_settings", {})
        min_space = safety.get("min_free_space_gb", 15)
        
        if min_space < 5:
            self.validation_errors.append(ConfigValidationError(
                path="safety_settings.min_free_space_gb",
                message=f"Minimum free space ({min_space}GB) is very low",
                suggestion="Consider at least 10GB to prevent disk space issues during compression",
                severity="warning"
            ))
    
    def _suggest_ffmpeg_path(self) -> str:
        """Suggest FFmpeg path based on platform."""
        system = platform.system().lower()
        if system == "darwin":  # macOS
            return "Try: /opt/homebrew/bin/ffmpeg or /usr/local/bin/ffmpeg"
        elif system == "linux":
            return "Try: /usr/bin/ffmpeg or install with: sudo apt install ffmpeg"
        elif system == "windows":
            return "Download FFmpeg from https://ffmpeg.org and add to PATH"
        return "Install FFmpeg and specify correct path"
    
    def _get_suggestion_for_schema_error(self, error: 'jsonschema.ValidationError') -> str:
        """Generate helpful suggestion for schema validation errors."""
        if "enum" in str(error.message):
            return f"Valid values are: {', '.join(error.schema.get('enum', []))}"
        elif "minimum" in str(error.message):
            return f"Value must be at least {error.schema.get('minimum')}"
        elif "maximum" in str(error.message):
            return f"Value must be no more than {error.schema.get('maximum')}"
        return "Check the configuration documentation for valid values"


def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    """
    Load and validate configuration with environment variable support.
    
    This function loads configuration from a JSON file, applies environment
    variable overrides, validates the configuration, and returns a complete
    configuration dictionary with intelligent defaults.
    
    Environment variable format: 
    - VIDEOCOMP_FFMPEG_PATH for ffmpeg_path
    - VIDEOCOMP_COMPRESSION_SETTINGS_CRF for compression_settings.crf
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Validated configuration dictionary
        
    Raises:
        SystemExit: If configuration is invalid and cannot be corrected
    """
    print(f"🔧 Loading configuration from: {config_path}")
    
    # Load base configuration
    try:
        config = _load_config_file(config_path)
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        print("🔧 Creating default configuration...")
        config = _create_default_config(config_path)
    
    # Apply environment variable overrides
    config = _apply_environment_overrides(config)
    
    # Validate configuration
    validator = ConfigurationValidator()
    validation_errors = validator.validate(config)
    
    # Report validation results
    if validation_errors:
        _report_validation_errors(validation_errors)
        
        # Exit on critical errors
        critical_errors = [e for e in validation_errors if e.severity == "error"]
        if critical_errors:
            print("❌ Configuration validation failed with critical errors.")
            sys.exit(1)
    else:
        print("✅ Configuration validation passed")
    
    # Apply platform-specific defaults
    config = _apply_platform_defaults(config)
    
    print(f"🎯 Configuration loaded successfully")
    return config


def _load_config_file(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    if not Path(config_path).exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        print(f"✅ Configuration file loaded: {config_path}")
        return config
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file: {e}")


def _create_default_config(config_path: str) -> Dict[str, Any]:
    """Create default configuration file."""
    default_config = {
        "ffmpeg_path": _detect_ffmpeg_path(),
        "temp_dir": str(Path.cwd() / "temp"),
        "log_dir": str(Path.cwd() / "logs"),
        "compression_settings": {
            "target_bitrate_reduction": 0.5,
            "preserve_10bit": True,
            "preserve_metadata": True,
            "video_codec": "libx265",
            "preset": "medium",
            "crf": 23,
            "enable_hardware_acceleration": True
        },
        "safety_settings": {
            "min_free_space_gb": 15,
            "verify_integrity": True,
            "create_backup_hash": True,
            "max_retries": 3,
            "delete_original_after_compression": False  # Conservative default
        },
        "large_file_settings": {
            "threshold_gb": 2,
            "segmentation_threshold_gb": 2,
            "enhanced_monitoring": True,
            "progress_update_interval": 10,
            "hash_chunk_size_mb": 5,
            "extended_timeouts": True,
            "use_same_filesystem": True,
            "ui_callback_interval_seconds": 0.5
        },
        "segmentation_settings": {
            "segment_duration_seconds": 180,  # 3 minutes
            "duration_threshold_minutes": 3,
            "segmentation_timeout_minutes_per_gb": 1,
            "min_segmentation_timeout_minutes": 5,
            "size_difference_warning_percent": 5,
            "merge_size_difference_warning_percent": 10
        },
        "logging_settings": {
            "max_log_files": 10,
            "max_log_size_mb": 20,
            "console_level": "INFO",
            "file_level": "DEBUG"
        },
        "parallel_processing": {
            "enabled": True,
            "max_workers": min(6, os.cpu_count() or 4),
            "max_workers_limit": 16,
            "segment_parallel": True,
            "small_file_timeout_hours": 2,
            "segment_timeout_hours": 1
        }
    }
    
    # Save default configuration
    try:
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        print(f"✅ Default configuration created: {config_path}")
    except Exception as e:
        print(f"⚠️ Could not save default configuration: {e}")
    
    return default_config


def _detect_ffmpeg_path() -> str:
    """Auto-detect FFmpeg installation path."""
    system = platform.system().lower()
    
    # Common FFmpeg paths by platform
    common_paths = {
        'darwin': [  # macOS
            '/opt/homebrew/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/opt/local/bin/ffmpeg'
        ],
        'linux': [
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/snap/bin/ffmpeg'
        ],
        'windows': [
            'ffmpeg.exe',
            'C:\\ffmpeg\\bin\\ffmpeg.exe',
            'C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe'
        ]
    }
    
    # Check system PATH first
    import shutil
    if shutil.which('ffmpeg'):
        return shutil.which('ffmpeg')
    
    # Check platform-specific paths
    for path in common_paths.get(system, []):
        if Path(path).exists():
            return path
    
    # Fallback
    return 'ffmpeg' if system == 'windows' else '/usr/local/bin/ffmpeg'


def _apply_environment_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply environment variable overrides to configuration."""
    env_prefix = "VIDEOCOMP_"
    
    # Environment variable mapping
    env_mappings = {
        f"{env_prefix}FFMPEG_PATH": "ffmpeg_path",
        f"{env_prefix}TEMP_DIR": "temp_dir", 
        f"{env_prefix}LOG_DIR": "log_dir",
        f"{env_prefix}MAX_WORKERS": "parallel_processing.max_workers",
        f"{env_prefix}CRF": "compression_settings.crf",
        f"{env_prefix}PRESET": "compression_settings.preset",
        f"{env_prefix}HARDWARE_ACCEL": "compression_settings.enable_hardware_acceleration"
    }
    
    for env_var, config_path in env_mappings.items():
        env_value = os.environ.get(env_var)
        if env_value is not None:
            _set_nested_config_value(config, config_path, env_value)
            print(f"🌍 Environment override: {config_path} = {env_value}")
    
    return config


def _set_nested_config_value(config: Dict[str, Any], path: str, value: str) -> None:
    """Set nested configuration value from dot-separated path."""
    keys = path.split('.')
    current = config
    
    # Navigate to parent of target key
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    
    # Set value with type conversion
    final_key = keys[-1]
    if value.lower() in ('true', 'false'):
        current[final_key] = value.lower() == 'true'
    elif value.isdigit():
        current[final_key] = int(value)
    else:
        try:
            current[final_key] = float(value)
        except ValueError:
            current[final_key] = value


def _apply_platform_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply platform-specific configuration defaults."""
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        # Enable hardware acceleration by default on Apple Silicon
        if platform.machine().lower() in ['arm64', 'aarch64']:
            config.setdefault("compression_settings", {})["enable_hardware_acceleration"] = True
    
    elif system == "windows":
        # Use appropriate temp directory
        config["temp_dir"] = config.get("temp_dir", str(Path.home() / "AppData" / "Local" / "Temp" / "video_compression"))
        
    return config


def _report_validation_errors(errors: List[ConfigValidationError]) -> None:
    """Report configuration validation errors with helpful formatting."""
    print("⚠️ Configuration validation issues found:")
    print("-" * 60)
    
    for error in errors:
        severity_icon = "❌" if error.severity == "error" else "⚠️"
        print(f"{severity_icon} {error.severity.upper()}: {error.path}")
        print(f"   {error.message}")
        if error.suggestion:
            print(f"   💡 Suggestion: {error.suggestion}")
        print()


# Utility functions for backward compatibility
def get_compression_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract compression settings from configuration."""
    return config.get("compression_settings", {})


def get_parallel_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract parallel processing settings from configuration."""
    return config.get("parallel_processing", {})