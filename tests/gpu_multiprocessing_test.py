"""
GPU Multiprocessing Test - 6 Parallel OCR Processes
Test if GTX 1650 can handle 6 simultaneous PaddleOCR instances
"""

import multiprocessing as mp
import time
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def worker_process(worker_id: int, num_iterations: int, results_queue: mp.Queue):
    """
    Simulate single bookmaker OCR workload
    """
    try:
        # Import here to avoid CUDA initialization in main process
        from paddleocr import PaddleOCR
        import numpy as np
        from PIL import Image
        
        # Initialize PaddleOCR with GPU
        ocr = PaddleOCR(
            use_gpu=True,
            gpu_mem=500,  # 500MB per process
            lang='en',
            show_log=False,
            use_angle_cls=False,
            det=True,
            rec=True
        )
        
        # Create dummy image (simulating screenshot region)
        dummy_img = Image.new('RGB', (200, 50), color='white')
        img_array = np.array(dummy_img)
        
        times = []
        
        for i in range(num_iterations):
            start = time.perf_counter()
            
            # Perform OCR
            result = ocr.ocr(img_array, cls=False)
            
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)
            
            # Small delay to simulate real workload
            time.sleep(0.1)
        
        # Calculate stats
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        results_queue.put({
            'worker_id': worker_id,
            'avg_ms': avg_time,
            'min_ms': min_time,
            'max_ms': max_time,
            'iterations': num_iterations,
            'success': True
        })
        
    except Exception as e:
        results_queue.put({
            'worker_id': worker_id,
            'error': str(e),
            'success': False
        })


def test_sequential_baseline():
    """Test 1: Sequential OCR (no multiprocessing)"""
    print("\n" + "="*60)
    print("TEST 1: SEQUENTIAL BASELINE (Single Process)")
    print("="*60)
    
    try:
        from paddleocr import PaddleOCR
        import numpy as np
        from PIL import Image
        
        ocr = PaddleOCR(
            use_gpu=True,
            gpu_mem=2000,  # Can use more since it's alone
            lang='en',
            show_log=False,
            use_angle_cls=False
        )
        
        dummy_img = Image.new('RGB', (200, 50), color='white')
        img_array = np.array(dummy_img)
        
        times = []
        for i in range(50):
            start = time.perf_counter()
            result = ocr.ocr(img_array, cls=False)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        avg = sum(times) / len(times)
        print(f"✅ Sequential OCR: {avg:.1f}ms avg")
        return avg
        
    except Exception as e:
        print(f"❌ Sequential test failed: {e}")
        return None


def test_parallel_6_processes():
    """Test 2: 6 Parallel OCR Processes"""
    print("\n" + "="*60)
    print("TEST 2: 6 PARALLEL PROCESSES (Simulating 6 Bookmakers)")
    print("="*60)
    
    # CRITICAL: Use 'spawn' for CUDA safety
    mp.set_start_method('spawn', force=True)
    
    num_workers = 6
    iterations_per_worker = 30
    
    results_queue = mp.Queue()
    processes = []
    
    # Start all workers simultaneously
    print(f"🚀 Starting {num_workers} workers...")
    start_time = time.time()
    
    for worker_id in range(num_workers):
        p = mp.Process(
            target=worker_process,
            args=(worker_id, iterations_per_worker, results_queue)
        )
        p.start()
        processes.append(p)
    
    # Wait for all to complete
    for p in processes:
        p.join()
    
    total_time = time.time() - start_time
    
    # Collect results
    results = []
    while not results_queue.empty():
        results.append(results_queue.get())
    
    # Print results
    print(f"\n⏱️  Total execution time: {total_time:.1f}s")
    print("\nPer-Worker Results:")
    print("-" * 60)
    
    successful = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]
    
    if successful:
        for r in sorted(successful, key=lambda x: x['worker_id']):
            print(f"Worker {r['worker_id']}: "
                  f"avg={r['avg_ms']:.1f}ms, "
                  f"min={r['min_ms']:.1f}ms, "
                  f"max={r['max_ms']:.1f}ms")
        
        avg_across_workers = sum(r['avg_ms'] for r in successful) / len(successful)
        print(f"\n📊 Average across all workers: {avg_across_workers:.1f}ms")
        
        # Calculate throughput
        total_ocr_calls = sum(r['iterations'] for r in successful)
        throughput = total_ocr_calls / total_time
        print(f"🚀 Throughput: {throughput:.1f} OCR/sec")
        
    if failed:
        print(f"\n❌ Failed workers: {len(failed)}")
        for r in failed:
            print(f"  Worker {r['worker_id']}: {r['error']}")
    
    return successful, failed


def test_memory_usage():
    """Test 3: Monitor GPU memory during parallel execution"""
    print("\n" + "="*60)
    print("TEST 3: GPU MEMORY MONITORING")
    print("="*60)
    
    try:
        import pynvml
        
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        
        # Get GPU info
        name = pynvml.nvmlDeviceGetName(handle)
        memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        
        print(f"GPU: {name}")
        print(f"Total VRAM: {memory_info.total / 1024**3:.2f} GB")
        print(f"Used VRAM: {memory_info.used / 1024**3:.2f} GB")
        print(f"Free VRAM: {memory_info.free / 1024**3:.2f} GB")
        
        pynvml.nvmlShutdown()
        
    except Exception as e:
        print(f"⚠️  Cannot monitor GPU memory: {e}")
        print("   Install: pip install pynvml")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 GPU MULTIPROCESSING TEST - GTX 1650")
    print("="*60)
    print("Testing if 6 parallel PaddleOCR processes can run on GTX 1650")
    
    # Test 1: Sequential baseline
    seq_time = test_sequential_baseline()
    
    # Test 2: 6 parallel processes
    successful, failed = test_parallel_6_processes()
    
    # Test 3: Memory monitoring
    test_memory_usage()
    
    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    
    if successful:
        parallel_avg = sum(r['avg_ms'] for r in successful) / len(successful)
        
        if seq_time:
            slowdown = (parallel_avg / seq_time - 1) * 100
            print(f"Sequential: {seq_time:.1f}ms")
            print(f"Parallel (6 workers): {parallel_avg:.1f}ms")
            print(f"Slowdown: {slowdown:+.1f}%")
            
            if slowdown > 50:
                print("\n⚠️  WARNING: Significant slowdown detected!")
                print("   GPU memory contention likely occurring.")
                print("   Recommendation: Use Tesseract whitelist (110ms) instead!")
            elif slowdown > 20:
                print("\n⚠️  Moderate slowdown detected.")
                print("   GPU can handle 6 processes but with some contention.")
            else:
                print("\n✅ GPU handles 6 processes well!")
        
        if len(successful) < 6:
            print(f"\n❌ Only {len(successful)}/6 workers succeeded!")
            print("   GTX 1650 may not have enough VRAM for 6 processes.")
            print("   Recommendation: Use Tesseract or reduce to 3-4 bookmakers.")
    else:
        print("\n❌ All workers failed!")
        print("   PaddleOCR GPU mode not compatible with multiprocessing.")
        print("   Recommendation: Use Tesseract whitelist (110ms).")
    
    print("\n" + "="*60)
