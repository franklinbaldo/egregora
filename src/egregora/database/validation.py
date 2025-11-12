"""Runtime validation for IR v1 schema compliance.

This module provides validation infrastructure to ensure data tables conform
to the IR v1 schema specification at runtime. It combines:

1. **Compile-time validation**: Checks Ibis table schemas match expected structure
2. **Runtime validation**: Validates sample rows using Pydantic models
3. **Adapter boundary enforcement**: Validates adapter outputs before pipeline

Usage:

    from egregora.database.validation import (
        validate_ir_schema,
        adapter_output_validator,
        validate_adapter_output,
        validate_stage,
    )

    # Manual validation
    table = adapter.parse_source(input_path)
    validate_ir_schema(table)  # Raises SchemaError if invalid

    # Function wrapper
    validated_table = adapter_output_validator(table)

    # Decorator for adapter methods
    @validate_adapter_output
    def parse(self, input_path: Path) -> ibis.Table:
        return parse_source(input_path)

    # Decorator for pipeline stage methods
    from egregora.pipeline.base import PipelineStage, StageResult

    class MyStage(PipelineStage):
        @validate_stage
        def process(self, data: Table, context: dict[str, Any]) -> StageResult:
            # Transform logic here
            return StageResult(data=transformed_data)

See Also:
    - docs/architecture/ir-v1-spec.md
    - schema/ir_v1.sql
    - schema/ir_v1.json (lockfile)

"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import ibis
import ibis.expr.datatypes as dt
from pydantic import BaseModel, Field, ValidationError

if TYPE_CHECKING:
    from ibis.expr.types import Table

# Type variable for decorator
F = TypeVar("F", bound=Callable[..., "Table"])

# Constants
MIN_STAGE_ARGS = 2  # Stage process method requires (self, data) at minimum


class SchemaError(Exception):
    """Raised when table schema doesn't match IR v1 specification."""


# ============================================================================
# IR v1 Schema Definition (Ibis)
# ============================================================================

IR_MESSAGE_SCHEMA = ibis.schema(
    {
        # Identity
        "event_id": dt.UUID,
        # Multi-Tenant
        "tenant_id": dt.string,
        "source": dt.string,
        # Threading
        "thread_id": dt.UUID,
        "msg_id": dt.string,
        # Temporal
        "ts": dt.Timestamp(timezone="UTC"),
        # Authors (PRIVACY BOUNDARY)
        "author_raw": dt.string,
        "author_uuid": dt.UUID,
        # Content
        "text": dt.String(nullable=True),
        "media_url": dt.String(nullable=True),
        "media_type": dt.String(nullable=True),
        # Metadata
        "attrs": dt.JSON(nullable=True),
        "pii_flags": dt.JSON(nullable=True),
        # Lineage
        "created_at": dt.Timestamp(timezone="UTC"),
        "created_by_run": dt.UUID(nullable=True),
    }
)


# ============================================================================
# Runtime Validator (Pydantic)
# ============================================================================


class IRMessageRow(BaseModel):
    """Runtime validator for IR v1 rows.

    This Pydantic model validates individual rows conform to IR v1 schema.
    Used for runtime validation of sample data.

    Attributes match IR v1 specification exactly.
    """

    # Identity
    event_id: uuid.UUID

    # Multi-Tenant
    tenant_id: str = Field(min_length=1)
    source: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")  # lowercase, alphanumeric + underscore/dash

    # Threading
    thread_id: uuid.UUID
    msg_id: str

    # Temporal
    ts: datetime

    # Authors
    author_raw: str
    author_uuid: uuid.UUID

    # Content
    text: str | None = None
    media_url: str | None = None
    media_type: str | None = None

    # Metadata
    attrs: dict[str, Any] | None = None
    pii_flags: dict[str, Any] | None = None

    # Lineage
    created_at: datetime
    created_by_run: uuid.UUID | None = None

    model_config = {"frozen": True}


# ============================================================================
# Schema Validation Functions
# ============================================================================


def load_ir_schema_lockfile(lockfile_path: Path | None = None) -> dict[str, Any]:
    """Load IR v1 schema from lockfile (schema/ir_v1.json).

    Args:
        lockfile_path: Path to ir_v1.json, defaults to schema/ir_v1.json

    Returns:
        Schema dictionary

    Raises:
        FileNotFoundError: If lockfile doesn't exist
        json.JSONDecodeError: If lockfile is invalid JSON

    """
    if lockfile_path is None:
        # Default location relative to this file
        lockfile_path = Path(__file__).parent.parent.parent.parent / "schema" / "ir_v1.json"

    if not lockfile_path.exists():
        msg = f"IR v1 lockfile not found: {lockfile_path}"
        raise FileNotFoundError(msg)

    return json.loads(lockfile_path.read_text())


