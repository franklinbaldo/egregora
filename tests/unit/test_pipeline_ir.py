"""Tests for pipeline IR (Intermediate Representation) schema and validation."""

import uuid
from datetime import UTC, datetime

import ibis
import pytest

from egregora.database.validation import (
    IR_MESSAGE_SCHEMA,
    SchemaError,
    create_ir_table,
    validate_ir_schema,
)
from egregora.privacy.constants import deterministic_author_uuid


class TestIRSchema:
    """Test IR schema definition and validation."""

    def test_ir_schema_has_required_fields(self):
        """IR schema should contain all required fields."""
        required_fields = {
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
        assert set(IR_MESSAGE_SCHEMA.keys()) == required_fields

    def test_validate_ir_schema_with_valid_table(self):
        """Validation should pass for a table conforming to IR schema."""
        # Create a valid IR table
        timestamp = datetime(2024, 1, 1, 12, tzinfo=UTC)
        data = [
            {
                "event_id": str(uuid.uuid4()),
                "tenant_id": "tenant-1",
                "source": "whatsapp",
                "thread_id": str(uuid.uuid4()),
                "msg_id": "123",
                "ts": timestamp,
                "author_raw": "user1",
                "author_uuid": str(uuid.uuid4()),
                "text": "Hello world",
                "media_url": None,
                "media_type": None,
                "attrs": {"lang": "en"},
                "pii_flags": {"contains_email": False},
                "created_at": timestamp,
                "created_by_run": str(uuid.uuid4()),
            }
        ]
        table = ibis.memtable(data, schema=IR_MESSAGE_SCHEMA)

        validate_ir_schema(table)

    def test_validate_ir_schema_with_missing_columns(self):
        """Validation should fail for a table missing required columns."""
        # Create table missing required columns
        data = [
            {
                "event_id": str(uuid.uuid4()),
                "tenant_id": "tenant-1",
                "source": "whatsapp",
                "ts": datetime(2024, 1, 1, 12, tzinfo=UTC),
                "author_raw": "user1",
                "author_uuid": str(uuid.uuid4()),
            }
        ]
        table = ibis.memtable(data)

        with pytest.raises(SchemaError):
            validate_ir_schema(table)

    def test_validate_ir_schema_with_wrong_types(self):
        """Validation should fail for columns with incompatible types."""
        # Create table with wrong types
        data = [
            {
                "event_id": str(uuid.uuid4()),
                "tenant_id": "tenant-1",
                "source": "whatsapp",
                "thread_id": str(uuid.uuid4()),
                "msg_id": "123",
                # Should be timestamp, but providing string to trigger type mismatch
                "ts": "2024-01-01T12:00:00Z",
                "author_raw": "user1",
                "author_uuid": str(uuid.uuid4()),
                "text": "Hello",
                "media_url": None,
                "media_type": None,
                "attrs": {},
                "pii_flags": {},
                "created_at": datetime(2024, 1, 1, 12, tzinfo=UTC),
                "created_by_run": str(uuid.uuid4()),
            }
        ]
        table = ibis.memtable(data)

        with pytest.raises(SchemaError):
            validate_ir_schema(table)

    def test_create_ir_table_with_minimal_valid_input(self):
        """create_ir_table should accept and normalize minimal valid input."""
        # Create minimal table with required core fields
        data = [
            {
                "timestamp": "2024-01-01 12:00:00",
                "author": "user1",
                "message": "Hello world",
            }
        ]
        table = ibis.memtable(data)

        ir_table = create_ir_table(
            table,
            tenant_id="tenant-1",
            source="whatsapp",
            thread_key="tenant-1",
            timezone="UTC",
        )

        # Should have all IR schema columns
        assert set(ir_table.columns) == set(IR_MESSAGE_SCHEMA.names)

        # Validate the resulting table
        validate_ir_schema(ir_table)

    def test_create_ir_table_preserves_data(self):
        """create_ir_table should preserve message data while adding schema fields."""
        data = [
            {
                "timestamp": "2024-01-01 12:00:00",
                "author": "alice",
                "message": "Test message",
            }
        ]
        table = ibis.memtable(data)

        ir_table = create_ir_table(
            table,
            tenant_id="tenant-1",
            source="whatsapp",
            thread_key="tenant-1",
            timezone="UTC",
        )

        result = ir_table.execute()

        assert len(result) == 1
        assert result["author_raw"][0] == "alice"
        assert result["text"][0] == "Test message"
        assert result["author_uuid"][0] == str(deterministic_author_uuid("alice"))
        assert result["attrs"][0] is None

    def test_create_ir_table_with_custom_timezone(self):
        """create_ir_table should handle custom timezones."""
        data = [
            {
                "timestamp": "2024-01-01 12:00:00",
                "author": "user1",
                "message": "Hello",
            }
        ]
        table = ibis.memtable(data)

        ir_table = create_ir_table(
            table,
            tenant_id="tenant-1",
            source="whatsapp",
            thread_key="tenant-1",
            timezone="America/New_York",
            author_namespace=uuid.uuid5(uuid.NAMESPACE_DNS, "custom"),
        )

        # Should not raise an error
        result = ir_table.execute()
        assert len(result) == 1
        expected_uuid = str(
            deterministic_author_uuid("user1", namespace=uuid.uuid5(uuid.NAMESPACE_DNS, "custom"))
        )
        assert result["author_uuid"][0] == expected_uuid


class TestIRSchemaContract:
    """Contract tests ensuring IR schema stability."""

    def test_ir_schema_has_timestamp_with_timezone(self):
        """IR schema timestamp must include timezone information."""
        timestamp_dtype = IR_MESSAGE_SCHEMA["ts"]
        assert timestamp_dtype.timezone is not None

    def test_ir_schema_message_id_is_nullable(self):
        """IR schema message_id must be nullable for flexibility."""
        message_id_dtype = IR_MESSAGE_SCHEMA["msg_id"]
        assert message_id_dtype.nullable

    def test_ir_schema_core_fields_not_nullable(self):
        """IR schema core fields (ts, author_raw, author_uuid) must not be nullable."""
        core_fields = ["ts", "author_raw", "author_uuid"]

        for field in core_fields:
            dtype = IR_MESSAGE_SCHEMA[field]
            assert not dtype.nullable
