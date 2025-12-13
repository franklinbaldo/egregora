"""Memory monitoring utilities for egregora pipeline.

Tracks memory usage during blog generation to identify bottlenecks.
"""

import gc
import logging
import os
import time
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import psutil

logger = logging.getLogger(__name__)


def get_memory_usage() -> dict[str, float]:
    """Get current memory usage statistics.
    
    Returns:
        Dictionary with memory stats in MB
    """
    process = psutil.Process()
    mem_info = process.memory_info()
    
    return {
        "rss_mb": mem_info.rss / 1024 / 1024,  # Resident Set Size
        "vms_mb": mem_info.vms / 1024 / 1024,  # Virtual Memory Size
        "percent": process.memory_percent(),
        "available_mb": psutil.virtual_memory().available / 1024 / 1024,
    }


def log_memory(label: str = "") -> None:
    """Log current memory usage."""
    mem = get_memory_usage()
    logger.info(
        f"[Memory] {label}: RSS={mem['rss_mb']:.1f}MB, "
        f"VMS={mem['vms_mb']:.1f}MB, "
        f"%={mem['percent']:.1f}%, "
        f"Avail={mem['available_mb']:.1f}MB"
    )


@contextmanager
def monitor_memory(label: str):
    """Context manager to monitor memory usage in a block.
    
    Usage:
        with monitor_memory("Loading embeddings"):
            embeddings = load_embeddings()
    """
    gc.collect()
    start_mem = get_memory_usage()
    start_time = time.time()
    
    logger.info(f"[Memory] {label} - START: {start_mem['rss_mb']:.1f}MB")
    
    try:
        yield
    finally:
        gc.collect()
        end_mem = get_memory_usage()
        duration = time.time() - start_time
        delta = end_mem['rss_mb'] - start_mem['rss_mb']
        
        logger.info(
            f"[Memory] {label} - END: {end_mem['rss_mb']:.1f}MB "
            f"(Δ{delta:+.1f}MB in {duration:.1f}s)"
        )


