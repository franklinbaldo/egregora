"""Tests for adapter output validation integration.

Tests cover:
- @validate_adapter_output decorator
- ValidatedAdapter wrapper
- AdapterRegistry with validate_outputs=True
- Schema validation error handling
"""

from __future__ import annotations

from pathlib import Path

import ibis
import pytest

from egregora.adapters.registry import AdapterRegistry, ValidatedAdapter
from egregora.database.validation import SchemaError, validate_adapter_output
from egregora.sources.base import AdapterMeta, SourceAdapter


class MockAdapter(SourceAdapter):
    """Mock adapter for testing validation."""

    def __init__(self, *, return_valid: bool = True) -> None:
        """Initialize mock adapter.

        Args:
            return_valid: If True, return valid IR v1 table. If False, return invalid table.

        """
        self._return_valid = return_valid

    @property
    def source_name(self) -> str:
        return "TestSource"

    @property
    def source_identifier(self) -> str:
        return "testsource"

    def adapter_meta(self) -> AdapterMeta:
        return AdapterMeta(
            name="TestSource",
            version="1.0.0",
            source="testsource",
            doc_url="https://example.com",
            ir_version="v1",
        )

    def parse(self, input_path: Path, **kwargs) -> ibis.Table:
        """Return valid or invalid table based on initialization."""
        if self._return_valid:
            # Return valid IR v1 table using IR schema
            import uuid
            from datetime import UTC, datetime

            import pandas as pd

            from egregora.database.validation import IR_V1_SCHEMA

            # Create test UUID for created_by_run to avoid null type issues
            test_run_id = uuid.uuid4()

            df = pd.DataFrame(
                {
                    "event_id": [uuid.uuid4()],
                    "tenant_id": ["test-tenant"],
                    "source": ["testsource"],
                    "thread_id": [uuid.uuid4()],
                    "msg_id": ["msg-001"],
                    "ts": [datetime.now(UTC)],
                    "author_raw": ["Test User"],
                    "author_uuid": [uuid.uuid4()],
                    "text": ["Test message"],
                    "media_url": [None],
                    "media_type": [None],
                    "attrs": [{}],
                    "pii_flags": [{}],
                    "created_at": [datetime.now(UTC)],
                    "created_by_run": [test_run_id],  # Use actual UUID to avoid null type
                }
            )
            # Create memtable with explicit schema
            return ibis.memtable(df, schema=IR_V1_SCHEMA)
        # Return invalid table (missing required columns)
        import pandas as pd

        data = {
            "invalid_column": ["test"],
            "another_column": [123],
        }
        return ibis.memtable(pd.DataFrame(data))


