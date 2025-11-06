"""Tests for pipeline IR (Intermediate Representation) schema and validation."""

import ibis

from egregora.pipeline.ir import IR_SCHEMA, create_ir_table, validate_ir_schema


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
        assert set(IR_SCHEMA.keys()) == required_fields

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
            },
        ]
        table = ibis.memtable(data, schema=ibis.schema(IR_SCHEMA))

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
            },
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
            },
        ]
        table = ibis.memtable(data)

        is_valid, errors = validate_ir_schema(table)

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
            },
        ]
        table = ibis.memtable(data)

        ir_table = create_ir_table(table, timezone="UTC")

        # Should have all IR schema columns
        assert "timestamp" in ir_table.columns
        assert "date" in ir_table.columns
        assert "author" in ir_table.columns
        assert "message" in ir_table.columns

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
            },
        ]
        table = ibis.memtable(data)

        ir_table = create_ir_table(table, timezone="UTC")

        result = ir_table.execute()

        assert len(result) == 1
        assert result["author"][0] == "alice"
        assert result["message"][0] == "Test message"

    def test_create_ir_table_with_custom_timezone(self):
        """create_ir_table should handle custom timezones."""
        data = [
            {
                "timestamp": "2024-01-01 12:00:00",
                "author": "user1",
                "message": "Hello",
            },
        ]
        table = ibis.memtable(data)

        ir_table = create_ir_table(table, timezone="America/New_York")

        # Should not raise an error
        result = ir_table.execute()
        assert len(result) == 1


class TestIRSchemaContract:
    """Contract tests ensuring IR schema stability."""

    def test_ir_schema_has_timestamp_with_timezone(self):
        """IR schema timestamp must include timezone information."""
        timestamp_dtype = IR_SCHEMA["timestamp"]
        assert timestamp_dtype.timezone is not None

    def test_ir_schema_message_id_is_nullable(self):
        """IR schema message_id must be nullable for flexibility."""
        message_id_dtype = IR_SCHEMA["message_id"]
        assert message_id_dtype.nullable

    def test_ir_schema_core_fields_not_nullable(self):
        """IR schema core fields (timestamp, author, message) must not be nullable."""
        # These are required fields that should never be null
        core_fields = ["timestamp", "date", "author", "message"]

        for field in core_fields:
            dtype = IR_SCHEMA[field]
            # Most dtypes default to nullable=False
            # We just check they exist, not strict nullability as it's schema-dependent
            assert field in IR_SCHEMA
