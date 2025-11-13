"""Property-based tests for deterministic UUID generation.

Tests verify that UUID5 namespace generation is:
1. Deterministic: Same inputs → same outputs
2. Isolated: Different tenants → different UUIDs
3. Source-aware: Different sources → different UUIDs
"""

from __future__ import annotations

import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from egregora.privacy.uuid_namespaces import (
    EGREGORA_NAMESPACE,
    NAMESPACE_AUTHOR,
    NAMESPACE_EVENT,
    NAMESPACE_THREAD,
    NamespaceContext,
    deterministic_author_uuid,
    deterministic_event_uuid,
)


class TestFrozenNamespaces:
    """Test that base namespaces are frozen constants."""

    def test_egregora_namespace_is_uuid(self):
        """EGREGORA_NAMESPACE is a valid UUID."""
        assert isinstance(EGREGORA_NAMESPACE, uuid.UUID)

    def test_author_namespace_is_uuid(self):
        """NAMESPACE_AUTHOR is a valid UUID."""
        assert isinstance(NAMESPACE_AUTHOR, uuid.UUID)

    def test_event_namespace_is_uuid(self):
        """NAMESPACE_EVENT is a valid UUID."""
        assert isinstance(NAMESPACE_EVENT, uuid.UUID)

    def test_thread_namespace_is_uuid(self):
        """NAMESPACE_THREAD is a valid UUID."""
        assert isinstance(NAMESPACE_THREAD, uuid.UUID)

    def test_namespaces_are_distinct(self):
        """All base namespaces are different."""
        namespaces = {
            EGREGORA_NAMESPACE,
            NAMESPACE_AUTHOR,
            NAMESPACE_EVENT,
            NAMESPACE_THREAD,
        }
        assert len(namespaces) == 4, "All namespaces should be unique"


class TestNamespaceContext:
    """Test NamespaceContext dataclass."""

    def test_namespace_context_immutable(self):
        """NamespaceContext is frozen (immutable)."""
        ctx = NamespaceContext(tenant_id="test", source="whatsapp")
        with pytest.raises(AttributeError):
            ctx.tenant_id = "modified"  # type: ignore[misc]

    def test_author_namespace_returns_uuid(self):
        """author_namespace() returns a valid UUID."""
        ctx = NamespaceContext(tenant_id="test", source="whatsapp")
        ns = ctx.author_namespace()
        assert isinstance(ns, uuid.UUID)

    def test_event_namespace_returns_uuid(self):
        """event_namespace() returns a valid UUID."""
        ctx = NamespaceContext(tenant_id="test", source="whatsapp")
        ns = ctx.event_namespace()
        assert isinstance(ns, uuid.UUID)

    def test_thread_namespace_returns_uuid(self):
        """thread_namespace() returns a valid UUID."""
        ctx = NamespaceContext(tenant_id="test", source="whatsapp")
        ns = ctx.thread_namespace()
        assert isinstance(ns, uuid.UUID)


class TestDeterministicAuthorUUID:
    """Test deterministic_author_uuid() function."""

    def test_basic_determinism(self):
        """Same inputs produce same UUID."""
        uuid1 = deterministic_author_uuid("default", "whatsapp", "Alice")
        uuid2 = deterministic_author_uuid("default", "whatsapp", "Alice")
        assert uuid1 == uuid2

    def test_tenant_isolation(self):
        """Different tenants get different UUIDs for same author."""
        uuid_acme = deterministic_author_uuid("acme", "whatsapp", "Alice")
        uuid_default = deterministic_author_uuid("default", "whatsapp", "Alice")
        assert uuid_acme != uuid_default

    def test_source_separation(self):
        """Different sources get different UUIDs for same author."""
        uuid_whatsapp = deterministic_author_uuid("default", "whatsapp", "Alice")
        uuid_slack = deterministic_author_uuid("default", "slack", "Alice")
        assert uuid_whatsapp != uuid_slack

    def test_case_insensitive(self):
        """Author names are normalized (case-insensitive)."""
        uuid_lower = deterministic_author_uuid("default", "whatsapp", "alice")
        uuid_upper = deterministic_author_uuid("default", "whatsapp", "ALICE")
        uuid_mixed = deterministic_author_uuid("default", "whatsapp", "Alice")
        assert uuid_lower == uuid_upper == uuid_mixed

    def test_whitespace_normalized(self):
        """Leading/trailing whitespace is stripped."""
        uuid1 = deterministic_author_uuid("default", "whatsapp", "Alice")
        uuid2 = deterministic_author_uuid("default", "whatsapp", "  Alice  ")
        assert uuid1 == uuid2


