"""Storage protocols defining contracts for data persistence.

This module defines Protocol interfaces that storage implementations must satisfy.
Protocols enable interface segregation - agents only depend on the storage types
they actually use (e.g., writer agent uses PostStorage + ProfileStorage + JournalStorage).

Key Design Principles:
1. **No Path Leakage** - Return opaque string IDs, not Path objects
2. **Interface Segregation** - Separate protocols for each concern
3. **Implementation Agnostic** - Works with filesystem, database, S3, etc.
4. **Testable** - Easy to create in-memory implementations for testing

Example Usage:
    # MkDocs filesystem implementation
    posts = MkDocsPostStorage(site_root)
    post_id = posts.write("my-post", {"title": "Hello"}, "# Content")
    # post_id = "posts/my-post.md" (relative path string)

    # Database implementation
    posts = DatabasePostStorage(conn)
    post_id = posts.write("my-post", {"title": "Hello"}, "# Content")
    # post_id = "1234" (row ID)

    # S3 implementation
    posts = S3PostStorage(bucket)
    post_id = posts.write("my-post", {"title": "Hello"}, "# Content")
    # post_id = "s3://bucket/posts/my-post.md" (S3 key)
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class PostStorage(Protocol):
    """Storage interface for blog posts.

    Implementations hide storage details (filesystem, database, S3).
    Return values are opaque identifiers (not Path objects).

    Contract:
        - write() must be idempotent (same slug overwrites existing post)
        - read() returns None if post doesn't exist (not an exception)
        - exists() is a cheap operation (no full content read)
    """

    def write(self, slug: str, metadata: dict, content: str) -> str:
        """Write a post. Returns post identifier (opaque).

        Args:
            slug: URL-friendly slug (lowercase, hyphenated)
            metadata: Post frontmatter (title, date, tags, authors, etc.)
            content: Markdown post content (body only, no frontmatter)

        Returns:
            Opaque identifier. Examples:
                - Filesystem: "posts/my-post.md" (relative path)
                - Database: "1234" (row ID)
                - S3: "s3://bucket/posts/my-post.md" (full key)

        """
        ...

    def read(self, slug: str) -> tuple[dict, str] | None:
        """Read a post. Returns (metadata, content) or None if not found.

        Args:
            slug: URL-friendly slug (same as used in write())

        Returns:
            (metadata dict, content string) if post exists, None otherwise

        """
        ...

    def exists(self, slug: str) -> bool:
        """Check if post exists.

        Args:
            slug: URL-friendly slug

        Returns:
            True if post exists, False otherwise

        """
        ...


@runtime_checkable
class ProfileStorage(Protocol):
    """Storage interface for author profiles.

    Profiles are markdown documents associated with anonymized author UUIDs.

    Contract:
        - write() must be idempotent (same UUID overwrites existing profile)
        - read() returns None if profile doesn't exist
        - UUIDs are deterministic (same author always gets same UUID)
    """

    def write(self, author_uuid: str, content: str) -> str:
        """Write profile. Returns profile identifier.

        Args:
            author_uuid: Anonymized author UUID (deterministic)
            content: Markdown profile content

        Returns:
            Opaque identifier (e.g., "profiles/abc-123.md")

        """
        ...

    def read(self, author_uuid: str) -> str | None:
        """Read profile content by UUID.

        Args:
            author_uuid: Anonymized author UUID

        Returns:
            Markdown content if profile exists, None otherwise

        """
        ...

    def exists(self, author_uuid: str) -> bool:
        """Check if profile exists.

        Args:
            author_uuid: Anonymized author UUID

        Returns:
            True if profile exists, False otherwise

        """
        ...


@runtime_checkable
class JournalStorage(Protocol):
    """Storage interface for agent journals (execution logs).

    Journals are markdown documents capturing the agent's internal reasoning,
    freeform reflections, and tool usage during window processing.

    Contract:
        - write() is called once per window after agent execution
        - window_label is human-readable (e.g., "2025-01-10 10:00 to 12:00")
        - Implementation converts labels to safe filenames/identifiers
    """

    def write(self, window_label: str, content: str) -> str:
        """Write journal entry. Returns journal identifier.

        Args:
            window_label: Human-readable window label
                         (e.g., "2025-01-10 10:00 to 12:00")
            content: Markdown journal content
                     (thinking + freeform + tool calls)

        Returns:
            Opaque identifier (e.g., "posts/journal/journal_2025-01-10_10-00_to_12-00.md")

        """
        ...


@runtime_checkable
class EnrichmentStorage(Protocol):
    """Storage for URL and media enrichments.

    Enrichments are LLM-generated descriptions of URLs and media files
    referenced in conversations. They're stored as markdown files and
    linked from posts/profiles.

    Contract:
        - write_url_enrichment() uses deterministic UUID based on URL
        - write_media_enrichment() stores description next to media file
        - Both operations are idempotent
    """

    def write_url_enrichment(self, url: str, content: str) -> str:
        """Write URL enrichment. Returns enrichment identifier.

        Args:
            url: Full URL that was enriched
            content: Markdown enrichment content (LLM-generated description)

        Returns:
            Opaque identifier (e.g., "media/urls/{uuid}.md")

        Note:
            Implementation should generate deterministic ID from URL
            (e.g., uuid.uuid5(NAMESPACE_URL, url))

        """
        ...

    def write_media_enrichment(self, filename: str, content: str) -> str:
        """Write media enrichment. Returns enrichment identifier.

        Args:
            filename: Original media filename (from WhatsApp export)
            content: Markdown enrichment content (LLM-generated description)

        Returns:
            Opaque identifier (e.g., "docs/media/{filename}.md")

        Note:
            For filesystem implementations, this typically goes next to
            the media file with .md extension added.

        """
        ...


__all__ = [
    "EnrichmentStorage",
    "JournalStorage",
    "PostStorage",
    "ProfileStorage",
]
