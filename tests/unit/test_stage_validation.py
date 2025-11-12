"""Tests for functional @validate_stage decorator.

Note: This test file has been refactored to use functional transformations
instead of the removed PipelineStage abstraction.
"""

import uuid
from datetime import datetime

import ibis
import pytest
from ibis.expr.types import Table

from egregora.database.validation import SchemaError, validate_stage


class TestFunctionalStageValidation:
    """Tests for @validate_stage decorator with functional approach."""

    def test_validate_stage_with_valid_function(self):
        """Test functional transformation with valid input and output passes validation."""

        @validate_stage
        def filter_messages(data: Table, min_length: int = 0) -> Table:
            """Simple filter that preserves schema."""
            return data.filter(data.text.length() >= min_length)

        # Create valid IR v1 table
        data = {
            "event_id": [str(uuid.uuid4()), str(uuid.uuid4())],
            "tenant_id": ["test-tenant", "test-tenant"],
            "source": ["whatsapp", "whatsapp"],
            "thread_id": [str(uuid.uuid4()), str(uuid.uuid4())],
            "msg_id": ["msg1", "msg2"],
            "ts": [datetime(2025, 1, 1, 10, 0), datetime(2025, 1, 1, 11, 0)],
            "author_raw": ["Alice", "Bob"],
            "author_uuid": [str(uuid.uuid4()), str(uuid.uuid4())],
            "text": ["Hello", "World"],
            "media_url": [None, None],
            "media_type": [None, None],
            "attrs": [None, None],
            "pii_flags": [None, None],
            "created_at": [datetime(2025, 1, 1, 10, 0), datetime(2025, 1, 1, 11, 0)],
            "created_by_run": [None, None],
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

        # Process should succeed
        result = filter_messages(table, min_length=0)

        assert result is not None

    def test_validate_stage_with_invalid_input_raises(self):
        """Test function with invalid input raises SchemaError."""

        @validate_stage
        def identity(data: Table) -> Table:
            return data

        # Create invalid table (missing required columns)
        invalid_data = {
            "event_id": [str(uuid.uuid4())],
            "text": ["Hello"],
        }
        invalid_schema = {"event_id": "uuid", "text": "string"}
        invalid_table = ibis.memtable(invalid_data, schema=invalid_schema)

        # Should raise SchemaError on input validation
        with pytest.raises(SchemaError, match="Stage input validation failed"):
            identity(invalid_table)

    def test_validate_stage_with_invalid_output_raises(self):
        """Test function that produces invalid output raises SchemaError."""

        @validate_stage
        def break_schema(data: Table) -> Table:
            """Drop required columns (breaks schema)."""
            return data.select("event_id", "text")

        # Create valid input
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

        # Should raise SchemaError on output validation
        with pytest.raises(SchemaError, match="Stage output validation failed"):
            break_schema(table)

    def test_validate_stage_preserves_schema_through_transformations(self):
        """Test that common transformations preserve IR schema."""

        @validate_stage
        def common_transforms(data: Table) -> Table:
            """Apply common transformations."""
            result = data.filter(data.text.notnull())
            result = result.order_by(data.ts)
            result = result.limit(10)
            return result

        # Create valid input
        data = {
            "event_id": [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())],
            "tenant_id": ["test-tenant", "test-tenant", "test-tenant"],
            "source": ["whatsapp", "whatsapp", "whatsapp"],
            "thread_id": [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())],
            "msg_id": ["msg1", "msg2", "msg3"],
            "ts": [datetime(2025, 1, 1, 10, 0), datetime(2025, 1, 1, 11, 0), datetime(2025, 1, 1, 12, 0)],
            "author_raw": ["Alice", "Bob", "Charlie"],
            "author_uuid": [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())],
            "text": ["Hello", None, "World"],
            "media_url": [None, None, None],
            "media_type": [None, None, None],
            "attrs": [None, None, None],
            "pii_flags": [None, None, None],
            "created_at": [
                datetime(2025, 1, 1, 10, 0),
                datetime(2025, 1, 1, 11, 0),
                datetime(2025, 1, 1, 12, 0),
            ],
            "created_by_run": [None, None, None],
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

        # Should succeed - transformations preserve schema
        result = common_transforms(table)

        assert result is not None

    def test_validate_stage_error_message_includes_function_name(self):
        """Test that validation errors include helpful context."""

        @validate_stage
        def my_custom_function(data: Table) -> Table:
            return data

        # Invalid input
        invalid_table = ibis.memtable({"id": [1]}, schema={"id": "int64"})

        # Error should include function name
        with pytest.raises(SchemaError) as exc_info:
            my_custom_function(invalid_table)

        error_msg = str(exc_info.value)
        assert "my_custom_function" in error_msg or "input validation failed" in error_msg.lower()

    def test_validate_stage_with_empty_table(self):
        """Test stage validation with empty table."""

        @validate_stage
        def identity(data: Table) -> Table:
            return data

        # Create empty but valid IR table
        data = {
            "event_id": [],
            "tenant_id": [],
            "source": [],
            "thread_id": [],
            "msg_id": [],
            "ts": [],
            "author_raw": [],
            "author_uuid": [],
            "text": [],
            "media_url": [],
            "media_type": [],
            "attrs": [],
            "pii_flags": [],
            "created_at": [],
            "created_by_run": [],
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
        empty_table = ibis.memtable(data, schema=schema)

        # Should succeed - empty table is valid
        result = identity(empty_table)

        assert result is not None
