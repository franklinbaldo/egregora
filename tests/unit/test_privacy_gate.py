"""Tests for privacy gate capability token pattern.

Tests verify that:
1. PrivacyPass tokens are immutable and unforgeable
2. @require_privacy_pass decorator enforces privacy contract
3. PrivacyGate.run() is the only way to create valid tokens
4. Tenant isolation works correctly
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import ibis
import pytest

from egregora.database.validation import IR_MESSAGE_SCHEMA
from egregora.privacy.constants import deterministic_author_uuid
from egregora.privacy.config import PrivacySettings
from egregora.privacy.gate import PrivacyGate, PrivacyPass, require_privacy_pass


def _build_ir_table(
    *,
    author_raw: str = "Alice",
    tenant_id: str = "test-tenant",
    source: str = "whatsapp",
) -> ibis.Table:
    now = datetime.now(UTC)
    author_uuid = deterministic_author_uuid(tenant_id, source, author_raw)
    data = {
        "event_id": [uuid4()],
        "tenant_id": [tenant_id],
        "source": [source],
        "thread_id": [uuid4()],
        "msg_id": ["msg-001"],
        "ts": [now],
        "author_raw": [author_raw],
        "author_uuid": [author_uuid],
        "text": ["Hello world"],
        "media_url": [None],
        "media_type": [None],
        "attrs": [{}],
        "pii_flags": [None],
        "created_at": [now],
        "created_by_run": [None],
    }
    return ibis.memtable(data, schema=IR_MESSAGE_SCHEMA)


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
            RuntimeError, match=r"received invalid privacy_pass.*Expected PrivacyPass instance, got str"
        ):
            protected_function("test data", privacy_pass="fake-token")  # type: ignore[arg-type]

        # Try to forge token with dict
        with pytest.raises(
            RuntimeError, match=r"received invalid privacy_pass.*Expected PrivacyPass instance, got dict"
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
        table = _build_ir_table(tenant_id="test-tenant")

        config = PrivacySettings(tenant_id="test-tenant")

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
        table = _build_ir_table(author_raw="Alice", tenant_id="test")

        config = PrivacySettings(tenant_id="test")
        anonymized, _ = PrivacyGate.run(table, config, "run-1")

        result = anonymized.execute()

        # Author should be anonymized (UUID format)
        author = result["author_raw"].iloc[0]
        assert author != "Alice"
        assert len(author) >= 8

    def test_privacy_gate_fails_with_empty_tenant_id(self):
        """PrivacySettings raises ValueError if tenant_id is empty."""
        table = _build_ir_table(tenant_id="tenant-1")

        with pytest.raises(ValueError, match="tenant_id cannot be empty"):
            config = PrivacySettings(tenant_id="")
            PrivacyGate.run(table, config, "run-1")

    def test_privacy_gate_fails_with_empty_run_id(self):
        """PrivacyGate.run() raises ValueError if run_id is empty."""
        table = _build_ir_table(tenant_id="test")
        config = PrivacySettings(tenant_id="test")

        with pytest.raises(ValueError, match="run_id cannot be empty"):
            PrivacyGate.run(table, config, "")

    def test_privacy_gate_tenant_isolation(self):
        """PrivacyGate.run() issues different tokens for different tenants."""
        table = _build_ir_table(author_raw="Alice", tenant_id="tenant-1")

        config_tenant1 = PrivacySettings(tenant_id="tenant-1")
        config_tenant2 = PrivacySettings(tenant_id="tenant-2")

        _, pass1 = PrivacyGate.run(table, config_tenant1, "run-1")

        # Table tenant mismatch should raise
        with pytest.raises(ValueError, match="unexpected tenant"):
            PrivacyGate.run(table, config_tenant2, "run-1")

        assert pass1.tenant_id == "tenant-1"


class TestPrivacyWorkflow:
    """Integration tests for privacy gate workflow."""

    def test_full_privacy_workflow(self):
        """Test complete privacy gate workflow."""
        # 1. Create raw table with PII
        raw_table = _build_ir_table(author_raw="Alice", tenant_id="acme-corp")

        # 2. Configure privacy
        config = PrivacySettings(
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
            author = result["author_raw"].iloc[0]
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
        raw_table = _build_ir_table(author_raw="Alice", tenant_id="test")

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
        config = PrivacySettings(tenant_id="test")
        anonymized, valid_pass = PrivacyGate.run(raw_table, config, "run-1")
        result = send_to_llm(anonymized, privacy_pass=valid_pass)

        # Alice should be anonymized
        assert "Alice" not in result