class TestDeterministicEventUUID:
    """Test deterministic_event_uuid() function."""

    def test_basic_determinism(self):
        """Same inputs produce same UUID."""
        uuid1 = deterministic_event_uuid("default", "whatsapp", "msg-123", "2025-01-08T10:00:00Z")
        uuid2 = deterministic_event_uuid("default", "whatsapp", "msg-123", "2025-01-08T10:00:00Z")
        assert uuid1 == uuid2

    def test_different_message_ids(self):
        """Different message IDs produce different UUIDs."""
        uuid1 = deterministic_event_uuid("default", "whatsapp", "msg-123", "2025-01-08T10:00:00Z")
        uuid2 = deterministic_event_uuid("default", "whatsapp", "msg-456", "2025-01-08T10:00:00Z")
        assert uuid1 != uuid2

    def test_different_timestamps(self):
        """Different timestamps produce different UUIDs."""
        uuid1 = deterministic_event_uuid("default", "whatsapp", "msg-123", "2025-01-08T10:00:00Z")
        uuid2 = deterministic_event_uuid("default", "whatsapp", "msg-123", "2025-01-08T11:00:00Z")
        assert uuid1 != uuid2


# ============================================================================
# Property-Based Tests (Hypothesis)
# ============================================================================


@given(
    tenant_id=st.text(min_size=1, max_size=50),
    source=st.text(min_size=1, max_size=20),
    author=st.text(min_size=1, max_size=100),
)
def test_uuid5_determinism_property(tenant_id: str, source: str, author: str):
    """Property test: Same inputs always produce same UUID."""
    uuid1 = deterministic_author_uuid(tenant_id, source, author)
    uuid2 = deterministic_author_uuid(tenant_id, source, author)
    assert uuid1 == uuid2
    assert isinstance(uuid1, uuid.UUID)


@given(
    tenant1=st.text(min_size=1, max_size=50),
    tenant2=st.text(min_size=1, max_size=50),
    source=st.text(min_size=1, max_size=20),
    author=st.text(min_size=1, max_size=100),
)
def test_tenant_isolation_property(tenant1: str, tenant2: str, source: str, author: str):
    """Property test: Different tenants → different UUIDs (unless same tenant)."""
    uuid1 = deterministic_author_uuid(tenant1, source, author)
    uuid2 = deterministic_author_uuid(tenant2, source, author)

    if tenant1 == tenant2:
        assert uuid1 == uuid2
    else:
        assert uuid1 != uuid2


@given(
    tenant_id=st.text(min_size=1, max_size=50),
    source1=st.text(min_size=1, max_size=20),
    source2=st.text(min_size=1, max_size=20),
    author=st.text(min_size=1, max_size=100),
)
def test_source_separation_property(tenant_id: str, source1: str, source2: str, author: str):
    """Property test: Different sources → different UUIDs (unless same source)."""
    uuid1 = deterministic_author_uuid(tenant_id, source1, author)
    uuid2 = deterministic_author_uuid(tenant_id, source2, author)

    if source1 == source2:
        assert uuid1 == uuid2
    else:
        assert uuid1 != uuid2


@given(
    tenant_id=st.text(min_size=1, max_size=50),
    source=st.text(min_size=1, max_size=20),
    msg_id=st.text(min_size=1, max_size=100),
    timestamp=st.text(min_size=1, max_size=50),
)
def test_event_uuid_determinism_property(tenant_id: str, source: str, msg_id: str, timestamp: str):
    """Property test: Event UUIDs are deterministic."""
    uuid1 = deterministic_event_uuid(tenant_id, source, msg_id, timestamp)
    uuid2 = deterministic_event_uuid(tenant_id, source, msg_id, timestamp)
    assert uuid1 == uuid2
    assert isinstance(uuid1, uuid.UUID)
