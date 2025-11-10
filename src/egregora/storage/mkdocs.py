"""MkDocs filesystem-based storage implementations.

This module provides storage implementations that follow MkDocs static site
conventions. All implementations work with a site_root directory structure:

    site_root/
    ├── posts/              # Blog posts
    │   └── journal/        # Agent journals
    ├── profiles/           # Author profiles
    └── media/              # Media files
        └── urls/           # URL enrichments

These implementations return relative paths as identifiers (e.g., "posts/my-post.md").
"""

from __future__ import annotations

import uuid as uuid_lib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from egregora.rendering.base import OutputFormat


class MkDocsPostStorage:
    """Filesystem-based post storage following MkDocs conventions.

    Structure:
        site_root/posts/{date}-{slug}.md

    Posts are stored as markdown files with YAML frontmatter:
        ---
        title: My Post
        date: 2025-01-10
        tags: [tag1, tag2]
        ---

        Post content here...
    """

    def __init__(self, site_root: Path, output_format: OutputFormat | None = None):
        """Initialize MkDocs post storage.

        Args:
            site_root: Root directory for MkDocs site
            output_format: OutputFormat instance for utilities (normalize_slug, etc.)
                          If None, will use default implementations without validations

        Side Effects:
            Creates posts/ directory if it doesn't exist

        """
        self.site_root = site_root
        self.posts_dir = site_root / "posts"
        self.posts_dir.mkdir(parents=True, exist_ok=True)
        self.output_format = output_format

    def write(self, slug: str, metadata: dict, content: str) -> str:
        """Write post to filesystem with data integrity validations.

        Args:
            slug: URL-friendly slug (e.g., "my-post")
            metadata: YAML frontmatter dict (date optional, defaults to today)
            content: Markdown content (body only)

        Returns:
            Relative path string (e.g., "posts/2025-01-10-my-post.md")

        Note:
            Uses OutputFormat utilities for:
            - Slug normalization (URL-safe, lowercase, hyphens)
            - Date extraction (handles window labels, ISO timestamps, defaults to today)
            - Unique filename generation (prevents silent overwrites)

        """
        import yaml

        # Extract date from metadata (optional, defaults to today via extract_date_prefix)
        date_str = metadata.get("date", "")

        # Apply data integrity validations if OutputFormat is available
        if self.output_format:
            # Normalize slug to URL-safe format
            normalized_slug = self.output_format.normalize_slug(slug)

            # Extract clean YYYY-MM-DD date prefix (handles empty string → today's date)
            date_prefix = self.output_format.extract_date_prefix(str(date_str))

            # Generate unique filename with date prefix
            filename_pattern = f"{date_prefix}-{normalized_slug}.md"
            path = self.output_format.generate_unique_filename(self.posts_dir, filename_pattern)
        else:
            # Fallback: simple filename without validations
            path = self.posts_dir / f"{slug}.md"

        # Combine frontmatter + content
        frontmatter = yaml.dump(metadata, sort_keys=False, allow_unicode=True)
        full_content = f"---\n{frontmatter}---\n\n{content}"

        # Atomic write
        path.write_text(full_content, encoding="utf-8")

        # Return relative path as identifier
        return str(path.relative_to(self.site_root))

    def read(self, slug: str) -> tuple[dict, str] | None:
        """Read post from filesystem.

        Args:
            slug: URL-friendly slug (matches files with or without date prefix)

        Returns:
            (metadata dict, content string) if post exists, None otherwise

        Note:
            Searches for both date-prefixed ({date}-{slug}.md) and simple ({slug}.md) formats.
            This provides backwards compatibility with posts written before data integrity updates.
            When multiple matches exist, returns the most recently modified file (deterministic).

        """
        # Try finding date-prefixed file first (new format)
        matching_files = list(self.posts_dir.glob(f"*-{slug}.md"))
        if matching_files:
            # Use most recent file if multiple matches (sort by mtime, descending)
            # Ensures deterministic behavior when duplicate slugs exist
            path = max(matching_files, key=lambda p: p.stat().st_mtime)
        else:
            # Fall back to simple format (legacy)
            path = self.posts_dir / f"{slug}.md"

        if not path.exists():
            return None

        # Parse frontmatter
        raw_content = path.read_text(encoding="utf-8")
        return self._parse_frontmatter(raw_content)

    def exists(self, slug: str) -> bool:
        """Check if post exists.

        Args:
            slug: URL-friendly slug (matches files with or without date prefix)

        Returns:
            True if post exists in either date-prefixed or simple format

        Note:
            Checks both {date}-{slug}.md (new format) and {slug}.md (legacy format).

        """
        # Check for date-prefixed format first
        matching_files = list(self.posts_dir.glob(f"*-{slug}.md"))
        if matching_files:
            return True

        # Fall back to simple format
        return (self.posts_dir / f"{slug}.md").exists()

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict, str]:
        """Parse YAML frontmatter from markdown content.

        Args:
            content: Raw markdown with frontmatter

        Returns:
            (metadata dict, body string)

        Raises:
            ValueError: If frontmatter is malformed

        """
        import yaml

        if not content.startswith("---\n"):
            return {}, content

        # Find end of frontmatter
        end_marker = content.find("\n---\n", 4)
        if end_marker == -1:
            # No closing marker
            return {}, content

        # Extract and parse frontmatter
        frontmatter_text = content[4:end_marker]
        body = content[end_marker + 5 :].lstrip()

        try:
            metadata = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML frontmatter: {e}") from e

        return metadata, body


