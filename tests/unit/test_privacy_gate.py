"""Tests for privacy gate capability token pattern.

Tests verify that:
1. PrivacyPass tokens are immutable and unforgeable
2. @require_privacy_pass decorator enforces privacy contract
3. PrivacyGate.run() is the only way to create valid tokens
4. Tenant isolation works correctly
"""

from __future__ import annotations

from datetime import UTC, datetime

import ibis
import pytest

from egregora.privacy.config import PrivacyConfig
from egregora.privacy.gate import PrivacyGate, PrivacyPass, require_privacy_pass


class TestPrivacyPass:
    """Test PrivacyPass capability token."""

    def test_privacy_pass_is_named_tuple(self):
        """PrivacyPass is a NamedTuple (immutable)."""
        privacy_pass = PrivacyPass(
            ir_version="1.0.0",
            run_id="test-run",
            tenant_id="default",
            timestamp=datetime.now(UTC),
        )

        assert isinstance(privacy_pass, tuple)
        assert hasattr(privacy_pass, "ir_version")
        assert hasattr(privacy_pass, "run_id")
        assert hasattr(privacy_pass, "tenant_id")
        assert hasattr(privacy_pass, "timestamp")

    def test_privacy_pass_is_immutable(self):
        """PrivacyPass cannot be modified after creation."""
        privacy_pass = PrivacyPass(
            ir_version="1.0.0",
            run_id="test-run",
            tenant_id="default",
            timestamp=datetime.now(UTC),
        )

        with pytest.raises(AttributeError):
            privacy_pass.tenant_id = "modified"  # type: ignore[misc]

    def test_privacy_pass_fields(self):
        """PrivacyPass contains expected fields."""
        now = datetime.now(UTC)
        privacy_pass = PrivacyPass(
            ir_version="1.0.0",
            run_id="run-123",
            tenant_id="acme-corp",
            timestamp=now,
        )

        assert privacy_pass.ir_version == "1.0.0"
        assert privacy_pass.run_id == "run-123"
        assert privacy_pass.tenant_id == "acme-corp"
        assert privacy_pass.timestamp == now


class TestRequirePrivacyPassDecorator:
    """Test @require_privacy_pass decorator enforcement."""

    def test_decorator_allows_valid_privacy_pass(self):
        """Decorator allows function to proceed with valid PrivacyPass."""

        @require_privacy_pass
        def protected_function(data: str, *, privacy_pass: PrivacyPass) -> str:
            return f"Processed: {data}"

        valid_pass = PrivacyPass(
            ir_version="1.0.0",
            run_id="test",
            tenant_id="default",
            timestamp=datetime.now(UTC),
        )

        result = protected_function("test data", privacy_pass=valid_pass)
        assert result == "Processed: test data"

    def test_decorator_fails_without_privacy_pass(self):
        """Decorator raises RuntimeError if privacy_pass is missing."""

        @require_privacy_pass
        def protected_function(data: str, *, privacy_pass: PrivacyPass) -> str:
            return f"Processed: {data}"

        with pytest.raises(RuntimeError, match="protected_function requires PrivacyPass capability"):
            protected_function("test data")  # type: ignore[call-arg]

    def test_decorator_fails_with_none_privacy_pass(self):
        """Decorator raises RuntimeError if privacy_pass is None."""

        @require_privacy_pass
        def protected_function(data: str, *, privacy_pass: PrivacyPass) -> str:
            return f"Processed: {data}"

        with pytest.raises(RuntimeError, match="protected_function requires PrivacyPass capability"):
            protected_function("test data", privacy_pass=None)  # type: ignore[arg-type]

    def test_decorator_fails_with_forged_token(self):
        """Decorator raises RuntimeError if privacy_pass is not PrivacyPass instance."""

        @require_privacy_pass
        def protected_function(data: str, *, privacy_pass: PrivacyPass) -> str:
            return f"Processed: {data}"

        # Try to forge token with string
        with pytest.raises(
            RuntimeError, match="received invalid privacy_pass.*Expected PrivacyPass instance, got str"
        ):
            protected_function("test data", privacy_pass="fake-token")  # type: ignore[arg-type]

        # Try to forge token with dict
        with pytest.raises(
            RuntimeError, match="received invalid privacy_pass.*Expected PrivacyPass instance, got dict"
        ):
            protected_function("test data", privacy_pass={"fake": "token"})  # type: ignore[arg-type]

    def test_decorator_preserves_function_metadata(self):
        """Decorator preserves function name and docstring."""

        @require_privacy_pass
        def my_function(*, privacy_pass: PrivacyPass) -> str:
            """This is my function."""
            return "result"

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "This is my function."


