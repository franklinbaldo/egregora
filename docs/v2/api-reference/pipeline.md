# Pipeline Orchestration Reference

The pipeline orchestration layer coordinates the execution of the content generation pipeline, managing window processing, worker coordination, and output generation.

## Overview

Pipeline orchestration provides:

- **Pipeline Runner**: Main orchestration loop for processing conversation windows
- **Pipeline Factory**: Constructs pipeline components from configuration
- **Pipeline Context**: Shared state and configuration for pipeline execution
- **Worker Base**: Abstract base for async workers (enrichment, profiles, banners)
- **Materializer**: Output generation and site building
- **Persistence**: Pipeline state persistence and recovery
- **Write Pipeline**: High-level write command orchestration

All pipeline components are designed for async execution with proper error handling and recovery.

## Core Pipeline Components

### Pipeline Runner

The main orchestrator that processes conversation windows and coordinates workers.

::: egregora.orchestration.runner.PipelineRunner
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      show_category_heading: true

### Pipeline Factory

Constructs pipeline components from configuration.

::: egregora.orchestration.factory.PipelineFactory
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      show_category_heading: true

### Pipeline Context

Shared context and configuration for pipeline execution.

::: egregora.orchestration.context.PipelineContext
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      show_category_heading: true

## Workers

### Worker Base

Abstract base class for async workers.

::: egregora.orchestration.worker_base
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Output Generation

### Materializer

Generates final output (MkDocs site, static files).

::: egregora.orchestration.materializer
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

### Persistence

Pipeline state persistence and recovery.

::: egregora.orchestration.persistence
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Pipeline Modules

### Write Pipeline

High-level orchestration for the write command.

::: egregora.orchestration.pipelines.write
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

### Media Processing Module

Handles media extraction and processing for windows.

::: egregora.orchestration.pipelines.modules.media
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Taxonomy Module

Manages content categorization and tagging.

::: egregora.orchestration.pipelines.modules.taxonomy
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Usage Examples

### Running the Pipeline

```python
from egregora.orchestration.pipelines.write import run_cli_flow
from pathlib import Path

# Run the complete write pipeline
await run_cli_flow(
    site_root=Path("./my-blog"),
    source="whatsapp",
    source_path=Path("./whatsapp-export"),
    window_size=7,
    window_unit="days",
)
```

### Using Pipeline Context

```python
from egregora.orchestration.context import PipelineContext
from egregora.config import load_egregora_config

# Create pipeline context
config = load_egregora_config(Path("./my-blog"))
context = PipelineContext(
    config=config,
    site_root=Path("./my-blog"),
    storage=storage,
    media_mapping=media_files,
)

# Context is shared across all pipeline stages
```

### Using the Pipeline Runner

```python
from egregora.orchestration.runner import PipelineRunner
from egregora.transformations.windowing import create_windows

# Create windows from messages
windows = create_windows(
    messages=message_table,
    window_size=7,
    window_unit="days",
)

# Create runner
runner = PipelineRunner(context=context)

# Process all windows
results, last_timestamp = runner.process_windows(windows)

# Results contain generated documents by window
for window_label, window_results in results.items():
    posts = window_results.get("posts", [])
    print(f"Window {window_label}: {len(posts)} posts")
```

### Creating a Custom Worker

```python
from egregora.orchestration.worker_base import WorkerBase
from egregora.data_primitives.document import Document

class CustomWorker(WorkerBase):
    """Custom async worker for pipeline processing."""

    async def process_batch(
        self,
        items: list[Document],
    ) -> list[Document]:
        """Process a batch of documents.

        Args:
            items: Documents to process

        Returns:
            Processed documents
        """
        results = []
        for item in items:
            # Custom processing logic
            processed = await self.process_item(item)
            results.append(processed)
        return results

    async def process_item(self, item: Document) -> Document:
        """Process single document."""
        # Implementation here
        pass

# Use the worker
worker = CustomWorker()
results = await worker.process_batch(documents)
```

### Pipeline Factory

