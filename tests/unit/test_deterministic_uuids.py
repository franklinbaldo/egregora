"""Property-based tests for deterministic UUID generation.

Tests verify that UUID5 namespace generation is:
1. Deterministic: Same inputs → same outputs
2. Namespace-aware: Different namespaces → different UUIDs
"""

from __future__ import annotations

import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from egregora.privacy.constants import (
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
        """NAMESPACE_AUTHOR mirrors Python's URL namespace."""
        assert isinstance(NAMESPACE_AUTHOR, uuid.UUID)
        assert NAMESPACE_AUTHOR == uuid.NAMESPACE_URL

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
        uuid1 = deterministic_author_uuid("Alice")
        uuid2 = deterministic_author_uuid("Alice")
        assert uuid1 == uuid2

    def test_case_insensitive(self):
        """Author names are normalized (case-insensitive)."""
        uuid_lower = deterministic_author_uuid("alice")
        uuid_upper = deterministic_author_uuid("ALICE")
        uuid_mixed = deterministic_author_uuid("Alice")
        assert uuid_lower == uuid_upper == uuid_mixed

    def test_whitespace_normalized(self):
        """Leading/trailing whitespace is stripped."""
        uuid1 = deterministic_author_uuid("Alice")
        uuid2 = deterministic_author_uuid("  Alice  ")
        assert uuid1 == uuid2

    def test_custom_namespace_changes_output(self):
        """Custom namespaces produce different UUIDs."""
        custom_ns = uuid.uuid5(uuid.NAMESPACE_DNS, "my-private-namespace")
        default_uuid = deterministic_author_uuid("Alice")
        custom_uuid = deterministic_author_uuid("Alice", namespace=custom_ns)
        assert default_uuid != custom_uuid


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
    author=st.text(min_size=1, max_size=100),
    namespace=st.none() | st.uuids(),
)
def test_uuid5_determinism_property(author: str, namespace: uuid.UUID | None):
    """Property test: Same inputs always produce same UUID."""
    kwargs = {"namespace": namespace} if namespace is not None else {}
    uuid1 = deterministic_author_uuid(author, **kwargs)
    uuid2 = deterministic_author_uuid(author, **kwargs)
    assert uuid1 == uuid2
    assert isinstance(uuid1, uuid.UUID)


@given(
    author=st.text(min_size=1, max_size=100),
    namespace1=st.uuids(),
    namespace2=st.uuids(),
)
def test_namespace_isolation_property(author: str, namespace1: uuid.UUID, namespace2: uuid.UUID):
    """Property test: Different namespaces produce different UUIDs."""
    uuid1 = deterministic_author_uuid(author, namespace=namespace1)
    uuid2 = deterministic_author_uuid(author, namespace=namespace2)

    if namespace1 == namespace2:
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
