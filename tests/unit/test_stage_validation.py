"""Tests for stage validation (Priority C.3)."""

import uuid
from datetime import datetime
from typing import Any

import ibis
import pytest
from ibis.expr.types import Table

from egregora.database.validation import SchemaError, validate_stage
from egregora.pipeline.base import PipelineStage, StageConfig, StageResult


class TestStageValidation:
    """Tests for @validate_stage decorator."""

    def test_validate_stage_with_valid_input_output(self):
        """Test stage with valid input and output passes validation."""

        class ValidStage(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "Valid Stage"

            @property
            def stage_identifier(self) -> str:
                return "valid"

            @validate_stage
            def process(self, data: Table, context: dict[str, Any]) -> StageResult:
                # Simple filter that preserves schema
                filtered = data.filter(data.text.notnull())
                return StageResult(data=filtered)

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
        config = StageConfig()
        stage = ValidStage(config)
        result = stage.process(table, {})

        assert isinstance(result, StageResult)
        assert result.data is not None

    def test_validate_stage_with_invalid_input_raises(self):
        """Test stage with invalid input raises SchemaError."""

        class TestStage(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "Test Stage"

            @property
            def stage_identifier(self) -> str:
                return "test"

            @validate_stage
            def process(self, data: Table, context: dict[str, Any]) -> StageResult:
                return StageResult(data=data)

        # Create invalid table (missing required columns)
        invalid_data = {
            "event_id": [str(uuid.uuid4())],
            "text": ["Hello"],
        }
        invalid_schema = {"event_id": "uuid", "text": "string"}
        invalid_table = ibis.memtable(invalid_data, schema=invalid_schema)

        # Should raise SchemaError on input validation
        config = StageConfig()
        stage = TestStage(config)
        with pytest.raises(SchemaError, match="Stage input validation failed"):
            stage.process(invalid_table, {})

    def test_validate_stage_with_invalid_output_raises(self):
        """Test stage that produces invalid output raises SchemaError."""

        class BreaksSchemaStage(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "Schema Breaker"

            @property
            def stage_identifier(self) -> str:
                return "breaker"

            @validate_stage
            def process(self, data: Table, context: dict[str, Any]) -> StageResult:
                # Drop required columns (breaks schema)
                broken = data.select("event_id", "text")
                return StageResult(data=broken)

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
        config = StageConfig()
        stage = BreaksSchemaStage(config)
        with pytest.raises(SchemaError, match="Stage output validation failed"):
            stage.process(table, {})

    def test_validate_stage_preserves_schema_through_transformations(self):
        """Test that common transformations preserve IR schema."""

        class TransformStage(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "Transform Stage"

            @property
            def stage_identifier(self) -> str:
                return "transform"

            @validate_stage
            def process(self, data: Table, context: dict[str, Any]) -> StageResult:
                # Common transformations
                result = data.filter(data.text.notnull())
                result = result.order_by(data.ts)
                result = result.limit(10)
                return StageResult(data=result)

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
        config = StageConfig()
        stage = TransformStage(config)
        result = stage.process(table, {})

        assert isinstance(result, StageResult)

    def test_validate_stage_error_message_includes_stage_name(self):
        """Test that validation errors include helpful context."""

        class MyCustomStage(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "My Custom Stage"

            @property
            def stage_identifier(self) -> str:
                return "custom"

            @validate_stage
            def process(self, data: Table, context: dict[str, Any]) -> StageResult:
                return StageResult(data=data)

        # Invalid input
        invalid_table = ibis.memtable({"id": [1]}, schema={"id": "int64"})

        config = StageConfig()
        stage = MyCustomStage(config)

        # Error should include stage method name
        with pytest.raises(SchemaError) as exc_info:
            stage.process(invalid_table, {})

        error_msg = str(exc_info.value)
        assert "MyCustomStage.process" in error_msg or "process" in error_msg
        assert "input validation failed" in error_msg.lower()

    def test_validate_stage_with_empty_table(self):
        """Test stage validation with empty table."""

        class EmptyHandlerStage(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "Empty Handler"

            @property
            def stage_identifier(self) -> str:
                return "empty"

            @validate_stage
            def process(self, data: Table, context: dict[str, Any]) -> StageResult:
                return StageResult(data=data)

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
        config = StageConfig()
        stage = EmptyHandlerStage(config)
        result = stage.process(empty_table, {})

        assert isinstance(result, StageResult)

    def test_validate_stage_without_enough_args_raises_typeerror(self):
        """Test that decorator raises TypeError if signature is wrong."""

        class BadStage(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "Bad Stage"

            @property
            def stage_identifier(self) -> str:
                return "bad"

            @validate_stage
            def process(self, data: Table, context: dict[str, Any]) -> StageResult:
                return StageResult(data=data)

        config = StageConfig()
        stage = BadStage(config)

        # Call with too few args (missing data)
        with pytest.raises(TypeError, match="requires at least 2 arguments"):
            stage.process()  # type: ignore[call-arg]
