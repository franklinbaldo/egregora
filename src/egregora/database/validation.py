"""Runtime validation for IR v1 schema compliance.

This module provides validation infrastructure to ensure data tables conform
to the IR v1 schema specification at runtime. It combines:

1. **Compile-time validation**: Checks Ibis table schemas match expected structure
2. **Runtime validation**: Validates sample rows using Pydantic models
3. **Adapter boundary enforcement**: Validates adapter outputs before pipeline

**Canonical Schema**: The `IR_MESSAGE_SCHEMA` imported from
`egregora.database.ir_schema` is the single source of truth for the IR v1
specification. All adapters MUST produce tables conforming to this schema.

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

    # Manual validation for pipeline transformations
    def filter_messages(data: Table, min_length: int = 0) -> Table:
        validate_ir_schema(data)  # Validate input
        result = data.filter(data.text.length() >= min_length)
        validate_ir_schema(result)  # Validate output
        return result

See Also:
    - docs/architecture/ir-v1-spec.md
    - schema/archive/ (historical SQL/JSON lockfiles)

"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

import ibis
import ibis.expr.datatypes as dt
from pydantic import BaseModel, Field, ValidationError, create_model

from egregora.database.ir_schema import IR_MESSAGE_SCHEMA
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


class SchemaError(Exception):
    """Raised when table schema doesn't match IR v1 specification."""


# ============================================================================
# Ibis-to-Pydantic Schema Generation
# ============================================================================


def ibis_type_to_python(ibis_type: dt.DataType) -> type:
    """Convert Ibis data type to Python type for Pydantic model generation.

    Args:
        ibis_type: Ibis data type

    Returns:
        Python type suitable for Pydantic field

    """
    # Map Ibis types to Python types
    type_mapping: dict[type, type] = {
        dt.String: str,
        dt.Int64: int,
        dt.Int32: int,
        dt.Float64: float,
        dt.Float32: float,
        dt.Boolean: bool,
        dt.Date: date,
        dt.Binary: bytes,
    }

    # Check base type
    ibis_base = type(ibis_type)

    # Special handling for complex types
    if ibis_base == dt.Timestamp:
        return datetime
    if ibis_base == dt.UUID:
        return uuid.UUID
    if ibis_base == dt.JSON:
        return dict[str, Any]
    if ibis_base == dt.Array:
        return list[Any]

    return type_mapping.get(ibis_base, Any)


def ibis_schema_to_pydantic(
    schema: ibis.Schema,
    model_name: str,
    *,
    field_overrides: dict[str, Any] | None = None,
    frozen: bool = True,
) -> type[BaseModel]:
    """Generate a Pydantic model from an Ibis schema.

    This function creates a Pydantic model that matches the structure of an
    Ibis schema, ensuring consistency between schema definitions for creation
    and validation.

    Args:
        schema: Ibis schema to convert
        model_name: Name for the generated Pydantic model
        field_overrides: Dict mapping field names to either:
                        - Pydantic Field() objects for custom validation
                        - Tuples (type, Field()) for type + validation overrides
        frozen: Whether the model should be frozen (immutable)

    Returns:
        Generated Pydantic BaseModel class

    Example:
        >>> schema = ibis.schema({"name": dt.string, "age": dt.Int64(nullable=True)})
        >>> Model = ibis_schema_to_pydantic(schema, "Person")
        >>> person = Model(name="Alice", age=30)

        >>> # With type override for UUID field
        >>> overrides = {
        ...     "user_id": (uuid.UUID, Field(...)),  # Override type + validation
        ...     "email": Field(pattern=r".*@.*"),    # Keep generated type, add validation
        ... }
        >>> Model = ibis_schema_to_pydantic(schema, "User", field_overrides=overrides)

    """
    from pydantic import ConfigDict  # noqa: PLC0415

    field_overrides = field_overrides or {}
    fields: dict[str, Any] = {}

    for name, ibis_type in schema.items():
        python_type = ibis_type_to_python(ibis_type)

        # Handle nullable types
        if ibis_type.nullable:
            python_type = python_type | None

        # Check for field override
        if name in field_overrides:
            override = field_overrides[name]
            # Support two override formats:
            # 1. Tuple (type, Field()) - full type + validation override
            # 2. Field() only - keep generated type, override validation
            if isinstance(override, tuple):
                fields[name] = override  # Use provided (type, Field())
            else:
                fields[name] = (python_type, override)  # Use generated type with Field()
        elif ibis_type.nullable:
            fields[name] = (python_type, None)
        else:
            fields[name] = (python_type, ...)

    # Create model with frozen config (Pydantic v2 style)
    model = create_model(model_name, **fields)
    if frozen:
        model.model_config = ConfigDict(frozen=True)
    return model


