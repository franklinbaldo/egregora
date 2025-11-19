"""Tests for IR v1 schema validation.

Tests compile-time and runtime validation of tables against IR v1 schema.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import ibis
import ibis.expr.datatypes as dt
import pytest
from pydantic import ValidationError

from egregora.database.validation import (
    IR_MESSAGE_SCHEMA,
    IRMessageRow,
    SchemaError,
    adapter_output_validator,
    schema_diff,
    validate_ir_schema,
)


def create_valid_ir_v1_table() -> ibis.Table:
    """Create a valid IR v1 table for testing."""
    # Note: Convert UUIDs to strings for memtable serialization
    # Ibis will cast them back to UUID type based on schema
    data = {
        "event_id": [str(uuid.uuid4())],
        "tenant_id": ["default"],
        "source": ["whatsapp"],
        "thread_id": [str(uuid.uuid4())],
        "msg_id": ["msg-001"],
        "ts": [datetime.now(UTC)],
        "author_raw": ["Alice"],
        "author_uuid": [str(uuid.uuid4())],
        "text": ["Hello world"],
        "media_url": [None],
        "media_type": [None],
        "attrs": [{"original_line": "test"}],
        "pii_flags": [None],
        "created_at": [datetime.now(UTC)],
        "created_by_run": [None],
    }
    return ibis.memtable(data, schema=IR_MESSAGE_SCHEMA)


class TestIRv1Schema:
    """Test IR v1 schema constant."""

    def test_schema_has_all_required_columns(self):
        """Test IR v1 schema contains all required columns."""
        expected_columns = {
            "event_id",
            "tenant_id",
            "source",
            "thread_id",
            "msg_id",
            "ts",
            "author_raw",
            "author_uuid",
            "text",
            "media_url",
            "media_type",
            "attrs",
            "pii_flags",
            "created_at",
            "created_by_run",
        }

        assert set(IR_MESSAGE_SCHEMA.names) == expected_columns

    def test_schema_uuid_columns(self):
        """Test UUID columns are stored as strings in Ibis schema.

        NOTE: UUID columns are stored as dt.string in Ibis because DuckDB
        handles the conversion to UUID type at the SQL level. The Pydantic
        validator (IRMessageRow) accepts uuid.UUID objects for convenience.
        """
        # These columns store UUIDs as strings in Ibis
        uuid_columns = ["event_id", "thread_id", "author_uuid", "created_by_run"]

        for col in uuid_columns:
            col_type = IR_MESSAGE_SCHEMA[col]
            assert isinstance(col_type, dt.String), f"{col} should be String type (UUIDs stored as strings)"

    def test_schema_nullable_columns(self):
        """Test nullable columns are marked correctly."""
        nullable_columns = ["text", "media_url", "media_type", "attrs", "pii_flags", "created_by_run"]

        for col in nullable_columns:
            col_type = IR_MESSAGE_SCHEMA[col]
            assert col_type.nullable, f"{col} should be nullable"


class TestIRv1Row:
    """Test IRMessageRow Pydantic validator."""

    def test_valid_row(self):
        """Test valid IR v1 row passes validation."""
        row = IRMessageRow(
            event_id=uuid.uuid4(),
            tenant_id="default",
            source="whatsapp",
            thread_id=uuid.uuid4(),
            msg_id="msg-001",
            ts=datetime.now(UTC),
            author_raw="Alice",
            author_uuid=uuid.uuid4(),
            text="Hello",
            media_url=None,
            media_type=None,
            attrs={"key": "value"},
            pii_flags=None,
            created_at=datetime.now(UTC),
            created_by_run=None,
        )

        assert row.tenant_id == "default"
        assert row.source == "whatsapp"

    def test_invalid_tenant_id_empty(self):
        """Test empty tenant_id fails validation."""
        with pytest.raises(ValidationError, match="tenant_id"):
            IRMessageRow(
                event_id=uuid.uuid4(),
                tenant_id="",  # Empty string
                source="whatsapp",
                thread_id=uuid.uuid4(),
                msg_id="msg-001",
                ts=datetime.now(UTC),
                author_raw="Alice",
                author_uuid=uuid.uuid4(),
                created_at=datetime.now(UTC),
            )

    def test_invalid_source_uppercase(self):
        """Test uppercase source fails validation."""
        with pytest.raises(ValidationError, match="source"):
            IRMessageRow(
                event_id=uuid.uuid4(),
                tenant_id="default",
                source="WhatsApp",  # Should be lowercase
                thread_id=uuid.uuid4(),
                msg_id="msg-001",
                ts=datetime.now(UTC),
                author_raw="Alice",
                author_uuid=uuid.uuid4(),
                created_at=datetime.now(UTC),
            )

    def test_nullable_fields_optional(self):
        """Test nullable fields can be None."""
        row = IRMessageRow(
            event_id=uuid.uuid4(),
            tenant_id="default",
            source="slack",
            thread_id=uuid.uuid4(),
            msg_id="msg-001",
            ts=datetime.now(UTC),
            author_raw="Alice",
            author_uuid=uuid.uuid4(),
            text=None,  # Nullable
            media_url=None,  # Nullable
            media_type=None,  # Nullable
            attrs=None,  # Nullable
            pii_flags=None,  # Nullable
            created_at=datetime.now(UTC),
            created_by_run=None,  # Nullable
        )

        assert row.text is None
        assert row.created_by_run is None


class TestSchemaDiff:
    """Test schema_diff helper function."""

    def test_diff_missing_columns(self):
        """Test diff detects missing columns."""
        expected = ibis.schema({"a": dt.string, "b": dt.int64})
        actual = ibis.schema({"a": dt.string})

        diff = schema_diff(expected, actual)

        assert "Missing columns" in diff
        assert "b" in diff

    def test_diff_extra_columns(self):
        """Test diff detects extra columns."""
        expected = ibis.schema({"a": dt.string})
        actual = ibis.schema({"a": dt.string, "b": dt.int64})

        diff = schema_diff(expected, actual)

        assert "Extra columns" in diff
        assert "b" in diff

    def test_diff_type_mismatches(self):
        """Test diff detects type mismatches."""
        expected = ibis.schema({"a": dt.string})
        actual = ibis.schema({"a": dt.int64})

        diff = schema_diff(expected, actual)

        assert "Type mismatches" in diff
        assert "a" in diff

    def test_diff_no_differences(self):
        """Test diff returns 'No differences' for identical schemas."""
        schema = ibis.schema({"a": dt.string, "b": dt.int64})

        diff = schema_diff(schema, schema)

        assert diff == "No differences"


class TestValidateIRSchema:
    """Test validate_ir_schema function."""

    def test_valid_table_passes(self):
        """Test valid IR v1 table passes validation."""
        table = create_valid_ir_v1_table()

        # Should not raise
        validate_ir_schema(table)

    def test_missing_column_fails(self):
        """Test table with missing column fails validation."""
        # Create table without 'source' column
        data = {
            "event_id": [uuid.uuid4()],
            "tenant_id": ["default"],
            # Missing: "source"
            "thread_id": [uuid.uuid4()],
            "msg_id": ["msg-001"],
            "ts": [datetime.now(UTC)],
            "author_raw": ["Alice"],
            "author_uuid": [uuid.uuid4()],
            "text": ["Hello"],
            "media_url": [None],
            "media_type": [None],
            "attrs": [None],
            "pii_flags": [None],
            "created_at": [datetime.now(UTC)],
            "created_by_run": [None],
        }

        # Build schema without 'source'
        schema = ibis.schema({k: IR_MESSAGE_SCHEMA[k] for k in data})
        table = ibis.memtable(data, schema=schema)

        with pytest.raises(SchemaError, match="schema mismatch"):
            validate_ir_schema(table)

    def test_extra_column_fails(self):
        """Test table with extra column fails validation."""
        data = {
            "event_id": [uuid.uuid4()],
            "tenant_id": ["default"],
            "source": ["whatsapp"],
            "thread_id": [uuid.uuid4()],
            "msg_id": ["msg-001"],
            "ts": [datetime.now(UTC)],
            "author_raw": ["Alice"],
            "author_uuid": [uuid.uuid4()],
            "text": ["Hello"],
            "media_url": [None],
            "media_type": [None],
            "attrs": [None],
            "pii_flags": [None],
            "created_at": [datetime.now(UTC)],
            "created_by_run": [None],
            "extra_field": ["should not be here"],  # Extra column
        }

        # Build schema with extra field
        schema = IR_MESSAGE_SCHEMA
        extra_schema = ibis.schema({**dict(schema.items()), "extra_field": dt.string})
        table = ibis.memtable(data, schema=extra_schema)

        with pytest.raises(SchemaError, match="schema mismatch"):
            validate_ir_schema(table)

    def test_type_mismatch_fails(self):
        """Test table with wrong column type fails validation."""
        data = {
            "event_id": [uuid.uuid4()],
            "tenant_id": ["default"],
            "source": ["whatsapp"],
            "thread_id": [uuid.uuid4()],
            "msg_id": ["msg-001"],
            "ts": [datetime.now(UTC)],
            "author_raw": ["Alice"],
            "author_uuid": [uuid.uuid4()],
            "text": ["Hello"],
            "media_url": [None],
            "media_type": [None],
            "attrs": [None],
            "pii_flags": [None],
            "created_at": [datetime.now(UTC)],
            "created_by_run": [None],
        }

        # Change tenant_id to int64 (should be string)
        wrong_schema = ibis.schema({**dict(IR_MESSAGE_SCHEMA.items()), "tenant_id": dt.int64})
        table = ibis.memtable({**data, "tenant_id": [123]}, schema=wrong_schema)

        with pytest.raises(SchemaError, match="type mismatch"):
            validate_ir_schema(table)

    def test_empty_table_passes(self):
        """Test empty table (0 rows) passes validation."""
        # Create empty table with correct schema
        table = ibis.memtable([], schema=IR_MESSAGE_SCHEMA)

        # Should not raise (empty table is valid)
        validate_ir_schema(table)

    def test_multiple_rows_valid(self):
        """Test table with multiple valid rows passes."""
        # Note: Convert UUIDs to strings for memtable serialization
        data = {
            "event_id": [str(uuid.uuid4()), str(uuid.uuid4())],
            "tenant_id": ["default", "default"],
            "source": ["whatsapp", "whatsapp"],
            "thread_id": [str(uuid.uuid4()), str(uuid.uuid4())],
            "msg_id": ["msg-001", "msg-002"],
            "ts": [datetime.now(UTC), datetime.now(UTC)],
            "author_raw": ["Alice", "Bob"],
            "author_uuid": [str(uuid.uuid4()), str(uuid.uuid4())],
            "text": ["Hello", "Hi"],
            "media_url": [None, None],
            "media_type": [None, None],
            "attrs": [None, None],
            "pii_flags": [None, None],
            "created_at": [datetime.now(UTC), datetime.now(UTC)],
            "created_by_run": [None, None],
        }

        table = ibis.memtable(data, schema=IR_MESSAGE_SCHEMA)

        # Should not raise
        validate_ir_schema(table)


class TestAdapterOutputValidator:
    """Test adapter_output_validator function."""

    def test_valid_table_returns_unchanged(self):
        """Test valid table is returned unchanged."""
        table = create_valid_ir_v1_table()

        result = adapter_output_validator(table)

        # Should return same table
        assert result is table

    def test_invalid_table_raises(self):
        """Test invalid table raises SchemaError."""
        # Create table with missing column
        data = {
            "event_id": [uuid.uuid4()],
            "tenant_id": ["default"],
            # Missing required columns
        }

        schema = ibis.schema({"event_id": dt.UUID, "tenant_id": dt.string})
        table = ibis.memtable(data, schema=schema)

        with pytest.raises(SchemaError):
            adapter_output_validator(table)


class TestValidationIntegration:
    """Integration tests for validation workflow."""

    def test_adapter_validation_workflow(self):
        """Test typical adapter validation workflow."""
        # Simulate adapter output
        table = create_valid_ir_v1_table()

        # Validate at boundary
        validated_table = adapter_output_validator(table)

        # Verify validation passed (returns same table)
        assert validated_table is table

        # Verify schema is correct
        assert "source" in validated_table.schema().names
        assert "event_id" in validated_table.schema().names
