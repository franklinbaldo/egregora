"""In-memory storage implementations for testing.

This module provides lightweight in-memory storage implementations that
satisfy the storage protocols without any filesystem operations. These are
ideal for unit tests where you want to verify agent behavior without I/O.

All implementations store data in simple dictionaries and return
identifiers with `memory://` prefix to make testing assertions clear.

Example Usage:
    def test_writer_agent():
        posts = InMemoryPostStorage()
        profiles = InMemoryProfileStorage()

        # Run agent...
        agent.write_post(...)

        # Verify without filesystem
        assert posts.exists("my-post")
        metadata, content = posts.read("my-post")
        assert metadata["title"] == "Expected Title"
"""

import uuid as uuid_lib

from egregora.utils.paths import slugify


class InMemoryPostStorage:
    """In-memory post storage for testing (no filesystem).

    Data is stored in a simple dictionary mapping slugs to (metadata, content) tuples.
    All state is lost when the object is garbage collected.
    """

    def __init__(self):
        """Initialize empty in-memory post storage."""
        self._posts: dict[str, tuple[dict, str]] = {}

    def write(self, slug: str, metadata: dict, content: str) -> str:
        """Store post in memory.

        Args:
            slug: URL-friendly slug
            metadata: Post frontmatter
            content: Markdown content

        Returns:
            Identifier with memory:// prefix (e.g., "memory://posts/my-post")

        """
        self._posts[slug] = (metadata.copy(), content)
        return f"memory://posts/{slug}"

    def read(self, slug: str) -> tuple[dict, str] | None:
        """Retrieve post from memory.

        Args:
            slug: URL-friendly slug

        Returns:
            (metadata dict, content string) if post exists, None otherwise

        """
        result = self._posts.get(slug)
        if result is None:
            return None

        # Return copies to prevent test mutations
        metadata, content = result
        return metadata.copy(), content

    def exists(self, slug: str) -> bool:
        """Check if post exists in memory.

        Args:
            slug: URL-friendly slug

        Returns:
            True if slug is in internal dictionary

        """
        return slug in self._posts

    def clear(self):
        """Clear all stored posts (useful for test cleanup)."""
        self._posts.clear()

    def __len__(self) -> int:
        """Return number of stored posts."""
        return len(self._posts)


class InMemoryProfileStorage:
    """In-memory profile storage for testing.

    Data is stored in a simple dictionary mapping UUIDs to content strings.
    """

    def __init__(self):
        """Initialize empty in-memory profile storage."""
        self._profiles: dict[str, str] = {}

    def write(self, author_uuid: str, content: str) -> str:
        """Store profile in memory.

        Args:
            author_uuid: Anonymized author UUID
            content: Markdown profile content

        Returns:
            Identifier with memory:// prefix (e.g., "memory://profiles/abc-123")

        """
        self._profiles[author_uuid] = content
        return f"memory://profiles/{author_uuid}"

    def read(self, author_uuid: str) -> str | None:
        """Retrieve profile from memory.

        Args:
            author_uuid: Anonymized author UUID

        Returns:
            Markdown content if profile exists, None otherwise

        """
        return self._profiles.get(author_uuid)

    def exists(self, author_uuid: str) -> bool:
        """Check if profile exists in memory.

        Args:
            author_uuid: Anonymized author UUID

        Returns:
            True if UUID is in internal dictionary

        """
        return author_uuid in self._profiles

    def clear(self):
        """Clear all stored profiles (useful for test cleanup)."""
        self._profiles.clear()

    def __len__(self) -> int:
        """Return number of stored profiles."""
        return len(self._profiles)


class InMemoryJournalStorage:
    """In-memory journal storage for testing.

    Data is stored in a dictionary mapping safe labels to content strings.
    Implements OutputAdapter protocol's serve() method for compatibility with new agent code.
    """

    def __init__(self):
        """Initialize empty in-memory journal storage."""
        self._journals: dict[str, str] = {}

    def serve(self, document) -> None:
        """Store document (OutputAdapter protocol).

        Args:
            document: Document object with content and metadata

        """
        # Extract window_label from metadata, fallback to source_window
        window_label = document.metadata.get("window_label")
        if window_label is None and hasattr(document, "source_window"):
            window_label = document.source_window
        if window_label is None:
            window_label = "unknown"

        safe_label = self._sanitize_label(window_label)
        self._journals[safe_label] = document.content

    def write(self, window_label: str, content: str) -> str:
        """Store journal entry in memory (legacy method).

        Args:
            window_label: Human-readable window label
            content: Markdown journal content

        Returns:
            Identifier with memory:// prefix (e.g., "memory://journal/2025-01-10_10-00...")

        """
        safe_label = self._sanitize_label(window_label)
        self._journals[safe_label] = content
        return f"memory://journal/{safe_label}"

    @staticmethod
    def _sanitize_label(label: str) -> str:
        """Convert window label to safe identifier.

        Args:
            label: Human-readable label

        Returns:
            Safe identifier (spaces→underscores, colons→hyphens)

        """
        return label.replace(" ", "_").replace(":", "-")

    def get_by_label(self, window_label: str) -> str | None:
        """Retrieve journal by original label (convenience for testing).

        Args:
            window_label: Original window label (will be sanitized)

        Returns:
            Journal content if exists, None otherwise

        """
        safe_label = self._sanitize_label(window_label)
        return self._journals.get(safe_label)

    def clear(self):
        """Clear all stored journals (useful for test cleanup)."""
        self._journals.clear()

    def __len__(self) -> int:
        """Return number of stored journals."""
        return len(self._journals)


