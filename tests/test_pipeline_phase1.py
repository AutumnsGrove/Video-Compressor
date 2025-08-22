#!/usr/bin/env python3
"""
Quick test script to verify Phase 1 pipeline implementation
"""

import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from VideoCompression import ParallelVideoProcessor

def test_pipeline_configuration():
    """Test that pipeline can be configured and instantiated."""
    print("🧪 Testing Pipeline Configuration...")
    
    # Load config
    config_path = str(Path(__file__).parent.parent / "config.json")
    if not Path(config_path).exists():
        print("❌ Config file not found")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Check parallel processing settings
        parallel_config = config.get("parallel_processing", {})
        print(f"   Parallel processing enabled: {parallel_config.get('enabled', False)}")
        print(f"   Max workers: {parallel_config.get('max_workers', 'Not set')}")
        print(f"   Segment parallel: {parallel_config.get('segment_parallel', 'Not set')}")
        
        # Try to instantiate the processor
        processor = ParallelVideoProcessor(config_path)
        print(f"   Processor created successfully")
        print(f"   Parallel enabled: {processor.parallel_enabled}")
        print(f"   Max concurrent jobs: {processor.max_concurrent_jobs}")
        print(f"   Segment parallel: {processor.segment_parallel}")
        
        # Test pipeline decision logic
        large_files = ["test1.mp4", "test2.mp4"]  # Fake files
        pipeline_enabled = (
            processor.segment_parallel and 
            len(large_files) > 1 and 
            processor.max_concurrent_jobs > 1
        )
        
        print(f"   Pipeline would be enabled for 2 large files: {pipeline_enabled}")
        
        print("✅ Pipeline configuration test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Pipeline test failed: {e}")
        return False

if __name__ == "__main__":
    test_pipeline_configuration()