# Performance & Scalability

## Priority: Medium
## Effort: Medium  
## Type: Enhancement

## Problem Description

While Egregora successfully processed a 208MB WhatsApp export, there are opportunities for performance improvements and better scalability for larger datasets:

1. **No Progress Indicators**: Large file processing appears to hang
2. **Memory Usage**: Entire dataset loaded into memory with Polars
3. **Sequential Processing**: Groups processed one at a time
4. **No Streaming**: Large files must fit in memory
5. **Limited Concurrency**: Enrichment could be parallelized better

**Current processing characteristics:**
- 208MB ZIP file processed successfully
- No feedback during long operations
- Memory usage not optimized for very large exports
- Single-threaded for most operations

## Current Behavior

### Large File Processing
```bash
uv run egregora --days 7
# No output for minutes while processing large files
# User unsure if system is working or hung
```

### Memory Usage
- Entire Polars DataFrame loaded into memory
- Media files extracted to disk but metadata kept in memory
- No streaming or chunked processing for very large exports

### Sequential Operations
- Groups processed one at a time
- Enrichment API calls mostly sequential
- No parallelization of independent operations

## Proposed Solution

### 1. Progress Indicators

```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

def process_with_progress(exports: List[WhatsAppExport]):
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        
        # Main processing task
        main_task = progress.add_task("Processing exports...", total=len(exports))
        
        for export in exports:
            # Sub-task for current export
            export_task = progress.add_task(
                f"Processing {export.name}...", 
                total=100
            )
            
            # Parsing phase
            progress.update(export_task, advance=10, description="Parsing...")
            parse_export(export)
            
            # Anonymization phase  
            progress.update(export_task, advance=20, description="Anonymizing...")
            anonymize_messages(export)
            
            # Enrichment phase
            progress.update(export_task, advance=30, description="Enriching...")
            enrich_content(export)
            
            # Generation phase
            progress.update(export_task, advance=40, description="Generating posts...")
            generate_posts(export)
            
            progress.update(main_task, advance=1)
            progress.remove_task(export_task)
```

### 2. Streaming Processing for Large Files

```python
class StreamingParser:
    """Process large WhatsApp exports without loading everything into memory."""
    
    def __init__(self, chunk_size: int = 10000):
        self.chunk_size = chunk_size
    
    def parse_streaming(self, zip_path: Path) -> Iterator[pl.DataFrame]:
        """Parse WhatsApp export in chunks."""
        with zipfile.ZipFile(zip_path) as zf:
            chat_file = self.find_chat_file(zf)
            
            with zf.open(chat_file) as f:
                buffer = []
                for line in f:
                    buffer.append(line.decode('utf-8'))
                    
                    if len(buffer) >= self.chunk_size:
                        # Process chunk and yield DataFrame
                        df_chunk = self.parse_chunk(buffer)
                        yield df_chunk
                        buffer = []
                
                # Process remaining lines
                if buffer:
                    yield self.parse_chunk(buffer)
    
    def process_large_export(self, export: WhatsAppExport) -> None:
        """Process export using streaming approach."""
        daily_chunks = defaultdict(list)
        
        for chunk_df in self.parse_streaming(export.zip_path):
            # Group by date
            for date_str, date_df in chunk_df.group_by("date"):
                daily_chunks[date_str].append(date_df)
        
        # Process each day
        for date_str, chunks in daily_chunks.items():
            day_df = pl.concat(chunks)
            self.process_daily_messages(date_str, day_df)
```

### 3. Parallel Processing

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

class ParallelProcessor:
    """Process multiple groups and perform enrichment concurrently."""
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
    
    async def process_groups_parallel(self, groups: List[GroupSource]) -> None:
        """Process multiple groups concurrently."""
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async def process_group_with_limit(group: GroupSource):
            async with semaphore:
                return await self.process_single_group(group)
        
        tasks = [process_group_with_limit(group) for group in groups]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to process group {groups[i].name}: {result}")
    
    async def enrich_links_parallel(self, links: List[str]) -> Dict[str, EnrichmentResult]:
        """Enrich multiple links concurrently with rate limiting."""
        enricher = ContentEnricher(self.config)
        
        async def enrich_with_retry(link: str) -> Tuple[str, EnrichmentResult]:
            try:
                result = await enricher.enrich_async(link)
                return link, result
            except Exception as e:
                logger.warning(f"Failed to enrich {link}: {e}")
                return link, None
        
        # Batch requests to respect API rate limits
        batch_size = 5
        results = {}
        
        for i in range(0, len(links), batch_size):
            batch = links[i:i + batch_size]
            batch_tasks = [enrich_with_retry(link) for link in batch]
            batch_results = await asyncio.gather(*batch_tasks)
            
            for link, result in batch_results:
                if result:
                    results[link] = result
            
            # Rate limiting pause between batches
            await asyncio.sleep(1)
        
        return results
