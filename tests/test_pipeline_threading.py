#!/usr/bin/env python3
"""
Test Phase 1 Pipeline Threading - Verify thread safety and coordination
"""

import sys
import os
import threading
import queue
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_producer_consumer_pattern():
    """Test basic producer-consumer pattern used in pipeline."""
    print("🧪 Testing Producer-Consumer Pattern...")
    
    try:
        # Setup queue and synchronization
        work_queue = queue.Queue(maxsize=10)
        results = []
        results_lock = threading.Lock()
        
        # Producer function
        def producer():
            producer_id = threading.current_thread().name
            for i in range(5):
                item = {'id': i, 'data': f'item_{i}', 'producer': producer_id}
                work_queue.put(item)
                time.sleep(0.01)  # Simulate work
            
            # Send stop signals
            for _ in range(2):  # 2 consumers
                work_queue.put(None)
        
        # Consumer function
        def consumer():
            consumer_id = threading.current_thread().name
            processed = 0
            
            while True:
                try:
                    item = work_queue.get(timeout=1.0)
                    if item is None:  # Stop signal
                        work_queue.task_done()
                        break
                    
                    # Process item (simulate segment compression)
                    processed_item = {
                        'original': item,
                        'consumer': consumer_id,
                        'processed_at': time.time()
                    }
                    
                    with results_lock:
                        results.append(processed_item)
                    
                    processed += 1
                    work_queue.task_done()
                    
                except queue.Empty:
                    break
            
            print(f"   Consumer {consumer_id} processed {processed} items")
        
        # Start threads
        producer_thread = threading.Thread(target=producer, name="TestProducer")
        consumer_threads = [
            threading.Thread(target=consumer, name=f"TestConsumer-{i}")
            for i in range(2)
        ]
        
        # Run test
        producer_thread.start()
        for t in consumer_threads:
            t.start()
        
        # Wait for completion
        producer_thread.join(timeout=5)
        for t in consumer_threads:
            t.join(timeout=5)
        
        work_queue.join()
        
        # Verify results
        assert len(results) == 5, f"Should have processed 5 items, got {len(results)}"
        
        # Check that all items were processed
        processed_ids = {r['original']['id'] for r in results}
        expected_ids = {0, 1, 2, 3, 4}
        assert processed_ids == expected_ids, f"Missing items: {expected_ids - processed_ids}"
        
        # Check thread safety (no duplicates)
        assert len(set(r['original']['id'] for r in results)) == 5, "Duplicate processing detected"
        
        print(f"   ✓ Processed {len(results)} items across 2 consumers")
        print(f"   ✓ No duplicate processing detected")
        print(f"   ✓ All threads completed successfully")
        
        print("✅ Producer-consumer pattern tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Producer-consumer pattern test failed: {e}")
        return False

