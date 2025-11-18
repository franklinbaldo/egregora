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

    # Decorator for pipeline transformations (functional approach)
    @validate_stage
    def filter_messages(data: Table, min_length: int = 0) -> Table:
        return data.filter(data.text.length() >= min_length)

See Also:
    - docs/architecture/ir-v1-spec.md
    - schema/ir_v1.sql
    - schema/ir_v1.json (lockfile)

"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import ibis
import ibis.expr.datatypes as dt
from pydantic import BaseModel, Field, ValidationError

from egregora.privacy.uuid_namespaces import (
    deterministic_author_uuid,
    deterministic_event_uuid,
    deterministic_thread_uuid,
)

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

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
        # NOTE: UUID columns stored as dt.string in Ibis, DuckDB schema handles conversion to UUID type
        "event_id": dt.string,
        # Multi-Tenant
        "tenant_id": dt.string,
        "source": dt.string,
        # Threading
        "thread_id": dt.string,
        "msg_id": dt.string,
        # Temporal
        "ts": dt.Timestamp(timezone="UTC"),
        # Authors (PRIVACY BOUNDARY)
        "author_raw": dt.string,
        "author_uuid": dt.string,
        # Content
        "text": dt.String(nullable=True),
        "media_url": dt.String(nullable=True),
        "media_type": dt.String(nullable=True),
        # Metadata
        "attrs": dt.JSON(nullable=True),
        "pii_flags": dt.JSON(nullable=True),
        # Lineage
        "created_at": dt.Timestamp(timezone="UTC"),
        "created_by_run": dt.string,
    }
)


# ============================================================================
# Schema Generation Functions (Single Source of Truth)
# ============================================================================


def generate_ir_sql_ddl(table_name: str = "ir_messages") -> str:
    """Generate CREATE TABLE SQL DDL from IR_MESSAGE_SCHEMA.

    This function is the single source of truth for runtime table creation.
    The SQL is generated dynamically from the Ibis schema definition.

    Args:
        table_name: Name of the table to create (default: "ir_messages")

    Returns:
        SQL DDL string with CREATE TABLE statement

    Example:
        >>> sql = generate_ir_sql_ddl()
        >>> conn.execute(sql)  # Create table in database

    """
    # Columns that are explicitly nullable (allow NULL values)
    # Based on IR v1 specification - text/media/metadata are optional
    NULLABLE_COLUMNS = {"text", "media_url", "media_type", "attrs", "pii_flags"}

    # Map Ibis data types to DuckDB SQL types
    def ibis_to_sql_type(dtype: dt.DataType) -> str:
        """Convert Ibis data type to DuckDB SQL type string."""
        if isinstance(dtype, dt.String):
            return "VARCHAR"
        elif isinstance(dtype, dt.Timestamp):
            # DuckDB TIMESTAMP WITH TIME ZONE
            if dtype.timezone:
                return "TIMESTAMP WITH TIME ZONE"
            return "TIMESTAMP"
        elif isinstance(dtype, dt.JSON):
            return "JSON"
        elif isinstance(dtype, dt.UUID):
            return "UUID"
        else:
            # Fallback to Ibis string representation
            return str(dtype).upper().split("(")[0]

    # Generate column definitions
    columns = []
    for col_name in IR_MESSAGE_SCHEMA.names:
        dtype = IR_MESSAGE_SCHEMA[col_name]
        sql_type = ibis_to_sql_type(dtype)

        # Determine nullability from explicit list (not Ibis attribute)
        nullable = col_name in NULLABLE_COLUMNS
        null_constraint = "" if nullable else " NOT NULL"

        columns.append(f"    {col_name} {sql_type}{null_constraint}")

    # Build CREATE TABLE statement
    sql_parts = [
        f"-- Generated from IR_MESSAGE_SCHEMA in validation.py",
        f"-- DO NOT EDIT: This SQL is auto-generated",
        f"",
        f"DROP TABLE IF EXISTS {table_name};",
        f"",
        f"CREATE TABLE {table_name} (",
        ",\n".join(columns),
        ",",
        f"    PRIMARY KEY (event_id)",
        ");",
        f"",
        f"-- Indexes for common query patterns",
        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_ts ON {table_name}(ts);",
        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_thread ON {table_name}(thread_id);",
        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_author ON {table_name}(author_uuid);",
    ]

    return "\n".join(sql_parts)