```python
from egregora.orchestration.factory import PipelineFactory

# Create factory
factory = PipelineFactory(config=egregora_config)

# Create input adapter
adapter = factory.create_input_adapter(source="whatsapp")

# Create storage manager
storage = factory.create_storage_manager(
    db_path=Path("./my-blog/pipeline.duckdb")
)

# Create output adapter
output = factory.create_output_adapter(
    adapter_type="mkdocs",
    site_root=Path("./my-blog"),
)
```

### Materializer

```python
from egregora.orchestration.materializer import materialize_output

# Generate final output
await materialize_output(
    context=context,
    documents=all_documents,
    output_path=Path("./my-blog/docs"),
)

# This creates the MkDocs site structure with all posts
```

### Pipeline Persistence

```python
from egregora.orchestration.persistence import (
    save_pipeline_state,
    load_pipeline_state,
    resume_pipeline,
)

# Save pipeline state
save_pipeline_state(
    state_path=Path("./my-blog/.pipeline_state"),
    context=context,
    last_window="2025-01-15",
)

# Load pipeline state
state = load_pipeline_state(
    state_path=Path("./my-blog/.pipeline_state")
)

# Resume from saved state
results = await resume_pipeline(
    state=state,
    context=context,
)
```

## Pipeline Architecture

### Execution Flow

The pipeline follows this execution pattern:

```
1. Input Stage
   ├── Parse source (WhatsApp/IPERON/etc.)
   ├── Extract media files
   └── Load into DuckDB

2. Transformation Stage
   ├── Create conversation windows
   ├── Enrich with URL/media context
   └── Generate author profiles

3. Generation Stage
   ├── Writer agent creates posts
   ├── Banner agent creates visuals
   └── Taxonomy categorization

4. Output Stage
   ├── Materialize MkDocs site
   ├── Copy media files
   └── Build static site
```

### Window Processing

Each window is processed independently:

```python
# Window structure
window = {
    "label": "2025-01-15",  # Window identifier
    "messages": table,       # Ibis table of messages
    "start_time": datetime,  # Window start
    "end_time": datetime,    # Window end
}

# Window processing generates:
results = {
    "posts": [Document(...)],         # Blog posts
    "profiles": [Document(...)],      # Author profiles
    "enrichments": [Document(...)],   # Context enrichments
    "media": [Document(...)],         # Media descriptions
}
```

### Error Handling

Pipeline operations use structured error handling:

```python
from egregora.orchestration.exceptions import (
    WindowSizeError,
    WindowSplitError,
    OutputSinkError,
)

try:
    results = runner.process_windows(windows)
except WindowSizeError as e:
    # Window too large, needs splitting
    print(f"Window size error: {e}")
except WindowSplitError as e:
    # Failed to split window
    print(f"Split error: {e}")
except OutputSinkError as e:
    # Failed to write output
    print(f"Output error: {e}")
```

### Async Coordination

Workers use async/await for concurrent processing:

```python
import asyncio

# Process multiple windows concurrently
async def process_all_windows(windows, context):
    tasks = [
        process_single_window(window, context)
        for window in windows
    ]
    results = await asyncio.gather(*tasks)
    return results
```

## Performance Optimization

### Window Sizing

Choose appropriate window sizes based on content:

```python
# Small windows for high-frequency chat
windows = create_windows(messages, window_size=1, window_unit="days")

# Large windows for low-frequency content
windows = create_windows(messages, window_size=30, window_unit="days")

# Adaptive: runner automatically splits oversized windows
runner.FULL_CONTEXT_WINDOW_SIZE  # 1M token limit
```

### Batch Processing

Use batch processing for efficiency:

```python
# Worker processes in batches
worker = EnrichmentWorker(batch_size=10)
results = await worker.process_batch(items)

# Batching reduces API calls and improves throughput
```

### Caching

Enable caching for repeated operations:

```python
# Context caching (automatic in Gemini 2.0+)
context.config.model.enable_caching = True

# Result caching for enrichments
enrichment_cache = {}
```

## Configuration

Pipeline behavior is controlled via configuration:

```toml
[pipeline]
window_size = 7
window_unit = "days"
max_workers = 4

[pipeline.enrichment]
enabled = true
max_urls_per_window = 5

[pipeline.profiles]
enabled = true
update_on_new_messages = true

[pipeline.banners]
enabled = true
batch_size = 5
```

See [Configuration Reference](../getting-started/configuration.md) for full details.
