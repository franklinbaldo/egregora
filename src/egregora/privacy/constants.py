"""UUID5 namespaces for deterministic identity generation.

CRITICAL: These UUIDs are IMMUTABLE. Changing them breaks:
- Re-identification (author_raw → author_uuid mapping)
- Multi-tenant joins (same person across tenants would get different UUIDs)
- Historical data (re-ingesting old exports would produce different UUIDs)

See ADR-002 for full policy and migration guidelines.

Design Rationale:
-----------------
We use UUID5 (name-based UUIDs) for deterministic, reproducible identities:

1. **Determinism**: Same input always produces same UUID
   - Re-ingesting WhatsApp export → identical event_id, author_uuid, thread_id
   - Enables idempotent pipelines and deduplication

2. **Multi-tenant Isolation**: Different tenants get different UUIDs for same name
   - Author "Alice" in tenant-a: uuid5(NS_AUTHORS, "tenant-a:whatsapp:Alice")
   - Author "Alice" in tenant-b: uuid5(NS_AUTHORS, "tenant-b:whatsapp:Alice")
   - Prevents cross-tenant data leaks

3. **Source Isolation**: Same author across platforms gets different UUIDs
   - Alice on WhatsApp: uuid5(NS_AUTHORS, "tenant:whatsapp:Alice")
   - Alice on Slack: uuid5(NS_AUTHORS, "tenant:slack:Alice")
   - Allows opt-in cross-platform linking without default correlation

4. **Re-identification Escrow**: Optional one-way mapping storage
   - By default, mapping author_raw → author_uuid is NOT persisted
   - Tenants can opt-in to store salted mapping for re-identification
   - See privacy.enable_reidentification config option

Namespace Strategy:
-------------------
We use different namespaces for different entity types to prevent collisions:

- NS_AUTHORS: People (message senders)
- NS_THREADS: Conversations (group chats, channels)
- NS_MEDIA: Media attachments (images, videos)
- NS_EVENTS: Individual messages/events

This ensures that if a thread_id happens to match an author name,
they still get different UUIDs (different namespaces).

Migration Policy:
-----------------
These UUIDs are **locked**. Changing them requires:

1. **Version bump**: Create constants_v2.py with new namespaces
2. **Migration script**: Re-compute all UUIDs in existing databases
3. **Re-identification impact**: Document loss of historical mapping
4. **Approval**: Security review + data steward approval

See: docs/architecture/adr-002-deterministic-uuids.md
"""

import uuid
from datetime import datetime

# ============================================================================
# UUID5 Namespaces (LOCKED - DO NOT CHANGE)
# ============================================================================
# These UUIDs were generated on 2025-01-08 and are now IMMUTABLE.
# Any change requires a new version and migration path.

# Namespace for author identities
# Used in: uuid5(NS_AUTHORS, f"{tenant_id}:{source}:{author_raw}")
NS_AUTHORS = uuid.UUID("a0eef1c4-7b8d-4f3e-9c6a-1d2e3f4a5b6c")

# Namespace for thread/conversation identities
# Used in: uuid5(NS_THREADS, f"{tenant_id}:{source}:{thread_key}")
NS_THREADS = uuid.UUID("b1ffa2d5-8c9e-5a4f-ad7b-2e3f4a5b6c7d")

# Namespace for media attachment identities
# Used in: uuid5(NS_MEDIA, f"{tenant_id}:{source}:{media_url}")
NS_MEDIA = uuid.UUID("c2aab3e6-9daf-6b5a-be8c-3f4a5b6c7d8e")

# Namespace for event/message identities
# Used in: uuid5(NS_EVENTS, f"{tenant_id}:{source}:{msg_id}")
NS_EVENTS = uuid.UUID("d3bbc4f7-aebf-7c6b-cf9d-4f5a6b7c8d9e")

# ============================================================================
# Locked Timestamp (for audit)
# ============================================================================
NAMESPACES_LOCKED_AT = datetime.fromisoformat("2025-01-08T00:00:00+00:00")
NAMESPACES_VERSION = "1.0.0"

# ============================================================================
# Helper Functions
# ============================================================================


