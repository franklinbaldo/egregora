# Stage Validation (Priority C.3)

**Status**: Implemented (2025-01-09)
**Module**: `egregora.database.validation`

## Overview

The **@validate_stage** decorator ensures pipeline stages preserve IR v1 schema conformance throughout transformations. It validates both inputs and outputs to catch schema violations early.

## Why Stage Validation?

**Problems it solves:**

1. **Schema drift**: Stages inadvertently drop required columns or change types
2. **Silent failures**: Invalid transformations that don't raise errors immediately
3. **Pipeline integrity**: Ensure all stages honor the IR v1 contract
4. **Early detection**: Catch schema violations before they propagate

**Benefits:**

1. **Automatic validation**: No manual schema checks needed
2. **Clear error messages**: Helpful context when validation fails
3. **Zero-cost abstraction**: Only validates during execution, no runtime overhead otherwise
4. **Consistency**: All stages follow same validation pattern

## Architecture

```python
from egregora.database.validation import validate_stage
from egregora.pipeline.base import PipelineStage, StageResult

class MyStage(PipelineStage):
    @validate_stage
    def process(self, data: Table, context: dict[str, Any]) -> StageResult:
        # Input validated automatically
        transformed = data.filter(...)
        # Output validated automatically
        return StageResult(data=transformed)
```

## Usage

### Basic Usage

**Decorate stage.process() method:**

```python
from typing import Any
from ibis.expr.types import Table
from egregora.database.validation import validate_stage
from egregora.pipeline.base import PipelineStage, StageConfig, StageResult

class FilteringStage(PipelineStage):
    """Filter messages while preserving IR schema."""

    def __init__(self, config: StageConfig) -> None:
        super().__init__(config)

    @property
    def stage_name(self) -> str:
        return "Message Filtering"

    @property
    def stage_identifier(self) -> str:
        return "filtering"

    @validate_stage
    def process(self, data: Table, context: dict[str, Any]) -> StageResult:
        """Filter unwanted messages."""
        # Input is validated here (before this line executes)

        # Safe transformations (preserve schema)
        filtered = data.filter(data.text.notnull())
        filtered = filtered.filter(~data.text.startswith("/egregora"))

        # Output is validated here (before return)
        return StageResult(
            data=filtered,
            metrics={"messages_filtered": data.count().execute() - filtered.count().execute()}
        )
```

### What Gets Validated

**Input validation (before stage execution):**
- All required IR v1 columns present
- Column types match IR v1 schema
- Nullable/non-nullable constraints respected

**Output validation (after stage execution):**
- Same checks as input
- Ensures transformations preserve schema contract

### Validation Modes

**Two-level validation (same as adapter validation):**

1. **Compile-time**: Checks Ibis schema structure (column names, types)
2. **Runtime**: Validates sample rows with Pydantic (value constraints)

Both levels run automatically via @validate_stage.

## Error Handling

**What happens when validation fails?**

```python
# Example: Stage that breaks schema
class BrokenStage(PipelineStage):
    @validate_stage
    def process(self, data: Table, context: dict[str, Any]) -> StageResult:
        # Drop required columns (BREAKS SCHEMA)
        broken = data.select("event_id", "text")
        return StageResult(data=broken)

# When executed:
>>> stage.process(valid_table, {})
SchemaError: Stage output validation failed in BrokenStage.process: IR v1 schema mismatch:
Missing columns:
  - tenant_id: string
  - source: string
  - thread_id: uuid
  - msg_id: string
  ...
```

**Error message includes:**
- Stage class and method name
- Whether input or output failed
- Detailed schema diff (missing/extra columns, type mismatches)

## Common Transformations

**Safe transformations (preserve schema):**

```python
@validate_stage
def process(self, data: Table, context: dict[str, Any]) -> StageResult:
    # ✅ Filtering
    result = data.filter(data.text.notnull())

    # ✅ Ordering
    result = result.order_by(data.ts)

    # ✅ Limiting
    result = result.limit(100)

    # ✅ Window functions (don't change schema)
    result = result.mutate(
        row_num=ibis.row_number().over(
            ibis.window(group_by="thread_id", order_by="ts")
        )
    )

    return StageResult(data=result)
```

**Unsafe transformations (break schema):**

```python
@validate_stage
def process(self, data: Table, context: dict[str, Any]) -> StageResult:
    # ❌ Dropping required columns
    result = data.select("event_id", "text")  # BREAKS SCHEMA

    # ❌ Renaming columns
    result = data.rename(event_id="id")  # BREAKS SCHEMA

    # ❌ Changing types
    result = data.mutate(ts=data.ts.cast("string"))  # BREAKS SCHEMA

    return StageResult(data=result)
```

## Testing

**Test stages with @validate_stage:**