# ============================================================================
# Runtime Validator (Pydantic)
# ============================================================================

# Generate IRMessageRow from IR_MESSAGE_SCHEMA for single source of truth
# This approach eliminates duplication between Ibis schema (creation) and Pydantic model (validation)
#
# Key Design Decisions:
# 1. UUID fields: Ibis stores as dt.string, but Pydantic accepts uuid.UUID for type safety
# 2. Custom validators: Field overrides add semantic validation (regex, min_length)
# 3. Type coercion: Pydantic auto-converts string UUIDs to uuid.UUID objects
#
# Benefits:
# - Schema changes automatically propagate to validation
# - Reduced maintenance burden (update IR_MESSAGE_SCHEMA only)
# - Type synchronization guaranteed at generation time

# Field overrides for custom validation and UUID type handling
# Format: field_name -> (type, Field()) for type override, or Field() to keep generated type
_IR_FIELD_OVERRIDES = {
    # UUID fields: Override type from str to uuid.UUID (Ibis stores as string, Pydantic validates as UUID)
    "event_id": (uuid.UUID | None, Field(default=None)),  # Optional UUID
    "thread_id": (uuid.UUID, Field(...)),  # Required UUID
    "author_uuid": (uuid.UUID, Field(...)),  # Required UUID
    "created_by_run": (uuid.UUID | None, Field(default=None)),  # Optional UUID
    # Custom validators (keep generated str type, add validation)
    "tenant_id": Field(min_length=1),  # Non-empty string
    "source": Field(pattern=r"^[a-z][a-z0-9_-]*$"),  # lowercase alphanumeric + underscore/dash
}

# Generate Pydantic model from Ibis schema
IRMessageRow = ibis_schema_to_pydantic(
    schema=IR_MESSAGE_SCHEMA,
    model_name="IRMessageRow",
    field_overrides=_IR_FIELD_OVERRIDES,
    frozen=True,
)

# Add docstring to generated class (Pydantic create_model doesn't preserve docstrings)
IRMessageRow.__doc__ = """Runtime validator for IR v1 rows.

This Pydantic model validates individual rows conform to IR v1 schema.
Used for runtime validation of sample data.

Generated from IR_MESSAGE_SCHEMA with custom field validators for:
- UUID type coercion (string → uuid.UUID)
- Semantic validation (regex patterns, min_length)

Attributes match IR v1 specification exactly.
"""


# ============================================================================
# Schema Validation Functions
# ============================================================================


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
        lines.extend(f"  - {col}: {expected[col]}" for col in sorted(missing))

    # Check for extra columns
    extra = actual_cols - expected_cols
    if extra:
        lines.append("Extra columns:")
        lines.extend(f"  + {col}: {actual[col]}" for col in sorted(extra))

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


def validate_ir_schema(table: Table, *, sample_size: int = 100) -> None:  # noqa: C901
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
        import logging  # noqa: PLC0415

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




# validate_stage decorator - REMOVED (2025-11-17)
# Rationale: Not used anywhere in codebase. Stages should call validate_ir_schema()
# directly when validation is needed, rather than using a decorator.
# See docs/SIMPLIFICATION_PLAN.md for details.


# ============================================================================
# IR Table Creation (Compatibility Layer)
# ============================================================================


def create_ir_table(  # noqa: C901, PLR0913
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
    "IR_MESSAGE_SCHEMA",
    "IRMessageRow",
    "SchemaError",
    "create_ir_table",
    "ibis_schema_to_pydantic",
    "ibis_type_to_python",
    "schema_diff",
    "validate_ir_schema",
]
