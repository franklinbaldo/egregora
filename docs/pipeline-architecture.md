# Source-Agnostic Pipeline Architecture

## Overview

Egregora now features a **source-agnostic pipeline architecture** that separates input concerns from orchestration, enabling easy addition of new chat platforms (Slack, Discord, Telegram, etc.) without modifying the core processing pipeline.

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Raw Chat Export                                  │
│              (WhatsApp ZIP, Slack JSON, etc.)                       │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │   Source Adapter     │
                  │  (WhatsApp/Slack)    │
                  │                      │
                  │  • parse()           │
                  │  • extract_media()   │
                  │  • get_metadata()    │
                  └──────────┬───────────┘
                             │
                             ▼
           ┌─────────────────────────────────┐
           │  Intermediate Representation    │
           │        (IR Schema)              │
           │                                 │
           │  Standardized Ibis Table with:  │
           │  • timestamp                    │
           │  • date                         │
           │  • author                       │
           │  • message                      │
           │  • message_id                   │
           │  • original_line                │
           │  • tagged_line                  │
           └────────────┬────────────────────┘
                        │
                        ▼
           ┌──────────────────────────────┐
           │    Core Orchestrator         │
           │  (Source-Agnostic)           │
           └──────────┬───────────────────┘
                      │
       ┌──────────────┼──────────────┐
       │              │              │
       ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│Pipeline  │  │Pipeline  │  │Pipeline  │
│Stage 1   │→ │Stage 2   │→ │Stage 3   │
│          │  │          │  │          │
│Filtering │  │Enrichment│  │Writing   │
└──────────┘  └──────────┘  └──────────┘
       │              │              │
       └──────────────┴──────────────┘
                      │
                      ▼
           ┌──────────────────────────┐
           │      Final Output        │
           │  • Blog posts (MD)       │
           │  • Author profiles       │
           │  • Media files           │
           │  • RAG vectors           │
           └──────────────────────────┘
```

## Key Components

### 1. Intermediate Representation (IR)

The **IR Schema** is the standardized data format that all sources must produce:

```python
IR_SCHEMA = {
    "timestamp": Timestamp(timezone=DEFAULT_TIMEZONE, scale=9),
    "date": Date(),
    "author": String(),
    "message": String(),
    "original_line": String(),
    "tagged_line": String(),
    "message_id": String(nullable=True),
}
```

**Purpose**: Ensures all pipeline stages can work with any source without modification.

**Contract**: All source adapters must produce Ibis tables conforming to this schema.

### 2. Source Adapters

**Abstract Interface**: `SourceAdapter`

**Required Methods**:
- `parse(input_path, timezone) → Table`: Convert raw export to IR-compliant table
- `extract_media(input_path, output_dir) → MediaMapping`: Extract media files (optional)
- `get_metadata(input_path) → dict`: Extract source metadata (optional)

**Properties**:
- `source_name`: Human-readable name (e.g., "WhatsApp")
- `source_identifier`: CLI identifier (e.g., "whatsapp")

**Available Adapters**:
- `WhatsAppAdapter`: Production-ready adapter for WhatsApp ZIP exports
- `SlackAdapter`: Stub/template adapter for Slack exports

### 3. Pipeline Stages

**Abstract Interface**: `PipelineStage`

**Required Methods**:
- `process(data, context) → StageResult`: Execute transformation
- `validate_input(data, context) → (bool, errors)`: Validate inputs (optional)

**Properties**:
- `stage_name`: Human-readable name
- `stage_identifier`: Unique identifier for checkpoints

**Current Stages**:
- `FilteringStage`: Remove unwanted messages, apply date filters
- *(More stages coming in future iterations)*

### 4. Core Orchestrator

The **CoreOrchestrator** is the source-agnostic execution engine:

```python
from egregora.pipeline import CoreOrchestrator, PipelineConfig
from egregora.adapters import get_adapter

# Get adapter
adapter = get_adapter("whatsapp")

# Configure pipeline
config = PipelineConfig(
    input_path=Path("export.zip"),
    output_dir=Path("output"),
    period="day",
)

# Create and run orchestrator
stages = [FilteringStage(config), ...]
orchestrator = CoreOrchestrator(adapter, stages)
result = orchestrator.run(config)
```

## Usage

### Command-Line Interface

The CLI now supports source selection via the `--source` flag:

```bash
# Process WhatsApp export (default)
egregora process export.zip --output output/

