"""Tests for pipeline IR (Intermediate Representation) schema and validation."""

import uuid

import ibis

from egregora.database.validation import IR_MESSAGE_SCHEMA, create_ir_table, validate_ir_schema
from egregora.privacy.constants import deterministic_author_uuid


class TestIRSchema:
    """Test IR schema definition and validation."""

    def test_ir_schema_has_required_fields(self):
        """IR schema should contain all required fields."""
        required_fields = {
            "timestamp",
            "date",
            "author",
            "message",
            "original_line",
            "tagged_line",
            "message_id",
        }
        assert set(IR_MESSAGE_SCHEMA.keys()) == required_fields

    def test_validate_ir_schema_with_valid_table(self):
        """Validation should pass for a table conforming to IR schema."""
        # Create a valid IR table
        data = [
            {
                "timestamp": "2024-01-01 12:00:00",
                "date": "2024-01-01",
                "author": "user1",
                "message": "Hello world",
                "original_line": "raw line",
                "tagged_line": "tagged line",
                "message_id": "123",
            }
        ]
        table = ibis.memtable(data, schema=ibis.schema(IR_MESSAGE_SCHEMA))

        is_valid, errors = validate_ir_schema(table)

        assert is_valid
        assert len(errors) == 0

    def test_validate_ir_schema_with_missing_columns(self):
        """Validation should fail for a table missing required columns."""
        # Create table missing required columns
        data = [
            {
                "timestamp": "2024-01-01 12:00:00",
                "author": "user1",
                # Missing: date, message, original_line, tagged_line, message_id
            }
        ]
        table = ibis.memtable(data)

        is_valid, errors = validate_ir_schema(table)

        assert not is_valid
        assert len(errors) > 0
        assert any("message" in err for err in errors)

    def test_validate_ir_schema_with_wrong_types(self):
        """Validation should fail for columns with incompatible types."""
        # Create table with wrong types
        data = [
            {
                "timestamp": "2024-01-01 12:00:00",
                "date": "2024-01-01",
                "author": 123,  # Should be string, not int
                "message": "Hello",
                "original_line": "raw",
                "tagged_line": "tagged",
                "message_id": "123",
            }
        ]
        table = ibis.memtable(data)

        is_valid, _errors = validate_ir_schema(table)

        # The validation will fail because author is int instead of string
        assert not is_valid

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
        is_valid, errors = validate_ir_schema(ir_table)
        assert is_valid, f"IR table validation failed: {errors}"

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
        assert result["author_uuid"][0] == deterministic_author_uuid("alice")
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
        expected_uuid = deterministic_author_uuid("user1", namespace=uuid.uuid5(uuid.NAMESPACE_DNS, "custom"))
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