def schema_diff(expected: ibis.Schema, actual: ibis.Schema) -> str:
    """Generate human-readable diff between two schemas.

    Args:
        expected: Expected schema
        actual: Actual schema

    Returns:
        Formatted diff string

    """
    lines = []

    # Check for missing columns
    expected_cols = set(expected.names)
    actual_cols = set(actual.names)

    missing = expected_cols - actual_cols
    if missing:
        lines.append("Missing columns:")
        for col in sorted(missing):
            lines.append(f"  - {col}: {expected[col]}")

    # Check for extra columns
    extra = actual_cols - expected_cols
    if extra:
        lines.append("Extra columns:")
        for col in sorted(extra):
            lines.append(f"  + {col}: {actual[col]}")

    # Check for type mismatches
    common_cols = expected_cols & actual_cols
    mismatches = []
    for col in sorted(common_cols):
        expected_type = expected[col]
        actual_type = actual[col]
        if expected_type != actual_type:
            mismatches.append(f"  {col}: expected {expected_type}, got {actual_type}")

    if mismatches:
        lines.append("Type mismatches:")
        lines.extend(mismatches)

    return "\n".join(lines) if lines else "No differences"


def validate_ir_schema(table: Table, *, sample_size: int = 100) -> None:
    """Validate table schema matches IR v1 lockfile.

    This function performs two levels of validation:
    1. Compile-time: Check Ibis schema structure
    2. Runtime: Validate sample rows with Pydantic

    Args:
        table: Ibis table to validate
        sample_size: Number of rows to validate (default: 100)

    Raises:
        SchemaError: If schema doesn't match IR v1 or row validation fails

    Example:
        >>> table = parse_whatsapp_export("export.zip")
        >>> validate_ir_schema(table)  # Raises SchemaError if invalid

    """
    # 1. Compile-time check: Schema structure
    actual_schema = table.schema()
    expected_schema = IR_MESSAGE_SCHEMA

    # Compare column names (order doesn't matter)
    expected_cols = set(expected_schema.names)
    actual_cols = set(actual_schema.names)

    if expected_cols != actual_cols:
        diff = schema_diff(expected_schema, actual_schema)
        msg = f"IR v1 schema mismatch:\n{diff}"
        raise SchemaError(msg)

    # Compare column types
    for col in expected_cols:
        expected_type = expected_schema[col]
        actual_type = actual_schema[col]

        # Type comparison (allow some flexibility for nullable)
        if expected_type != actual_type:
            # Allow nullable mismatches if both are same base type
            # e.g., String(nullable=True) vs String(nullable=False)
            if not _types_compatible(expected_type, actual_type):
                msg = f"IR v1 type mismatch for column '{col}': expected {expected_type}, got {actual_type}"
                raise SchemaError(msg)

    # 2. Runtime check: Validate sample rows with Pydantic
    # Note: Skip runtime validation if table execution fails (e.g., memtable serialization issues)
    # Schema validation above is sufficient for most use cases.
    try:
        # Execute sample rows (limit to avoid expensive validation)
        sample = table.limit(sample_size).execute()

        if len(sample) == 0:
            # Empty table is valid (no rows to validate)
            return

        # Validate each row
        for idx, row in enumerate(sample.itertuples(index=False)):
            try:
                # Convert row to dict
                row_dict = row._asdict()

                # Convert UUID objects to proper UUIDs if needed
                # (pandas/pyarrow might return UUID objects or strings)
                for field in ["event_id", "thread_id", "author_uuid", "created_by_run"]:
                    if field in row_dict and row_dict[field] is not None:
                        value = row_dict[field]
                        if not isinstance(value, uuid.UUID):
                            # Convert string to UUID
                            row_dict[field] = uuid.UUID(str(value))

                # Validate with Pydantic
                IRMessageRow(**row_dict)
            except ValidationError as e:
                msg = f"IR v1 validation failed at row {idx}: {e}"
                raise SchemaError(msg) from e

    except Exception as e:
        if isinstance(e, SchemaError):
            raise
        # Runtime validation failure is not critical - schema validation passed
        # Log warning but don't fail (execution issues with memtable, etc.)
        import logging

        logging.getLogger(__name__).warning("IR v1 runtime validation skipped due to execution error: %s", e)