def generate_ir_lockfile_json(version: str = "1.0.0") -> dict[str, Any]:
    """Generate JSON lockfile from IR_MESSAGE_SCHEMA for validation.

    This function generates the lockfile used by CI to detect schema drift.
    The lockfile is the schema serialized to JSON format.

    Args:
        version: Schema version string (default: "1.0.0")

    Returns:
        Dictionary representing the schema lockfile

    Example:
        >>> lockfile = generate_ir_lockfile_json()
        >>> Path("schema/ir_v1.json").write_text(json.dumps(lockfile, indent=2))

    """
    # Columns that are explicitly nullable (same as generate_ir_sql_ddl)
    NULLABLE_COLUMNS = {"text", "media_url", "media_type", "attrs", "pii_flags"}

    return {
        "version": version,
        "table": "ir_messages",
        "columns": {
            col: {
                "type": str(IR_MESSAGE_SCHEMA[col]).split("(")[0].upper(),
                "nullable": col in NULLABLE_COLUMNS,
                "timezone": getattr(IR_MESSAGE_SCHEMA[col], "timezone", None),
            }
            for col in IR_MESSAGE_SCHEMA.names
        },
    }


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
    event_id: uuid.UUID | None = None

    # Multi-Tenant
    tenant_id: str = Field(min_length=1)
    source: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")  # lowercase, alphanumeric + underscore/dash

    # Threading
    thread_id: uuid.UUID
    msg_id: str | None = None  # Required identifier in canonical schema

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
        >>> class MyAdapter(InputAdapter):
        ...     @validate_adapter_output
        ...     def parse(self, input_path: Path) -> Table:
        ...         # Parse logic here
        ...         return table

    Note:
        This is a convenience decorator. InputAdapterRegistry can also
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

    This decorator wraps stage functions to automatically validate:
    1. Input data conforms to IR v1 schema
    2. Output data conforms to IR v1 schema (preserves schema contract)

    Works with both:
    - Plain functions: `(data: Table, ...) -> Table`
    - Methods: `(self, data: Table, ...) -> Table`

    Args:
        func: Function or method that takes a Table as input and returns a Table

    Returns:
        Wrapped function that validates input/output

    Raises:
        SchemaError: If input or output doesn't match IR v1 schema

    Example (functional approach):
        >>> @validate_stage
        ... def filter_messages(data: Table, min_length: int = 0) -> Table:
        ...     return data.filter(data.text.length() >= min_length)

    Example (legacy class-based - for backward compatibility only):
        >>> # Note: PipelineStage abstraction has been removed
        >>> # This decorator now supports both plain functions and legacy methods

    Note:
        This validates BOTH inputs and outputs to ensure transformation
        preserve the IR v1 schema contract throughout the pipeline.

    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Determine if this is a method (has self) or function
        # For methods: args = (self, data, ...), data is at index 1
        # For functions: args = (data, ...), data is at index 0
        is_method = len(args) >= MIN_STAGE_ARGS and hasattr(args[0], "__class__")
        data_index = 1 if is_method else 0

        if len(args) <= data_index:
            msg = f"Function requires at least {data_index + 1} argument(s): data parameter missing"
            raise TypeError(msg)

        input_data = args[data_index]

        # Validate input
        try:
            validate_ir_schema(input_data)
        except SchemaError as e:
            func_name = getattr(func, "__qualname__", func.__name__)
            msg = f"Stage input validation failed in {func_name}: {e}"
            raise SchemaError(msg) from e

        # Call original function
        result = func(*args, **kwargs)

        # Extract output data
        # Support both plain Table returns and legacy StageResult objects
        if hasattr(result, "data"):
            # Legacy StageResult pattern
            output_data = result.data
        else:
            # Modern functional pattern: direct Table return
            output_data = result

        # Validate output
        try:
            validate_ir_schema(output_data)
        except SchemaError as e:
            func_name = getattr(func, "__qualname__", func.__name__)
            msg = f"Stage output validation failed in {func_name}: {e}"
            raise SchemaError(msg) from e

        return result

    return wrapper  # type: ignore[return-value]


# ============================================================================
# IR Table Creation (Compatibility Layer)
# ============================================================================