class TestPrivacyGate:
    """Test PrivacyGate.run() token issuer."""

    def test_privacy_gate_returns_anonymized_table_and_token(self):
        """PrivacyGate.run() returns (anonymized_table, privacy_pass)."""
        # Create test table
        data = {
            "timestamp": [datetime.now(UTC)],
            "author": ["Alice"],
            "message": ["Hello world"],
        }
        table = ibis.memtable(data)

        config = PrivacyConfig(tenant_id="test-tenant")

        anonymized, privacy_pass = PrivacyGate.run(table, config, "run-123")

        # Check anonymized table is returned
        assert isinstance(anonymized, ibis.Table)

        # Check privacy_pass is valid PrivacyPass
        assert isinstance(privacy_pass, PrivacyPass)
        assert privacy_pass.ir_version == "1.0.0"
        assert privacy_pass.run_id == "run-123"
        assert privacy_pass.tenant_id == "test-tenant"
        assert isinstance(privacy_pass.timestamp, datetime)

    def test_privacy_gate_anonymizes_authors(self):
        """PrivacyGate.run() anonymizes author column."""
        data = {
            "timestamp": [datetime.now(UTC)],
            "author": ["Alice"],
            "message": ["Hello"],
        }
        table = ibis.memtable(data)

        config = PrivacyConfig(tenant_id="test")
        anonymized, _ = PrivacyGate.run(table, config, "run-1")

        result = anonymized.execute()

        # Author should be anonymized (UUID format)
        author = result["author"].iloc[0]
        assert author != "Alice"
        assert len(author) == 8  # UUID hex format (8 chars)

    def test_privacy_gate_fails_with_empty_tenant_id(self):
        """PrivacyGate.run() raises ValueError if tenant_id is empty."""
        table = ibis.memtable([{"author": ["test"]}])

        with pytest.raises(ValueError, match="tenant_id cannot be empty"):
            config = PrivacyConfig(tenant_id="")
            PrivacyGate.run(table, config, "run-1")

    def test_privacy_gate_fails_with_empty_run_id(self):
        """PrivacyGate.run() raises ValueError if run_id is empty."""
        table = ibis.memtable([{"author": ["test"]}])
        config = PrivacyConfig(tenant_id="test")

        with pytest.raises(ValueError, match="run_id cannot be empty"):
            PrivacyGate.run(table, config, "")

    def test_privacy_gate_tenant_isolation(self):
        """PrivacyGate.run() issues different tokens for different tenants."""
        data = {
            "timestamp": [datetime.now(UTC)],
            "author": ["Alice"],
            "message": ["Hello"],
        }
        table = ibis.memtable(data)

        config_tenant1 = PrivacyConfig(tenant_id="tenant-1")
        config_tenant2 = PrivacyConfig(tenant_id="tenant-2")

        _, pass1 = PrivacyGate.run(table, config_tenant1, "run-1")
        _, pass2 = PrivacyGate.run(table, config_tenant2, "run-1")

        assert pass1.tenant_id == "tenant-1"
        assert pass2.tenant_id == "tenant-2"
        assert pass1.tenant_id != pass2.tenant_id


class TestPrivacyWorkflow:
    """Integration tests for privacy gate workflow."""

    def test_full_privacy_workflow(self):
        """Test complete privacy gate workflow."""
        # 1. Create raw table with PII
        raw_data = {
            "timestamp": [datetime.now(UTC)],
            "author": ["Alice"],  # Real name (PII)
            "message": ["Hello world"],
        }
        raw_table = ibis.memtable(raw_data)

        # 2. Configure privacy
        config = PrivacyConfig(
            tenant_id="acme-corp",
            detect_pii=True,
        )

        # 3. Run privacy gate
        anonymized_table, privacy_pass = PrivacyGate.run(raw_table, config, run_id="run-123")

        # 4. Use privacy_pass with protected function
        @require_privacy_pass
        def process_anonymized_data(
            table: ibis.Table,
            *,
            privacy_pass: PrivacyPass,
        ) -> str:
            # This function is safe - decorator verified privacy_pass
            result = table.execute()
            author = result["author"].iloc[0]
            return f"Processed author: {author}"

        # 5. Call protected function with token
        result = process_anonymized_data(
            anonymized_table,
            privacy_pass=privacy_pass,
        )

        # Author should be anonymized
        assert "Alice" not in result
        assert "Processed author:" in result

    def test_cannot_bypass_privacy_gate(self):
        """Test that you cannot bypass privacy gate with forged tokens."""
        raw_data = {
            "timestamp": [datetime.now(UTC)],
            "author": ["Alice"],  # Real name (PII)
            "message": ["Hello"],
        }
        raw_table = ibis.memtable(raw_data)

        @require_privacy_pass
        def send_to_llm(table: ibis.Table, *, privacy_pass: PrivacyPass) -> str:
            result = table.execute()
            return f"LLM received: {result['author'].iloc[0]}"

        # ❌ Cannot call without privacy_pass
        with pytest.raises(RuntimeError, match="requires PrivacyPass capability"):
            send_to_llm(raw_table)  # type: ignore[call-arg]

        # ❌ Cannot forge token
        with pytest.raises(RuntimeError, match="invalid privacy_pass"):
            send_to_llm(raw_table, privacy_pass="forged")  # type: ignore[arg-type]

        # ✅ Must go through privacy gate
        config = PrivacyConfig(tenant_id="test")
        anonymized, valid_pass = PrivacyGate.run(raw_table, config, "run-1")
        result = send_to_llm(anonymized, privacy_pass=valid_pass)

        # Alice should be anonymized
        assert "Alice" not in result