```

### 4. Memory Optimization

```python
class MemoryOptimizedProcessor:
    """Process exports with optimized memory usage."""
    
    def __init__(self, memory_limit_mb: int = 500):
        self.memory_limit = memory_limit_mb * 1024 * 1024
    
    def process_with_memory_limit(self, export: WhatsAppExport) -> None:
        """Process export while monitoring memory usage."""
        import psutil
        process = psutil.Process()
        
        # Check if we should use streaming mode
        if export.estimated_memory_usage() > self.memory_limit:
            logger.info(f"Large export detected, using streaming mode")
            self.process_streaming(export)
        else:
            self.process_standard(export)
        
        # Monitor memory during processing
        current_memory = process.memory_info().rss
        if current_memory > self.memory_limit:
            logger.warning(f"Memory usage high: {current_memory / 1024 / 1024:.1f}MB")
    
    def optimize_dataframe_memory(self, df: pl.DataFrame) -> pl.DataFrame:
        """Optimize DataFrame memory usage."""
        return df.select([
            # Use more efficient string storage
            pl.col("content").str.to_categorical(),
            pl.col("sender").str.to_categorical(),
            # Use smaller integer types where possible
            pl.col("message_id").cast(pl.UInt32),
            # Keep other columns as-is
            pl.exclude(["content", "sender", "message_id"])
        ])
```

### 5. Performance Monitoring

```python
import time
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class PerformanceMetrics:
    operation: str
    duration: float
    memory_used: int
    items_processed: int
    
    @property
    def items_per_second(self) -> float:
        return self.items_processed / self.duration if self.duration > 0 else 0

class PerformanceMonitor:
    """Monitor and report performance metrics."""
    
    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
    
    @contextmanager
    def measure(self, operation: str, items_count: int = 0):
        """Context manager to measure operation performance."""
        import psutil
        process = psutil.Process()
        
        start_time = time.time()
        start_memory = process.memory_info().rss
        
        yield
        
        end_time = time.time()
        end_memory = process.memory_info().rss
        
        metrics = PerformanceMetrics(
            operation=operation,
            duration=end_time - start_time,
            memory_used=end_memory - start_memory,
            items_processed=items_count
        )
        
        self.metrics.append(metrics)
        logger.info(f"{operation}: {metrics.duration:.2f}s, "
                   f"{metrics.items_per_second:.1f} items/s")
    
    def generate_report(self) -> str:
        """Generate performance report."""
        if not self.metrics:
            return "No performance data collected"
        
        total_time = sum(m.duration for m in self.metrics)
        total_items = sum(m.items_processed for m in self.metrics)
        
        report = f"Performance Summary:\n"
        report += f"Total time: {total_time:.2f}s\n"
        report += f"Total items: {total_items}\n"
        report += f"Overall rate: {total_items / total_time:.1f} items/s\n\n"
        
        for metric in self.metrics:
            report += f"{metric.operation}: {metric.duration:.2f}s "
            report += f"({metric.items_per_second:.1f} items/s)\n"
        
        return report
```

## Implementation Details

### Performance Benchmarks

Create benchmarks for different file sizes:
```python
def benchmark_processing():
    """Benchmark processing performance."""
    test_files = [
        ("small", "1MB"),
        ("medium", "50MB"), 
        ("large", "200MB"),
        ("huge", "1GB")
    ]
    
    for name, size in test_files:
        with performance_monitor.measure(f"process_{name}_file", items_count=1):
            process_test_file(size)
```

### Memory Profiling
```bash
# Add memory profiling tools
uv add memory-profiler
python -m memory_profiler egregora/processor.py
```

### Async Integration
```python
# Update main CLI to support async processing
async def main_async():
    processor = ParallelProcessor()
    await processor.process_groups_parallel(groups)

def main():
    if config.parallel_processing:
        asyncio.run(main_async())
    else:
        # Fallback to synchronous processing
        process_sequential(groups)
```

## Expected Benefits

1. **Better UX**: Progress indicators show processing status
2. **Scalability**: Handle much larger exports (>1GB)
3. **Performance**: Faster processing through parallelization
4. **Resource Efficiency**: Lower memory usage for large files
5. **Monitoring**: Performance insights and optimization guidance

## Acceptance Criteria

- [ ] Progress bars for all long-running operations
- [ ] Streaming mode for files >100MB
- [ ] Parallel processing option for multiple groups
- [ ] Memory usage monitoring and warnings
- [ ] Performance benchmarks and reporting
- [ ] Configurable concurrency limits
- [ ] Graceful handling of memory constraints

## Configuration Options

```toml
[performance]
# Enable parallel processing
parallel_processing = true
max_workers = 4

# Memory management
memory_limit_mb = 500
streaming_threshold_mb = 100

# Progress reporting
show_progress = true
detailed_progress = false

# Performance monitoring
collect_metrics = true
metrics_file = "metrics/performance.json"
```

## Files to Modify

- `src/egregora/processor.py` - Add progress and parallel processing
- `src/egregora/parser.py` - Streaming parser implementation
- `src/egregora/enrichment.py` - Async enrichment
- `src/egregora/config.py` - Performance configuration
- `src/egregora/monitoring.py` - New performance monitoring
- `docs/performance.md` - Performance guide

## Related Issues

- #007: Media Handling (optimize media processing)
- #012: Monitoring & Analytics
- #006: Testing & Development (performance tests)