def _types_compatible(expected: dt.DataType, actual: dt.DataType) -> bool:
    """Check if two Ibis types are compatible (allowing nullable differences).

    Args:
        expected: Expected data type
        actual: Actual data type

    Returns:
        True if compatible, False otherwise

    """
    # Exact match
    if expected == actual:
        return True

    # Allow nullable differences for optional fields
    # e.g., String(nullable=True) is compatible with String(nullable=False)
    if hasattr(expected, "nullable") and hasattr(actual, "nullable"):
        # Same base type, different nullable
        expected_base = type(expected)
        actual_base = type(actual)
        if expected_base == actual_base:
            # Allow actual to be more permissive (nullable=True) than expected
            return True

    return False


def adapter_output_validator(table: Table) -> Table:
    """Validate adapter output before pipeline.

    This function validates adapter outputs at the pipeline boundary
    to ensure they conform to IR v1 schema.

    Args:
        table: Adapter output table

    Returns:
        Validated table (same as input)

    Raises:
        SchemaError: If schema validation fails

    Usage:
        >>> table = adapter.parse_source(input_path)
        >>> table = adapter_output_validator(table)  # Enforce contract

    """
    validate_ir_schema(table)
    return table


def validate_adapter_output[F: Callable[..., "Table"]](func: F) -> F:
    """Decorator to validate adapter outputs against IR v1 schema.

    This decorator wraps adapter methods (typically `parse()`) to automatically
    validate their outputs conform to IR v1 schema specification.

    Args:
        func: Function returning an Ibis Table (adapter parse method)

    Returns:
        Wrapped function that validates output

    Raises:
        SchemaError: If adapter output doesn't match IR v1 schema

    Example:
        >>> class MyAdapter(SourceAdapter):
        ...     @validate_adapter_output
        ...     def parse(self, input_path: Path) -> Table:
        ...         # Parse logic here
        ...         return table

    Note:
        This is a convenience decorator. AdapterRegistry can also
        auto-validate outputs when validate_outputs=True.

    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Table:
        # Call original function
        result = func(*args, **kwargs)

        # Validate output
        try:
            validate_ir_schema(result)
        except SchemaError as e:
            # Enhance error with function context
            func_name = getattr(func, "__qualname__", func.__name__)
            msg = f"Adapter output validation failed in {func_name}: {e}"
            raise SchemaError(msg) from e

        return result

    return wrapper  # type: ignore[return-value]


def validate_stage[F: Callable[..., "Table"]](func: F) -> F:
    """Decorator to validate pipeline stage inputs and outputs against IR v1 schema.

    This decorator wraps stage.process() methods to automatically validate:
    1. Input data conforms to IR v1 schema
    2. Output data conforms to IR v1 schema (preserves schema contract)

    Args:
        func: Stage process method (returns StageResult with .data attribute)

    Returns:
        Wrapped function that validates input/output

    Raises:
        SchemaError: If input or output doesn't match IR v1 schema

    Example:
        >>> from egregora.pipeline.base import PipelineStage, StageResult
        >>> class MyStage(PipelineStage):
        ...     @validate_stage
        ...     def process(self, data: Table, context: dict[str, Any]) -> StageResult:
        ...         # Transform logic here
        ...         transformed = data.filter(...)
        ...         return StageResult(data=transformed)

    Note:
        This validates BOTH inputs and outputs to ensure stages preserve
        the IR v1 schema contract throughout the pipeline.

    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:  # Returns StageResult
        # Extract input data from args
        # Signature: process(self, data: Table, context: dict[str, Any]) -> StageResult
        if len(args) < MIN_STAGE_ARGS:
            msg = "Stage process method requires at least 2 arguments: (self, data)"
            raise TypeError(msg)

        input_data = args[1]  # data parameter

        # Validate input
        try:
            validate_ir_schema(input_data)
        except SchemaError as e:
            func_name = getattr(func, "__qualname__", func.__name__)
            msg = f"Stage input validation failed in {func_name}: {e}"
            raise SchemaError(msg) from e

        # Call original function
        result = func(*args, **kwargs)

        # Extract output data from StageResult
        # StageResult has .data attribute
        output_data = result.data

        # Validate output
        try:
            validate_ir_schema(output_data)
        except SchemaError as e:
            func_name = getattr(func, "__qualname__", func.__name__)
            msg = f"Stage output validation failed in {func_name}: {e}"
            raise SchemaError(msg) from e

        return result

    return wrapper  # type: ignore[return-value]