```python
import uuid
from datetime import datetime
import ibis
import pytest
from egregora.database.validation import SchemaError, validate_stage
from egregora.pipeline.base import StageResult

def test_my_stage_preserves_schema():
    """Test that MyStage preserves IR v1 schema."""
    # Create valid IR v1 test data
    data = {
        "event_id": [str(uuid.uuid4())],
        "tenant_id": ["test-tenant"],
        "source": ["whatsapp"],
        "thread_id": [str(uuid.uuid4())],
        "msg_id": ["msg1"],
        "ts": [datetime(2025, 1, 1, 10, 0)],
        "author_raw": ["Alice"],
        "author_uuid": [str(uuid.uuid4())],
        "text": ["Hello"],
        "media_url": [None],
        "media_type": [None],
        "attrs": [None],
        "pii_flags": [None],
        "created_at": [datetime(2025, 1, 1, 10, 0)],
        "created_by_run": [None],
    }
    schema = {
        "event_id": "uuid",
        "tenant_id": "string",
        "source": "string",
        "thread_id": "uuid",
        "msg_id": "string",
        "ts": "timestamp",
        "author_raw": "string",
        "author_uuid": "uuid",
        "text": "string",
        "media_url": "string",
        "media_type": "string",
        "attrs": "json",
        "pii_flags": "json",
        "created_at": "timestamp",
        "created_by_run": "uuid",
    }
    table = ibis.memtable(data, schema=schema)

    # Stage should succeed
    config = StageConfig()
    stage = MyStage(config)
    result = stage.process(table, {})

    assert isinstance(result, StageResult)
    assert result.data is not None

def test_broken_stage_raises_schema_error():
    """Test that broken stages raise SchemaError."""
    # ... create valid table ...

    config = StageConfig()
    stage = BrokenStage(config)

    # Should raise on output validation
    with pytest.raises(SchemaError, match="output validation failed"):
        stage.process(table, {})
```

## Performance Considerations

**Validation overhead:**
- **Compile-time check**: Fast (schema structure comparison)
- **Runtime check**: Samples first 100 rows (configurable)
- **Total overhead**: ~10-50ms per stage execution

**When to skip validation:**
- Production deployments where schema is guaranteed
- High-frequency inner loops (use manual validation)

**How to skip validation (NOT recommended):**

```python
# Option 1: Don't use decorator (manual validation)
def process(self, data: Table, context: dict[str, Any]) -> StageResult:
    # No automatic validation
    result = transform(data)
    return StageResult(data=result)

# Option 2: Conditional validation in tests only
if os.getenv("VALIDATE_STAGES"):
    @validate_stage
    def process(...):
        ...
```

## Integration with PipelineStage

**PipelineStage.validate_input():**

The base class already has a `validate_input()` method for custom validation:

```python
class PipelineStage(ABC):
    def validate_input(self, data: Table, context: dict[str, Any]) -> tuple[bool, list[str]]:
        """Override for custom validation."""
        return (True, [])
```

**@validate_stage vs validate_input():**

- **@validate_stage**: Validates IR v1 schema conformance (input + output)
- **validate_input()**: Custom business logic validation (e.g., "table must have >10 rows")

**Use both together:**

```python
class MyStage(PipelineStage):
    def validate_input(self, data: Table, context: dict[str, Any]) -> tuple[bool, list[str]]:
        """Custom validation: require minimum message count."""
        count = data.count().execute()
        if count < 10:
            return (False, [f"Need at least 10 messages, got {count}"])
        return (True, [])

    @validate_stage
    def process(self, data: Table, context: dict[str, Any]) -> StageResult:
        # IR validation happens automatically
        # Custom validation can be checked manually if needed
        is_valid, errors = self.validate_input(data, context)
        if not is_valid:
            raise ValueError(f"Invalid input: {errors}")

        # Transform...
        return StageResult(data=transformed)
```

## Migration Guide

**Before (no validation):**

```python
class OldStage(PipelineStage):
    def process(self, data: Table, context: dict[str, Any]) -> StageResult:
        # No schema validation
        result = data.filter(...)
        return StageResult(data=result)
```

**After (with validation):**

```python
from egregora.database.validation import validate_stage

class NewStage(PipelineStage):
    @validate_stage
    def process(self, data: Table, context: dict[str, Any]) -> StageResult:
        # Automatic input/output validation
        result = data.filter(...)
        return StageResult(data=result)
```

**Benefits:**
- Catches schema violations early
- Self-documenting (decorator signals conformance requirement)
- Consistent validation across all stages

## Roadmap Items Completed

- ✅ C.3: Validate All Stages Conform to IR
  - @validate_stage decorator for automatic validation
  - Two-level validation (compile-time + runtime)
  - Input and output validation
  - Helpful error messages with stage context
  - 7 comprehensive tests

## Related Documentation

- `src/egregora/database/validation.py` - Implementation (validate_stage decorator)
- `tests/unit/test_stage_validation.py` - Test suite (7 tests)
- `src/egregora/pipeline/base.py` - PipelineStage base class
- `docs/pipeline/view-registry.md` - ViewRegistry (C.1)
- `docs/database/storage-manager.md` - StorageManager (C.2)
- `ARCHITECTURE_ROADMAP.md` - Priority C specification

## Example: Filtering Stage with Validation

See `src/egregora/pipeline/stages/filtering.py` for a real-world example of a stage that can use @validate_stage decorator.

**Before adding decorator:**

```python
class FilteringStage(PipelineStage):
    def process(self, data: Table, context: dict[str, Any]) -> StageResult:
        # Manual schema checks scattered throughout
        filtered = data.filter(...)
        return StageResult(data=filtered)
```

**After adding decorator:**

```python
from egregora.database.validation import validate_stage

class FilteringStage(PipelineStage):
    @validate_stage
    def process(self, data: Table, context: dict[str, Any]) -> StageResult:
        # Automatic validation - no manual checks needed
        filtered = data.filter(...)
        return StageResult(data=filtered)
```

## See Also

- **Adapter validation**: `@validate_adapter_output` for source adapters
- **IR v1 schema**: `IR_V1_SCHEMA` in `src/egregora/database/validation.py`
- **Schema lockfile**: `schema/ir_v1.json` (canonical schema definition)
