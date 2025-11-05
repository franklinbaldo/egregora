# Configuration Objects Refactoring Guide

**Status**: In Progress
**Goal**: Replace long parameter lists (10+ params) with structured config objects

---

## Problem

Many functions in the codebase have 10-16 parameters, making them:
- Hard to call correctly
- Difficult to test
- Prone to parameter order mistakes
- Challenging to extend with new options

### Worst Offenders

| Function | Parameters | Status |
|----------|-----------|--------|
| `pipeline.py:_process_whatsapp_export` | 16 | ✅ Config available |
| `pipeline.py:process_whatsapp_export` | 15 | ✅ Config available |
| `agents/writer/core.py:_process_tool_calls` | 14 | 📝 Planned |
| `enrichment/core.py:enrich_table` | 13 | 📝 Planned |
| `cli.py:process` | 13 | ✅ Config available |

---

## Solution: Configuration Objects

Use dataclasses to group related parameters into cohesive configuration objects.

### Before
```python
def process_whatsapp_export(
    zip_path: Path,
    output_dir: Path = Path("output"),
    period: str = "day",
    enable_enrichment: bool = True,
    from_date=None,
    to_date=None,
    timezone=None,
    gemini_api_key: str | None = None,
    model: str | None = None,
    resume: bool = True,
    batch_threshold: int = 10,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
    # 15 parameters! 😱
    pass
```

### After
```python
from egregora.config import ProcessConfig

def process_whatsapp_export(
    config: ProcessConfig,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
    # Only 2 parameters! ✅
    # All configuration is in structured config object
    pass

# Usage
config = ProcessConfig(
    zip_file=Path("export.zip"),
    output_dir=Path("output"),
    period="week",
    enable_enrichment=True,
    resume=True,
    batch_threshold=10,
)

result = process_whatsapp_export(config)
```

---

## Available Config Objects

### 1. `ProcessConfig` ✅ **Ready to Use**

**Location**: `egregora.config.types.ProcessConfig`

**Purpose**: Complete pipeline configuration for WhatsApp export processing

**Fields**:
```python
@dataclass
class ProcessConfig:
    # Required
    zip_file: Path
    output_dir: Path

    # Optional with defaults
    period: str = "day"                      # Time grouping
    enable_enrichment: bool = True           # Enable LLM enrichment
    from_date: date | None = None           # Filter start date
    to_date: date | None = None             # Filter end date
    timezone: str | None = None             # Timezone for parsing
    gemini_key: str | None = None           # API key
    model: str | None = None                # Model override
    debug: bool = False                     # Debug logging
    retrieval_mode: str = "ann"             # RAG retrieval mode
    retrieval_nprobe: int | None = None     # ANN tuning
    retrieval_overfetch: int | None = None  # ANN tuning
    resume: bool = True                     # Checkpoint resume
    batch_threshold: int = 10               # Batching threshold
```

**Example**:
```python
from pathlib import Path
from egregora.config import ProcessConfig

# Create with sensible defaults
config = ProcessConfig(
    zip_file=Path("my-export.zip"),
    output_dir=Path("./my-site"),
)

# Or customize specific options
config = ProcessConfig(
    zip_file=Path("my-export.zip"),
    output_dir=Path("./my-site"),
    period="week",              # Group by week instead of day
    enable_enrichment=False,    # Skip LLM enrichment
    from_date=date(2024, 1, 1), # Only process 2024+
    retrieval_mode="flat",       # Use exact search
)
```

### 2. `PipelineEnrichmentConfig` ✅ **Ready to Use**

**Location**: `egregora.config.pipeline.PipelineEnrichmentConfig`

**Purpose**: Enrichment-specific configuration for fine-grained control

**Fields**:
```python
@dataclass
class PipelineEnrichmentConfig:
    batch_threshold: int = 10      # Min items for batching
    max_enrichments: int = 500     # Max enrichments per period
    enable_url: bool = True        # Enrich URLs
    enable_media: bool = True      # Enrich media
```