class InMemoryEnrichmentStorage:
    """In-memory enrichment storage for testing.

    Implements OutputAdapter protocol with serve() method.
    URL enrichments are stored with slugified URLs (like filesystem version).
    Media enrichments are stored by filename.
    """

    def __init__(self):
        """Initialize empty in-memory enrichment storage."""
        self._url_enrichments: dict[str, str] = {}
        self._media_enrichments: dict[str, str] = {}

    def serve(self, document) -> None:
        """Store document (OutputAdapter protocol).

        Args:
            document: Document object with content, type, and metadata

        """
        from egregora.core.document import DocumentType

        if document.type == DocumentType.ENRICHMENT_URL:
            url = document.metadata.get("url", "")
            url_prefix = slugify(url, max_len=40)
            url_uuid = str(uuid_lib.uuid5(uuid_lib.NAMESPACE_URL, url))
            url_hash = url_uuid.replace("-", "")[:8]
            filename = f"{url_prefix}-{url_hash}"
            self._url_enrichments[filename] = document.content
        elif document.type == DocumentType.ENRICHMENT_MEDIA:
            filename = document.metadata.get("filename", "unknown")
            self._media_enrichments[filename] = document.content

    def write_url_enrichment(self, url: str, content: str) -> str:
        """Store URL enrichment in memory (legacy method).

        Args:
            url: Full URL that was enriched
            content: Markdown enrichment content

        Returns:
            Identifier with memory:// prefix (e.g., "memory://enrichments/urls/example-com-article-a1b2c3d4")

        Note:
            Uses readable prefix + UUID5 hash suffix (same as MkDocs implementation)

        """
        url_prefix = slugify(url, max_len=40)
        url_uuid = str(uuid_lib.uuid5(uuid_lib.NAMESPACE_URL, url))
        url_hash = url_uuid.replace("-", "")[:8]
        filename = f"{url_prefix}-{url_hash}"
        self._url_enrichments[filename] = content
        return f"memory://enrichments/urls/{filename}"

    def write_media_enrichment(self, filename: str, content: str) -> str:
        """Store media enrichment in memory (legacy method).

        Args:
            filename: Original media filename
            content: Markdown enrichment content

        Returns:
            Identifier with memory:// prefix (e.g., "memory://enrichments/media/{filename}")

        """
        self._media_enrichments[filename] = content
        return f"memory://enrichments/media/{filename}"

    def get_url_enrichment_by_url(self, url: str) -> str | None:
        """Retrieve URL enrichment by original URL (convenience for testing).

        Args:
            url: Original URL

        Returns:
            Enrichment content if exists, None otherwise

        """
        url_prefix = slugify(url, max_len=40)
        url_uuid = str(uuid_lib.uuid5(uuid_lib.NAMESPACE_URL, url))
        url_hash = url_uuid.replace("-", "")[:8]
        filename = f"{url_prefix}-{url_hash}"
        return self._url_enrichments.get(filename)

    def get_media_enrichment(self, filename: str) -> str | None:
        """Retrieve media enrichment by filename.

        Args:
            filename: Original media filename

        Returns:
            Enrichment content if exists, None otherwise

        """
        return self._media_enrichments.get(filename)

    def clear(self):
        """Clear all stored enrichments (useful for test cleanup)."""
        self._url_enrichments.clear()
        self._media_enrichments.clear()

    def __len__(self) -> int:
        """Return total number of stored enrichments (URL + media)."""
        return len(self._url_enrichments) + len(self._media_enrichments)


__all__ = [
    "InMemoryEnrichmentStorage",
    "InMemoryJournalStorage",
    "InMemoryPostStorage",
    "InMemoryProfileStorage",
]