# Explicitly specify source
egregora process export.zip --source whatsapp --output output/

# Process Slack export (when implemented)
egregora process slack-export.json --source slack --output output/
```

### Adding a New Source

To add support for a new chat platform:

#### 1. Create Adapter Class

```python
# src/egregora/adapters/discord.py

from egregora.pipeline.adapters import SourceAdapter
from egregora.pipeline.ir import create_ir_table

class DiscordAdapter(SourceAdapter):
    @property
    def source_name(self) -> str:
        return "Discord"

    @property
    def source_identifier(self) -> str:
        return "discord"

    def parse(self, input_path, *, timezone=None, **kwargs):
        # 1. Read Discord export format
        raw_messages = self._read_discord_export(input_path)

        # 2. Convert to IR format
        ir_data = []
        for msg in raw_messages:
            ir_data.append({
                "timestamp": msg["timestamp"],
                "author": msg["author"]["username"],
                "message": msg["content"],
                # ... map other fields
            })

        # 3. Create IR-compliant table
        table = ibis.memtable(ir_data)
        return create_ir_table(table, timezone=timezone)
```

#### 2. Register Adapter

```python
# src/egregora/adapters/__init__.py

from egregora.adapters.discord import DiscordAdapter

ADAPTER_REGISTRY = {
    "whatsapp": WhatsAppAdapter,
    "slack": SlackAdapter,
    "discord": DiscordAdapter,  # Add new adapter
}
```

#### 3. Use Immediately

```bash
egregora process discord-export.json --source discord
```

**That's it!** No changes needed to:
- Core pipeline stages
- Orchestrator logic
- Output generation
- RAG indexing

## Benefits

### ✅ Source Decoupling
- Add new sources without modifying core pipeline
- Test sources independently

### ✅ Standardization
- Consistent behavior across all sources
- Privacy filters, enrichment, and output work uniformly

### ✅ Maintainability
- Clear separation of concerns
- Each component has a single responsibility

### ✅ Testability
- Contract tests ensure adapter compliance
- Stage tests independent of source

### ✅ Extensibility
- New stages can be added without touching adapters
- New adapters work with existing stages

## Migration from Old Architecture

### Before (Monolithic)

```python
# Old: WhatsApp-specific pipeline
process_whatsapp_export(
    zip_path=Path("export.zip"),
    output_dir=Path("output"),
    # ... many parameters
)
```

### After (Source-Agnostic)

```python
# New: Works with any source
run_source_pipeline(
    source="whatsapp",  # or "slack", "discord", etc.
    input_path=Path("export.zip"),
    output_dir=Path("output"),
    # ... same parameters
)
```

The CLI automatically uses the new architecture with full backward compatibility for WhatsApp exports.

## Testing

### IR Schema Contract Tests

```bash
uv run pytest tests/unit/test_pipeline_ir.py -v
```

Validates:
- IR schema structure
- Schema validation logic
- IR table creation

### Adapter Contract Tests

```bash
uv run pytest tests/unit/test_adapters.py -v
```

Validates:
- All adapters implement required methods
- Adapters produce valid IR-compliant tables
- Adapter metadata is correct

### Integration Testing

Integration tests validate end-to-end pipeline execution with real or realistic data.

#### Test Fixtures

Create fixture exports for testing:

```
tests/fixtures/
├── whatsapp/
│   ├── minimal-export.zip      # Small test export
│   ├── medium-export.zip        # Moderate size with media
│   └── edge-cases.zip           # Edge cases (empty messages, special chars)
├── slack/
│   ├── minimal-export.json
│   └── channel-export/          # Multi-channel export
└── expected/
    ├── whatsapp-minimal/        # Expected outputs
    │   ├── posts/
    │   └── profiles/
    └── slack-minimal/
```

#### End-to-End Pipeline Tests

Test complete pipeline execution:

```python
# tests/integration/test_pipeline_e2e.py

import pytest
from pathlib import Path
from egregora.pipeline.runner import run_source_pipeline