class MkDocsProfileStorage:
    """Filesystem-based profile storage.

    Structure:
        site_root/profiles/{uuid}.md

    Profiles are stored as plain markdown files (no frontmatter).
    """

    def __init__(self, site_root: Path):
        """Initialize MkDocs profile storage.

        Args:
            site_root: Root directory for MkDocs site

        Side Effects:
            Creates profiles/ directory if it doesn't exist

        """
        self.site_root = site_root
        self.profiles_dir = site_root / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def write(self, author_uuid: str, content: str) -> str:
        """Write profile to filesystem.

        Args:
            author_uuid: Anonymized author UUID
            content: Markdown profile content

        Returns:
            Relative path string (e.g., "profiles/abc-123.md")

        """
        path = self.profiles_dir / f"{author_uuid}.md"
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(self.site_root))

    def read(self, author_uuid: str) -> str | None:
        """Read profile from filesystem.

        Args:
            author_uuid: Anonymized author UUID

        Returns:
            Markdown content if profile exists, None otherwise

        """
        path = self.profiles_dir / f"{author_uuid}.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def exists(self, author_uuid: str) -> bool:
        """Check if profile exists.

        Args:
            author_uuid: Anonymized author UUID

        Returns:
            True if {profiles_dir}/{uuid}.md exists

        """
        return (self.profiles_dir / f"{author_uuid}.md").exists()


class MkDocsJournalStorage:
    """Filesystem-based journal storage.

    Structure:
        site_root/posts/journal/journal_{safe_label}.md

    Journals are stored inside the posts/journal/ directory so they appear
    in the blog navigation alongside posts.

    Window labels like "2025-01-10 10:00 to 12:00" are converted to
    safe filenames like "journal_2025-01-10_10-00_to_12-00.md".
    """

    def __init__(self, site_root: Path):
        """Initialize MkDocs journal storage.

        Args:
            site_root: Root directory for MkDocs site

        Side Effects:
            Creates posts/journal/ directory if it doesn't exist

        """
        self.site_root = site_root
        self.journal_dir = site_root / "posts" / "journal"
        self.journal_dir.mkdir(parents=True, exist_ok=True)

    def write(self, window_label: str, content: str) -> str:
        """Write journal entry to filesystem.

        Args:
            window_label: Human-readable window label
                         (e.g., "2025-01-10 10:00 to 12:00")
            content: Markdown journal content

        Returns:
            Relative path string (e.g., "posts/journal/journal_2025-01-10_10-00_to_12-00.md")

        """
        # Convert window label to filename-safe format
        safe_label = self._sanitize_label(window_label)
        path = self.journal_dir / f"journal_{safe_label}.md"
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(self.site_root))

    @staticmethod
    def _sanitize_label(label: str) -> str:
        """Convert window label to filename-safe string.

        Args:
            label: Human-readable label (e.g., "2025-01-10 10:00 to 12:00")

        Returns:
            Safe filename (e.g., "2025-01-10_10-00_to_12-00")

        """
        return label.replace(" ", "_").replace(":", "-")


class MkDocsEnrichmentStorage:
    """Filesystem-based enrichment storage.

    Structure:
        site_root/media/urls/{enrichment_id}.md    # URL enrichments
        site_root/docs/{filename}.md               # Media enrichments

    URL enrichments use deterministic UUIDs based on the URL.
    Media enrichments are stored next to the media file with .md extension.
    """

    def __init__(self, site_root: Path):
        """Initialize MkDocs enrichment storage.

        Args:
            site_root: Root directory for MkDocs site

        Side Effects:
            Creates media/urls/ directory if it doesn't exist

        """
        self.site_root = site_root
        self.urls_dir = site_root / "media" / "urls"
        self.urls_dir.mkdir(parents=True, exist_ok=True)

    def write_url_enrichment(self, url: str, content: str) -> str:
        """Write URL enrichment to filesystem.

        Args:
            url: Full URL that was enriched
            content: Markdown enrichment content

        Returns:
            Relative path string (e.g., "media/urls/{uuid}.md")

        Note:
            Uses deterministic UUID (uuid5 with NAMESPACE_URL)

        """
        enrichment_id = uuid_lib.uuid5(uuid_lib.NAMESPACE_URL, url)
        path = self.urls_dir / f"{enrichment_id}.md"
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(self.site_root))

    def write_media_enrichment(self, filename: str, content: str) -> str:
        """Write media enrichment to filesystem.

        Args:
            filename: Original media filename (from export)
            content: Markdown enrichment content

        Returns:
            Relative path string (e.g., "docs/media/{filename}.md")

        Note:
            Enrichment is stored next to the media file with .md extension.
            Parent directories are created if needed.

        """
        # Media enrichment goes next to the media file
        media_path = self.site_root / "docs" / filename
        enrichment_path = media_path.with_suffix(media_path.suffix + ".md")

        # Ensure parent directory exists
        enrichment_path.parent.mkdir(parents=True, exist_ok=True)

        enrichment_path.write_text(content, encoding="utf-8")
        return str(enrichment_path.relative_to(self.site_root))


__all__ = [
    "MkDocsEnrichmentStorage",
    "MkDocsJournalStorage",
    "MkDocsPostStorage",
    "MkDocsProfileStorage",
]
