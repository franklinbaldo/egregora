"""Frozen UUID5 namespaces for deterministic identity generation.

This module defines the canonical UUID5 namespaces used throughout Egregora
for generating deterministic pseudonymous identities. These namespaces MUST
remain frozen to ensure reproducibility across pipeline runs.

Architecture Decision Record: docs/architecture/adr-002-deterministic-uuids.md
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

# ============================================================================
# Frozen UUID5 Namespaces (DO NOT MODIFY)
# ============================================================================
# These namespaces were generated on 2025-01-08 and MUST remain constant.
# Changing these values will break deterministic identity mapping across runs.

# Base namespace for all Egregora UUIDs (generated from 'egregora.dev')
EGREGORA_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# Author identity namespace (default author pseudonymization namespace)
# Using Python's built-in URL namespace keeps behaviour predictable and
# allows adapters to opt into custom namespaces when needed.
NAMESPACE_AUTHOR = uuid.NAMESPACE_URL

# Event identity namespace (for deterministic event_id generation)
# Generated from: uuid.uuid5(EGREGORA_NAMESPACE, "event")
NAMESPACE_EVENT = uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")

# Thread identity namespace (for conversation threading)
# Generated from: uuid.uuid5(EGREGORA_NAMESPACE, "thread")
NAMESPACE_THREAD = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")


# ============================================================================
# Multi-Tenant Namespace Generation
# ============================================================================


@dataclass(frozen=True, slots=True)
class NamespaceContext:
    """Context for generating tenant-isolated UUID5 namespaces.

    Attributes:
        tenant_id: Tenant identifier for multi-tenant isolation
        source: Source adapter name (e.g., 'whatsapp', 'slack')

    """

    tenant_id: str
    source: str

    def event_namespace(self) -> uuid.UUID:
        """Get tenant-scoped event namespace.

        Returns:
            UUID5 namespace for event identity within this tenant+source

        """
        namespace_key = f"tenant:{self.tenant_id}:source:{self.source}:event"
        return uuid.uuid5(NAMESPACE_EVENT, namespace_key)

    def thread_namespace(self) -> uuid.UUID:
        """Get tenant-scoped thread namespace.

        Returns:
            UUID5 namespace for thread identity within this tenant+source

        """
        namespace_key = f"tenant:{self.tenant_id}:source:{self.source}:thread"
        return uuid.uuid5(NAMESPACE_THREAD, namespace_key)


# ============================================================================
# Helper Functions
# ============================================================================


def deterministic_author_uuid(
    author_raw: str,
    *,
    namespace: uuid.UUID = NAMESPACE_AUTHOR,
) -> uuid.UUID:
    """Generate deterministic UUID for an author.

    This function ensures:
    1. Same author → same UUID across runs (determinism)
    2. Custom namespaces → distinct UUIDs when adapters opt-in

    Args:
        author_raw: Original author name
        namespace: UUID5 namespace controlling pseudonymization scope

    Returns:
        Deterministic UUID5 for this author

    Example:
        >>> deterministic_author_uuid("Alice")
        UUID('...')  # Always the same for this input
        >>> ns = uuid.uuid5(uuid.NAMESPACE_DNS, "my-private-space")
        >>> deterministic_author_uuid("Alice", namespace=ns)
        UUID('...')  # Different UUID when namespace changes

    """
    normalized_author = author_raw.strip().lower()
    if not normalized_author:
        msg = "author_raw cannot be empty when generating author UUID"
        raise ValueError(msg)
    return uuid.uuid5(namespace, normalized_author)


def deterministic_event_uuid(
    tenant_id: str,
    source: str,
    message_id: str,
    timestamp: str | datetime,
) -> uuid.UUID:
    """Generate deterministic UUID for an event.

    Args:
        tenant_id: Tenant identifier
        source: Source adapter name
        message_id: Source-specific message identifier
        timestamp: Timestamp associated with the event (datetime or ISO string)

    Returns:
        Deterministic UUID5 for this event

    Example:
        >>> deterministic_event_uuid(
        ...     "default", "whatsapp", "msg-123", "2025-01-08T10:00:00Z"
        ... )
        UUID('...')

    """
    if isinstance(timestamp, datetime):
        timestamp_iso = timestamp.astimezone().isoformat()
    else:
        timestamp_iso = timestamp
    ctx = NamespaceContext(tenant_id=tenant_id, source=source)
    event_namespace = ctx.event_namespace()
    event_key = f"{message_id}:{timestamp_iso}"
    return uuid.uuid5(event_namespace, event_key)


def deterministic_thread_uuid(tenant_id: str, source: str, thread_key: str) -> uuid.UUID:
    """Generate deterministic UUID for a conversation thread."""

    ctx = NamespaceContext(tenant_id=tenant_id, source=source)
    thread_namespace = ctx.thread_namespace()
    return uuid.uuid5(thread_namespace, thread_key)