class TestWhatsAppPipeline:
    """Integration tests for WhatsApp pipeline."""

    def test_minimal_export_produces_output(self, tmp_path):
        """Test pipeline with minimal WhatsApp export."""
        fixture = Path("tests/fixtures/whatsapp/minimal-export.zip")
        output_dir = tmp_path / "output"

        result = run_source_pipeline(
            source="whatsapp",
            input_path=fixture,
            output_dir=output_dir,
            enable_enrichment=False,  # Fast test
        )

        # Verify outputs exist
        assert (output_dir / "posts").exists()
        assert (output_dir / "profiles").exists()
        assert result["status"] == "success"

    def test_output_matches_golden_fixture(self, tmp_path):
        """Test output matches expected golden fixture."""
        fixture = Path("tests/fixtures/whatsapp/minimal-export.zip")
        expected = Path("tests/fixtures/expected/whatsapp-minimal")
        output_dir = tmp_path / "output"

        run_source_pipeline(
            source="whatsapp",
            input_path=fixture,
            output_dir=output_dir,
            enable_enrichment=False,
        )

        # Compare outputs (normalized diff for non-deterministic fields)
        assert_outputs_match(output_dir, expected)
```

#### Performance Testing

Track pipeline performance over time:

```python
# tests/integration/test_performance.py

import pytest
import time
from egregora.pipeline.runner import run_source_pipeline

@pytest.mark.slow
class TestPipelinePerformance:
    """Performance benchmarks for pipeline."""

    def test_medium_export_processing_time(self, benchmark, tmp_path):
        """Benchmark processing time for medium export."""
        fixture = Path("tests/fixtures/whatsapp/medium-export.zip")

        def run_pipeline():
            return run_source_pipeline(
                source="whatsapp",
                input_path=fixture,
                output_dir=tmp_path,
                enable_enrichment=False,
            )

        result = benchmark(run_pipeline)
        assert result["status"] == "success"

    def test_memory_usage_stays_bounded(self, tmp_path):
        """Test pipeline doesn't leak memory on large exports."""
        # Monitor memory during processing
        # Assert peak memory < threshold
        pass
```

#### Adapter-Specific Integration Tests

Test source-specific behavior:

```python
# tests/integration/test_whatsapp_adapter.py

class TestWhatsAppAdapterIntegration:
    """Integration tests for WhatsApp adapter."""

    def test_parse_real_export_structure(self):
        """Test parsing actual WhatsApp export structure."""
        from egregora.adapters import WhatsAppAdapter

        adapter = WhatsAppAdapter()
        table = adapter.parse(
            Path("tests/fixtures/whatsapp/minimal-export.zip"),
            timezone="UTC",
        )

        # Verify parsed structure
        assert table.count().execute() > 0
        assert "timestamp" in table.columns
        assert "message" in table.columns

    def test_media_references_in_messages(self):
        """Test media references are correctly handled."""
        # Test that media references in messages are preserved
        pass
```

#### Running Integration Tests

```bash
# Run all integration tests
uv run pytest tests/integration/ -v

# Run only fast integration tests (exclude slow benchmarks)
uv run pytest tests/integration/ -v -m "not slow"

# Run with coverage
uv run pytest tests/integration/ --cov=egregora --cov-report=html
```

#### CI/CD Integration

Add to `.github/workflows/test.yml`:

```yaml
integration-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    - name: Install dependencies
      run: uv sync
    - name: Run integration tests
      run: uv run pytest tests/integration/ -v
      env:
        GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
```

#### Best Practices

1. **Use small fixtures**: Keep test exports minimal for fast execution
2. **Mock external calls**: Mock LLM API calls to avoid rate limits and costs
3. **Test edge cases**: Include exports with empty messages, special characters, etc.
4. **Version fixtures**: Track fixture versions alongside code changes
5. **Automated golden fixture updates**: Script to regenerate expected outputs when intentionally changing behavior

## Future Enhancements

### Phase 1 (Current)
- ✅ IR schema definition
- ✅ SourceAdapter interface
- ✅ WhatsApp adapter
- ✅ Slack stub adapter
- ✅ Core orchestrator
- ✅ CLI integration
- ✅ Contract tests

### Phase 2 (Planned)
- [ ] Full Slack adapter implementation
- [ ] Discord adapter
- [ ] Telegram adapter
- [ ] Additional pipeline stages (EnrichmentStage, WritingStage)
- [ ] Stage-level caching and checkpointing
- [ ] Parallel stage execution

### Phase 3 (Future)
- [ ] Plugin system for custom adapters
- [ ] Dynamic adapter loading
- [ ] Adapter configuration via mkdocs.yml
- [ ] Streaming/incremental processing
- [ ] Multi-source aggregation

## See Also

- [API Reference](api/pipeline.md)
- [Adapter Development Guide](guides/adapter-development.md)
- [Stage Development Guide](guides/stage-development.md)
- [Testing Guide](guides/testing.md)