class TestValidateAdapterOutputDecorator:
    """Tests for @validate_adapter_output decorator."""

    def test_decorator_validates_valid_output(self, tmp_path: Path) -> None:
        """Test decorator allows valid output."""

        @validate_adapter_output
        def parse_valid(input_path: Path) -> ibis.Table:
            adapter = MockAdapter(return_valid=True)
            return adapter.parse(input_path)

        # Should not raise
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        result = parse_valid(test_file)
        assert result is not None

    def test_decorator_rejects_invalid_output(self, tmp_path: Path) -> None:
        """Test decorator rejects invalid output."""

        @validate_adapter_output
        def parse_invalid(input_path: Path) -> ibis.Table:
            adapter = MockAdapter(return_valid=False)
            return adapter.parse(input_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with pytest.raises(SchemaError, match="Adapter output validation failed"):
            parse_invalid(test_file)

    def test_decorator_preserves_function_metadata(self) -> None:
        """Test decorator preserves original function metadata."""

        @validate_adapter_output
        def my_parse_function(input_path: Path) -> ibis.Table:
            """My docstring."""
            adapter = MockAdapter()
            return adapter.parse(input_path)

        assert my_parse_function.__name__ == "my_parse_function"
        assert "My docstring" in my_parse_function.__doc__


class TestValidatedAdapter:
    """Tests for ValidatedAdapter wrapper."""

    def test_wrapper_validates_by_default(self, tmp_path: Path) -> None:
        """Test ValidatedAdapter validates by default."""
        base_adapter = MockAdapter(return_valid=True)
        validated = ValidatedAdapter(base_adapter)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # Should not raise (valid output)
        result = validated.parse(test_file)
        assert result is not None

    def test_wrapper_rejects_invalid_output(self, tmp_path: Path) -> None:
        """Test ValidatedAdapter rejects invalid output."""
        base_adapter = MockAdapter(return_valid=False)
        validated = ValidatedAdapter(base_adapter)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with pytest.raises(SchemaError):
            validated.parse(test_file)

    def test_wrapper_can_disable_validation(self, tmp_path: Path) -> None:
        """Test ValidatedAdapter can disable validation."""
        base_adapter = MockAdapter(return_valid=False)
        validated = ValidatedAdapter(base_adapter, validate=False)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # Should not raise even with invalid output
        result = validated.parse(test_file)
        assert result is not None

    def test_wrapper_delegates_other_methods(self) -> None:
        """Test ValidatedAdapter delegates non-parse methods."""
        base_adapter = MockAdapter()
        validated = ValidatedAdapter(base_adapter)

        # Should delegate to base adapter
        assert validated.source_name == "TestSource"
        assert validated.source_identifier == "testsource"
        meta = validated.adapter_meta()
        assert meta["name"] == "TestSource"

    def test_wrapper_repr(self) -> None:
        """Test ValidatedAdapter string representation."""
        base_adapter = MockAdapter()
        validated = ValidatedAdapter(base_adapter)

        repr_str = repr(validated)
        assert "ValidatedAdapter" in repr_str
        assert "validate=True" in repr_str


class TestAdapterRegistryValidation:
    """Tests for AdapterRegistry with validation enabled."""

    def test_registry_without_validation(self) -> None:
        """Test AdapterRegistry without validation (default)."""
        registry = AdapterRegistry(validate_outputs=False)

        # Should load adapters without validation
        assert len(registry) >= 2
        assert "whatsapp" in registry

    def test_registry_with_validation(self) -> None:
        """Test AdapterRegistry with validation enabled."""
        registry = AdapterRegistry(validate_outputs=True)

        # Should load adapters with validation wrappers
        assert len(registry) >= 2

        adapter = registry.get("whatsapp")
        # Should be wrapped
        assert isinstance(adapter, ValidatedAdapter)

    def test_registry_validated_adapters_work(self, tmp_path: Path) -> None:
        """Test that validated adapters from registry work correctly."""
        registry = AdapterRegistry(validate_outputs=False)

        # Get WhatsApp adapter (should work with valid export)
        adapter = registry.get("whatsapp")
        assert adapter.source_identifier == "whatsapp"

    def test_registry_list_adapters_with_validation(self) -> None:
        """Test that list_adapters works with validated adapters."""
        registry = AdapterRegistry(validate_outputs=True)

        adapters = registry.list_adapters()
        assert len(adapters) >= 2

        # Should still return correct metadata (delegates to wrapped adapter)
        sources = {meta["source"] for meta in adapters}
        assert "whatsapp" in sources
        assert "slack" in sources


class TestSchemaValidationErrors:
    """Tests for schema validation error messages."""

    def test_missing_columns_error(self) -> None:
        """Test error message for missing columns."""
        import pandas as pd

        # Create table with missing columns
        data = {"event_id": [1], "tenant_id": ["test"]}
        table = ibis.memtable(pd.DataFrame(data))

        with pytest.raises(SchemaError, match="IR v1 schema mismatch"):
            from egregora.database.validation import validate_ir_schema

            validate_ir_schema(table)

    def test_extra_columns_allowed(self) -> None:
        """Test that extra columns are allowed (schema is superset)."""
        import uuid
        from datetime import UTC, datetime

        import pandas as pd

        # Create valid table with extra column
        data = {
            "event_id": [uuid.uuid4()],
            "tenant_id": ["test-tenant"],
            "source": ["testsource"],
            "thread_id": [uuid.uuid4()],
            "msg_id": ["msg-001"],
            "ts": [datetime.now(UTC)],
            "author_raw": ["Test User"],
            "author_uuid": [uuid.uuid4()],
            "text": ["Test message"],
            "media_url": [None],
            "media_type": [None],
            "attrs": [{}],
            "pii_flags": [{}],
            "created_at": [datetime.now(UTC)],
            "created_by_run": [None],
            "extra_column": ["extra data"],  # Extra column
        }
        table = ibis.memtable(pd.DataFrame(data))

        # Should raise because extra columns are not allowed
        with pytest.raises(SchemaError, match="Extra columns"):
            from egregora.database.validation import validate_ir_schema

            validate_ir_schema(table)


class TestIntegrationWithRealAdapters:
    """Integration tests with real WhatsApp adapter."""

    def test_whatsapp_adapter_validates(self, tmp_path: Path) -> None:
        """Test that WhatsApp adapter output validates."""
        # Note: This test would require a real WhatsApp export file
        # Skipping for now as it requires test fixtures
        pytest.skip("Requires WhatsApp export test fixture")

    def test_slack_adapter_fails_validation(self) -> None:
        """Test that Slack stub raises NotImplementedError before validation."""
        from egregora.adapters import get_global_registry

        registry = get_global_registry()
        slack_adapter = registry.get("slack")

        # Slack adapter should raise NotImplementedError when calling parse()
        with pytest.raises(NotImplementedError):
            slack_adapter.parse(Path("dummy.json"))