**Example**:
```python
from egregora.config import PipelineEnrichmentConfig

# Light enrichment for testing
test_config = PipelineEnrichmentConfig(
    max_enrichments=10,
    enable_url=True,
    enable_media=False,
)

# Heavy enrichment for production
prod_config = PipelineEnrichmentConfig(
    max_enrichments=1000,
    batch_threshold=50,
    enable_url=True,
    enable_media=True,
)
```

### 3. `WriterConfig` ✅ **Ready to Use**

**Location**: `egregora.config.types.WriterConfig`

**Purpose**: Post writing configuration

**Fields**:
```python
@dataclass
class WriterConfig:
    posts_dir: Path
    profiles_dir: Path
    rag_dir: Path
    model_config: ModelConfig | None = None
    enable_rag: bool = True
```

---

## Migration Path

### Step 1: Add Config Parameter (Backward Compatible)

```python
# Before
def my_function(
    param1: str,
    param2: int,
    param3: bool,
    param4: str,
    # ... 10 more params
) -> Result:
    pass

# After (supports both old and new style)
def my_function(
    param1: str = None,
    param2: int = None,
    # ... other params
    config: MyConfig | None = None,  # NEW: config object
) -> Result:
    # Use config if provided, otherwise fall back to individual params
    if config:
        param1 = param1 or config.param1
        param2 = param2 or config.param2
        # ...

    # Rest of function unchanged
    pass
```

### Step 2: Deprecate Old Parameters

Add deprecation warnings for individual parameters:

```python
import warnings

def my_function(
    param1: str = None,
    param2: int = None,
    config: MyConfig | None = None,
) -> Result:
    if param1 is not None or param2 is not None:
        warnings.warn(
            "Passing individual parameters is deprecated. "
            "Use MyConfig object instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    # Use config-first approach
    final_param1 = config.param1 if config else param1
    # ...
```

### Step 3: Remove Old Parameters

After deprecation period, simplify to config-only:

```python
def my_function(config: MyConfig) -> Result:
    # Clean, simple signature!
    pass
```

---

## Benefits Demonstrated

### ✅ Type Safety

```python
# Before: Easy to mix up parameter order
result = process(
    Path("file.zip"),
    "week",        # Oops, forgot output_dir!
    True,
    # ...
)

# After: IDE autocomplete + type checking
config = ProcessConfig(
    zip_file=Path("file.zip"),
    output_dir=Path("out"),  # Compiler error if missing!
    period="week",
)
```

### ✅ Easy Testing

```python
# Before: Tedious to set up tests
def test_processing():
    result = process_whatsapp_export(
        Path("test.zip"),
        Path("test-out"),
        "day",
        True,
        None,
        None,
        None,
        "fake-key",
        "fake-model",
        False,
        5,
        "flat",
        None,
        None,
        mock_client,
    )

# After: Clear test setup
def test_processing():
    config = ProcessConfig(
        zip_file=Path("test.zip"),
        output_dir=Path("test-out"),
        gemini_key="fake-key",
        resume=False,
    )
    result = process_whatsapp_export(config, mock_client)
```

### ✅ Easy to Extend

```python
# Adding a new option:

# Before: Change signature everywhere
def process(..., new_option: bool = False):  # Update 20+ call sites!

# After: Just add to config
@dataclass
class ProcessConfig:
    # ... existing fields ...
    new_option: bool = False  # Single place to add, all call sites work!
```

---

## Next Steps

1. ✅ **Done**: Create config dataclasses (`ProcessConfig`, `PipelineEnrichmentConfig`)
2. 📝 **In Progress**: Refactor `_process_whatsapp_export` to use configs
3. 📝 **Planned**: Refactor `_process_tool_calls` (14 params)
4. 📝 **Planned**: Refactor `enrich_table` (13 params)
5. 📝 **Planned**: Create `ToolCallContext` for writer agent

---

## References

- Original analysis: `docs/code-smells-analysis.md` (Section 3: Long Parameter Lists)
- Python dataclasses: https://docs.python.org/3/library/dataclasses.html
- Configuration pattern: https://refactoring.guru/introduce-parameter-object