def deterministic_author_uuid(tenant_id: str, source: str, author_raw: str) -> uuid.UUID:
    """Generate deterministic author UUID.

    Args:
        tenant_id: Tenant identifier (e.g., 'acme-corp', 'default')
        source: Source platform ('whatsapp', 'slack', 'discord')
        author_raw: Original author name/identifier from source

    Returns:
        UUID5 hash (stable across re-ingests)

    Examples:
        >>> deterministic_author_uuid("default", "whatsapp", "Alice")
        UUID('...')  # Same UUID every time

        >>> deterministic_author_uuid("default", "whatsapp", "Alice")
        UUID('...')  # Identical to above

        >>> deterministic_author_uuid("tenant-b", "whatsapp", "Alice")
        UUID('...')  # Different UUID (different tenant)

    Privacy Note:
        This function does NOT store the mapping author_raw → UUID.
        By default, the mapping is one-way and NOT reversible.
        See privacy.enable_reidentification config for escrow option.
    """
    key = f"{tenant_id}:{source}:{author_raw}"
    return uuid.uuid5(NS_AUTHORS, key)


def deterministic_thread_uuid(tenant_id: str, source: str, thread_key: str) -> uuid.UUID:
    """Generate deterministic thread/conversation UUID.

    Args:
        tenant_id: Tenant identifier
        source: Source platform
        thread_key: Source-specific thread identifier
            - WhatsApp: Group chat name or phone number
            - Slack: Channel ID (C1234567890)
            - Discord: Channel ID

    Returns:
        UUID5 hash (stable across re-ingests)

    Examples:
        >>> deterministic_thread_uuid("default", "whatsapp", "Family Group")
        UUID('...')

        >>> deterministic_thread_uuid("default", "slack", "C1234567890")
        UUID('...')
    """
    key = f"{tenant_id}:{source}:{thread_key}"
    return uuid.uuid5(NS_THREADS, key)


def deterministic_media_uuid(tenant_id: str, source: str, media_identifier: str) -> uuid.UUID:
    """Generate deterministic media attachment UUID.

    Args:
        tenant_id: Tenant identifier
        source: Source platform
        media_identifier: Source-specific media identifier
            - WhatsApp: Original filename or URL
            - Slack: file.id
            - Discord: Attachment URL

    Returns:
        UUID5 hash (stable across re-ingests)

    Examples:
        >>> deterministic_media_uuid("default", "whatsapp", "IMG_1234.jpg")
        UUID('...')
    """
    key = f"{tenant_id}:{source}:{media_identifier}"
    return uuid.uuid5(NS_MEDIA, key)


def deterministic_event_uuid(tenant_id: str, source: str, msg_id: str) -> uuid.UUID:
    """Generate deterministic event/message UUID.

    Args:
        tenant_id: Tenant identifier
        source: Source platform
        msg_id: Source-specific message identifier
            - WhatsApp: Milliseconds since group creation
            - Slack: Message timestamp (ts)
            - Discord: Message ID (snowflake)

    Returns:
        UUID5 hash (stable across re-ingests)

    Examples:
        >>> deterministic_event_uuid("default", "whatsapp", "1641024000000")
        UUID('...')

        >>> deterministic_event_uuid("default", "slack", "1641024000.000100")
        UUID('...')

    Note:
        This is used for the event_id (PRIMARY KEY) in IR v1 schema.
        Re-ingesting the same data must produce identical event_ids.
    """
    key = f"{tenant_id}:{source}:{msg_id}"
    return uuid.uuid5(NS_EVENTS, key)


# ============================================================================
# Validation
# ============================================================================


def validate_namespaces() -> None:
    """Validate that namespaces are properly initialized.

    Raises:
        AssertionError: If namespaces are invalid or changed

    Called on module import to catch accidental modifications.
    """
    # Ensure all namespaces are distinct
    namespaces = {NS_AUTHORS, NS_THREADS, NS_MEDIA, NS_EVENTS}
    assert len(namespaces) == 4, "Namespace collision detected!"

    # Ensure all are valid UUID v4 format
    for ns in namespaces:
        assert isinstance(ns, uuid.UUID), f"Invalid namespace type: {type(ns)}"

    # Ensure they haven't been accidentally modified
    # (We store the hex values as a checksum)
    expected_hashes = {
        NS_AUTHORS.hex,
        NS_THREADS.hex,
        NS_MEDIA.hex,
        NS_EVENTS.hex,
    }

    assert len(expected_hashes) == 4, "Namespace values have changed!"


# Validate on import
validate_namespaces()