def profile_memory(func: Callable) -> Callable:
    """Decorator to profile memory usage of a function.
    
    Usage:
        @profile_memory
        def my_function():
            ...
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with monitor_memory(f"{func.__module__}.{func.__name__}"):
            return func(*args, **kwargs)
    return wrapper


def track_object_sizes(show_top: int = 10) -> None:
    """Track sizes of objects in memory.
    
    Args:
        show_top: Number of top objects to show
    """
    import sys
    from collections import defaultdict
    
    type_counts = defaultdict(int)
    type_sizes = defaultdict(int)
    
    for obj in gc.get_objects():
        obj_type = type(obj).__name__
        type_counts[obj_type] += 1
        try:
            type_sizes[obj_type] += sys.getsizeof(obj)
        except (TypeError, AttributeError):
            pass
    
    # Sort by size
    sorted_types = sorted(type_sizes.items(), key=lambda x: x[1], reverse=True)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"TOP {show_top} MEMORY CONSUMERS")
    logger.info(f"{'='*60}")
    logger.info(f"{'Type':<30} {'Count':<10} {'Size (MB)':<15}")
    logger.info(f"{'-'*60}")
    
    for obj_type, size in sorted_types[:show_top]:
        count = type_counts[obj_type]
        size_mb = size / 1024 / 1024
        logger.info(f"{obj_type:<30} {count:<10} {size_mb:<15.2f}")
    
    logger.info(f"{'='*60}\n")


def estimate_lancedb_size(lancedb_dir: Path) -> dict[str, float]:
    """Estimate LanceDB memory footprint.
    
    Args:
        lancedb_dir: Path to LanceDB directory
        
    Returns:
        Dictionary with size estimates
    """
    if not lancedb_dir.exists():
        return {"disk_mb": 0, "estimated_ram_mb": 0}
    
    total_size = sum(f.stat().st_size for f in lancedb_dir.rglob("*") if f.is_file())
    disk_mb = total_size / 1024 / 1024
    
    # LanceDB typically uses ~2-3x disk size in RAM when loaded
    estimated_ram_mb = disk_mb * 2.5
    
    return {
        "disk_mb": disk_mb,
        "estimated_ram_mb": estimated_ram_mb,
        "files": len(list(lancedb_dir.rglob("*"))),
    }


def estimate_zip_size(zip_path: Path) -> dict[str, float]:
    """Estimate ZIP memory footprint.
    
    Args:
        zip_path: Path to ZIP file
        
    Returns:
        Dictionary with size estimates
    """
    import zipfile
    
    if not zip_path.exists():
        return {"compressed_mb": 0, "uncompressed_mb": 0}
    
    compressed_mb = zip_path.stat().st_size / 1024 / 1024
    
    # Estimate uncompressed size
    with zipfile.ZipFile(zip_path) as zf:
        uncompressed = sum(info.file_size for info in zf.infolist())
        uncompressed_mb = uncompressed / 1024 / 1024
    
    return {
        "compressed_mb": compressed_mb,
        "uncompressed_mb": uncompressed_mb,
        "compression_ratio": uncompressed_mb / compressed_mb if compressed_mb > 0 else 0,
    }


class MemoryMonitor:
    """Continuous memory monitoring during pipeline execution."""
    
    def __init__(self, interval: float = 5.0, log_file: Path | None = None):
        """Initialize monitor.
        
        Args:
            interval: Sampling interval in seconds
            log_file: Optional file to write memory logs
        """
        self.interval = interval
        self.log_file = log_file
        self.samples: list[dict[str, Any]] = []
        self._running = False
    
    def start(self) -> None:
        """Start monitoring in background."""
        import threading
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info(f"Memory monitoring started (interval={self.interval}s)")
    
    def stop(self) -> None:
        """Stop monitoring and save results."""
        self._running = False
        if hasattr(self, '_thread'):
            self._thread.join(timeout=self.interval * 2)
        
        if self.log_file and self.samples:
            self._save_samples()
        
        logger.info("Memory monitoring stopped")
        self._print_summary()
    
    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            sample = {
                "timestamp": time.time(),
                **get_memory_usage(),
            }
            self.samples.append(sample)
            time.sleep(self.interval)
    
    def _save_samples(self) -> None:
        """Save samples to CSV."""
        import csv
        
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.samples[0].keys())
            writer.writeheader()
            writer.writerows(self.samples)
        
        logger.info(f"Memory samples saved to {self.log_file}")
    
    def _print_summary(self) -> None:
        """Print memory usage summary."""
        if not self.samples:
            return
        
        rss_values = [s['rss_mb'] for s in self.samples]
        
        logger.info(f"\n{'='*60}")
        logger.info(f"MEMORY USAGE SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"  Samples: {len(self.samples)}")
        logger.info(f"  Duration: {self.samples[-1]['timestamp'] - self.samples[0]['timestamp']:.1f}s")
        logger.info(f"  Peak RSS: {max(rss_values):.1f}MB")
        logger.info(f"  Min RSS: {min(rss_values):.1f}MB")
        logger.info(f"  Avg RSS: {sum(rss_values)/len(rss_values):.1f}MB")
        logger.info(f"  Peak %: {max(s['percent'] for s in self.samples):.1f}%")
        logger.info(f"{'='*60}\n")


def diagnose_memory_issues(
    zip_path: Path | None = None,
    lancedb_dir: Path | None = None,
) -> None:
    """Diagnose potential memory issues.
    
    Args:
        zip_path: Path to input ZIP file
        lancedb_dir: Path to LanceDB directory
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"MEMORY DIAGNOSTICS")
    logger.info(f"{'='*60}")
    
    # Current memory
    current = get_memory_usage()
    logger.info(f"\nCurrent Memory:")
    logger.info(f"  RSS: {current['rss_mb']:.1f}MB")
    logger.info(f"  Available: {current['available_mb']:.1f}MB")
    logger.info(f"  Process %: {current['percent']:.1f}%")
    
    # ZIP analysis
    if zip_path and zip_path.exists():
        zip_info = estimate_zip_size(zip_path)
        logger.info(f"\nZIP File:")
        logger.info(f"  Compressed: {zip_info['compressed_mb']:.1f}MB")
        logger.info(f"  Uncompressed: {zip_info['uncompressed_mb']:.1f}MB")
        logger.info(f"  Ratio: {zip_info['compression_ratio']:.1f}x")
        logger.info(f"  ⚠️  Risk: Loading full ZIP uses {zip_info['uncompressed_mb']:.1f}MB RAM")
    
    # LanceDB analysis
    if lancedb_dir and lancedb_dir.exists():
        db_info = estimate_lancedb_size(lancedb_dir)
        logger.info(f"\nLanceDB:")
        logger.info(f"  Disk: {db_info['disk_mb']:.1f}MB")
        logger.info(f"  Estimated RAM: {db_info['estimated_ram_mb']:.1f}MB")
        logger.info(f"  Files: {db_info['files']}")
        logger.info(f"  ⚠️  Risk: Loading embeddings uses ~{db_info['estimated_ram_mb']:.1f}MB RAM")
    
    # Total estimated usage
    total_estimated = 0
    if zip_path and zip_path.exists():
        total_estimated += estimate_zip_size(zip_path)['uncompressed_mb']
    if lancedb_dir and lancedb_dir.exists():
        total_estimated += estimate_lancedb_size(lancedb_dir)['estimated_ram_mb']
    
    if total_estimated > 0:
        logger.info(f"\nEstimated Total: {total_estimated:.1f}MB")
        if total_estimated > current['available_mb'] * 0.8:
            logger.warning(
                f"⚠️  WARNING: Estimated usage ({total_estimated:.1f}MB) "
                f"exceeds 80% of available RAM ({current['available_mb']:.1f}MB)"
            )
    
    # Object analysis
    logger.info(f"\nObject Analysis:")
    track_object_sizes(show_top=5)
    
    logger.info(f"{'='*60}\n")


# Convenience function for CLI usage
def monitor_pipeline(
    output_dir: Path,
    interval: float = 5.0,
) -> MemoryMonitor:
    """Start memory monitoring for pipeline execution.
    
    Args:
        output_dir: Output directory for logs
        interval: Sampling interval
        
    Returns:
        MemoryMonitor instance (call .stop() when done)
    """
    log_file = output_dir / ".egregora" / "memory_profile.csv"
    monitor = MemoryMonitor(interval=interval, log_file=log_file)
    monitor.start()
    return monitor