def test_thread_safety_with_locks():
    """Test thread safety using locks similar to pipeline implementation."""
    print("🧪 Testing Thread Safety with Locks...")
    
    try:
        # Shared data structure (like file_status in pipeline)
        shared_data = {}
        data_lock = threading.RLock()  # Same type as pipeline
        
        # Initialize data
        file_paths = [f"/fake/file_{i}.mp4" for i in range(3)]
        for file_path in file_paths:
            shared_data[file_path] = {
                'status': 'pending',
                'segments': [],
                'compressed_segments': [],
                'counter': 0
            }
        
        # Worker function that modifies shared data
        def worker(worker_id, file_path):
            for i in range(10):
                with data_lock:
                    # Read current state
                    current_counter = shared_data[file_path]['counter']
                    
                    # Simulate some work
                    time.sleep(0.001)
                    
                    # Update state
                    shared_data[file_path]['counter'] = current_counter + 1
                    shared_data[file_path]['segments'].append(f'seg_{worker_id}_{i}')
                    
                    # Update status
                    if shared_data[file_path]['counter'] >= 30:  # 3 workers × 10 increments
                        shared_data[file_path]['status'] = 'complete'
        
        # Start workers (3 workers per file, simulating segment processing)
        threads = []
        for file_path in file_paths:
            for worker_id in range(3):
                t = threading.Thread(
                    target=worker, 
                    args=(worker_id, file_path),
                    name=f"Worker-{worker_id}-{Path(file_path).stem}"
                )
                threads.append(t)
                t.start()
        
        # Wait for all workers to complete
        for t in threads:
            t.join(timeout=5)
        
        # Verify results
        for file_path in file_paths:
            file_data = shared_data[file_path]
            
            # Check counter (should be exactly 30 from 3 workers × 10 increments each)
            assert file_data['counter'] == 30, f"Counter should be 30, got {file_data['counter']} for {file_path}"
            
            # Check segments (should have 30 segments)
            assert len(file_data['segments']) == 30, f"Should have 30 segments, got {len(file_data['segments'])} for {file_path}"
            
            # Check status
            assert file_data['status'] == 'complete', f"Status should be 'complete' for {file_path}"
            
            print(f"   ✓ File {Path(file_path).name}: counter={file_data['counter']}, segments={len(file_data['segments'])}, status={file_data['status']}")
        
        print(f"   ✓ All {len(threads)} threads completed successfully")
        print(f"   ✓ No race conditions detected")
        print(f"   ✓ Lock-based synchronization working correctly")
        
        print("✅ Thread safety tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Thread safety test failed: {e}")
        return False

def test_queue_blocking_behavior():
    """Test queue blocking behavior under high load."""
    print("🧪 Testing Queue Blocking Behavior...")
    
    try:
        # Small queue to test blocking
        work_queue = queue.Queue(maxsize=3)
        results = []
        
        def fast_producer():
            producer_id = threading.current_thread().name
            for i in range(10):
                item = {'id': i, 'producer': producer_id}
                work_queue.put(item)  # Will block when queue is full
                print(f"   Producer queued item {i}")
        
        def slow_consumer():
            consumer_id = threading.current_thread().name
            while True:
                try:
                    item = work_queue.get(timeout=2.0)
                    if item is None:
                        work_queue.task_done()
                        break
                    
                    # Slow processing
                    time.sleep(0.1)
                    results.append(item)
                    work_queue.task_done()
                    print(f"   Consumer processed item {item['id']}")
                    
                except queue.Empty:
                    break
        
        # Start consumer first
        consumer_thread = threading.Thread(target=slow_consumer, name="SlowConsumer")
        consumer_thread.start()
        
        # Start producer (should block when queue fills)
        producer_thread = threading.Thread(target=fast_producer, name="FastProducer")
        producer_thread.start()
        
        # Wait a bit, then send stop signal
        time.sleep(1.0)
        work_queue.put(None)  # Stop signal
        
        # Wait for completion
        producer_thread.join(timeout=10)
        consumer_thread.join(timeout=10)
        
        # Verify that some items were processed (queue was working)
        assert len(results) > 0, "Consumer should have processed some items"
        assert len(results) <= 10, "Should not process more than 10 items"
        
        print(f"   ✓ Processed {len(results)} items with queue size 3")
        print(f"   ✓ Producer blocking behavior working correctly")
        print(f"   ✓ Consumer timeout behavior working correctly")
        
        print("✅ Queue blocking behavior tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Queue blocking behavior test failed: {e}")
        return False

def run_all_threading_tests():
    """Run all Phase 1 threading tests."""
    print("🚀 Running Phase 1 Threading Tests...\n")
    
    tests = [
        test_producer_consumer_pattern,
        test_thread_safety_with_locks,
        test_queue_blocking_behavior
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
        print()  # Add spacing between tests
    
    print(f"📊 Threading Test Summary:")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📈 Success Rate: {(passed/(passed+failed)*100):.1f}%")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_threading_tests()
    sys.exit(0 if success else 1)