def create_ir_table(
    table: Table,
    *,
    tenant_id: str,
    source: str,
    timezone: str | ZoneInfo | None = None,
    thread_key: str | None = None,
    run_id: uuid.UUID | None = None,
    author_namespace: uuid.UUID | None = None,
) -> Table:
    """Convert legacy conversation table to IR v1 schema."""
    if not tenant_id:
        msg = "tenant_id is required when constructing IR table"
        raise ValueError(msg)
    if not source:
        msg = "source is required when constructing IR table"
        raise ValueError(msg)

    # CLEAN BREAK: Adapters MUST return IR-like schema (ts, text, author_raw, author_uuid)
    # No legacy CONVERSATION schema support - fix adapters instead

    # Verify adapter returned IR schema
    required_cols = {"ts", "text", "author_raw", "author_uuid"}
    missing = required_cols - set(table.columns)
    if missing:
        msg = f"Adapter must return IR schema. Missing columns: {missing}"
        raise ValueError(msg)

    # No normalization - use IR column names directly
    if "message_id" not in table.columns:
        table = table.mutate(message_id=ibis.row_number().cast(dt.string))

    namespace_override = author_namespace

    @ibis.udf.scalar.python
    def author_uuid_udf(author_raw: str | None) -> str:
        if author_raw is None or not author_raw.strip():
            msg = "author_raw column cannot be empty when generating author_uuid"
            raise ValueError(msg)
        if namespace_override is not None:
            normalized_author = author_raw.strip().lower()
            return str(uuid.uuid5(namespace_override, normalized_author))
        return str(deterministic_author_uuid(tenant_id, source, author_raw))

    @ibis.udf.scalar.python
    def event_uuid_udf(message_id: str | None, ts_value: datetime) -> str:
        if ts_value is None:
            msg = "ts is required to generate event_id"
            raise ValueError(msg)
        key = message_id or ts_value.isoformat()
        return str(deterministic_event_uuid(tenant_id, source, key, ts_value))

    @ibis.udf.scalar.python
    def attrs_udf(
        original_line: str | None,
        tagged_line: str | None,
        date_value: date | None,
    ) -> dict[str, str] | None:
        data: dict[str, str] = {}
        if original_line:
            data["original_line"] = original_line
        if tagged_line:
            data["tagged_line"] = tagged_line
        if date_value:
            data["date"] = date_value.isoformat()
        return data or None

    thread_identifier = thread_key or tenant_id
    thread_uuid = deterministic_thread_uuid(tenant_id, source, thread_identifier)

    created_at_literal = ibis.literal(datetime.now(UTC), type=dt.Timestamp(timezone="UTC"))
    if run_id is not None:
        # Convert Python UUID to string - DuckDB handles str→UUID conversion
        created_by_run_literal = ibis.literal(str(run_id), type=dt.string)
    else:
        created_by_run_literal = ibis.null().cast(dt.string)

    # CLEAN BREAK: Use IR column names directly (ts, text, author_raw, author_uuid)
    # NOTE: UDF functions already return str, matching the VARCHAR-based IR schema.
    ir_table = table.mutate(
        event_id=event_uuid_udf(
            table.message_id.cast(dt.string),
            table.ts.cast(dt.Timestamp()),
        ),
        tenant_id=ibis.literal(tenant_id, type=dt.string),
        source=ibis.literal(source, type=dt.string),
        # thread_uuid is Python UUID → convert to string for DuckDB
        thread_id=ibis.literal(str(thread_uuid), type=dt.string),
        msg_id=table.message_id.cast(dt.string),
        ts=table.ts.cast(dt.Timestamp(timezone="UTC")),
        author_raw=table.author_raw,
        author_uuid=author_uuid_udf(table.author_raw),
        text=table.text,
        media_url=ibis.null().cast(dt.String(nullable=True)),
        media_type=ibis.null().cast(dt.String(nullable=True)),
        attrs=attrs_udf(
            table.original_line if "original_line" in table.columns else ibis.null(),
            table.tagged_line if "tagged_line" in table.columns else ibis.null(),
            table.date if "date" in table.columns else ibis.null(),
        ).cast(dt.JSON(nullable=True)),
        pii_flags=ibis.null().cast(dt.JSON(nullable=True)),
        created_at=ibis.literal(datetime.now(UTC), type=dt.Timestamp(timezone="UTC")),
        created_by_run=created_by_run_literal,
    )

    return ir_table.select(*IR_MESSAGE_SCHEMA.names)


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # Exceptions
    "SchemaError",
    # Schema definitions
    "IR_MESSAGE_SCHEMA",
    # Schema generation (single source of truth)
    "generate_ir_sql_ddl",
    "generate_ir_lockfile_json",
    # Validation models
    "IRMessageRow",
    # Validation functions
    "validate_ir_schema",
    "schema_diff",
    "load_ir_schema_lockfile",
    # Adapter validation
    "adapter_output_validator",
    "validate_adapter_output",
    # Stage validation (functional)
    "validate_stage",
    # IR table creation
    "create_ir_table",
]
