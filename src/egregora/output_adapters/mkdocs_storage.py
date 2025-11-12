"""MkDocs filesystem storage implementations.

This module contains filesystem-based storage implementations for MkDocs:
- MkDocsPostStorage: Blog posts with YAML frontmatter
- MkDocsProfileStorage: Author profiles with .authors.yml integration
- MkDocsJournalStorage: Agent journal entries
- MkDocsEnrichmentStorage: URL and media enrichments

These storage classes are used by both MkDocsOutputAdapter and HugoOutputAdapter.
"""

from __future__ import annotations

import logging
import uuid as uuid_lib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from egregora.agents.shared.author_profiles import write_profile as write_profile_content
from egregora.utils.paths import safe_path_join, slugify

if TYPE_CHECKING:
    from egregora.output_adapters.base import OutputAdapter

logger = logging.getLogger(__name__)

# Constants
ISO_DATE_LENGTH = 10  # Length of ISO date format (YYYY-MM-DD)


def _extract_clean_date(date_str: str) -> str:
    """Extract clean YYYY-MM-DD date from various formats.

    Handles:
    - Clean dates: "2025-03-02"
    - ISO timestamps: "2025-03-02T10:30:00"
    - Window labels: "2025-03-02 08:01 to 12:49"
    - Datetimes: "2025-03-02 10:30:45"

    Args:
        date_str: Date string in various formats

    Returns:
        Clean date in YYYY-MM-DD format

    """
    import datetime
    import re

    # Remove leading/trailing whitespace
    date_str = date_str.strip()

    # Try to parse as ISO date first (most common)
    try:
        # Handle ISO format (YYYY-MM-DD)
        if len(date_str) == ISO_DATE_LENGTH and date_str[4] == "-" and date_str[7] == "-":
            datetime.date.fromisoformat(date_str)  # Validate
            return date_str
    except (ValueError, AttributeError):
        pass

    # Extract YYYY-MM-DD from longer strings (window labels, timestamps)
    match = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
    if match:
        clean_date = match.group(1)
        try:
            datetime.date.fromisoformat(clean_date)  # Validate
        except (ValueError, AttributeError):
            pass
        else:
            return clean_date

    # Fallback: return original if we can't parse it
    return date_str


def _write_mkdocs_post(content: str, metadata: dict[str, Any], output_dir: Path) -> str:
    """Save a blog post with YAML front matter (MkDocs format).

    Args:
        content: Markdown post content
        metadata: Post metadata (title, slug, date, tags, summary, authors, category)

    Returns:
        Path where post was saved

    Raises:
        ValueError: If required metadata is missing

    """
    import datetime

    required = ["title", "slug", "date"]
    for key in required:
        if key not in metadata:
            msg = f"Missing required metadata: {key}"
            raise ValueError(msg)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse and clean date
    raw_date = metadata["date"]
    date_prefix = _extract_clean_date(raw_date)

    # Slugify and handle duplicates
    base_slug = slugify(metadata["slug"])
    slug_candidate = base_slug
    filename = f"{date_prefix}-{slug_candidate}.md"
    filepath = safe_path_join(output_dir, filename)
    suffix = 2
    while filepath.exists():
        slug_candidate = f"{base_slug}-{suffix}"
        filename = f"{date_prefix}-{slug_candidate}.md"
        filepath = safe_path_join(output_dir, filename)
        suffix += 1

    # Build front matter
    front_matter = {
        "title": metadata["title"],
        "slug": slug_candidate,
    }

    # Use cleaned date for front matter
    try:
        front_matter["date"] = datetime.date.fromisoformat(date_prefix)
    except (ValueError, AttributeError):
        front_matter["date"] = date_prefix

    if "tags" in metadata:
        front_matter["tags"] = metadata["tags"]
    if "summary" in metadata:
        front_matter["summary"] = metadata["summary"]
    if "authors" in metadata:
        front_matter["authors"] = metadata["authors"]
    if "category" in metadata:
        front_matter["category"] = metadata["category"]

    yaml_front = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True)
    full_post = f"---\n{yaml_front}---\n\n{content}"
    filepath.write_text(full_post, encoding="utf-8")
    return str(filepath)


def secure_path_join(base_dir: Path, user_path: str) -> Path:
    """Safely join a user-provided path to a base directory, preventing path traversal.

    Args:
        base_dir: Base directory that result must stay within
        user_path: User-provided path (potentially malicious)

    Returns:
        Resolved path within base_dir

    Raises:
        ValueError: If user_path attempts to escape base_dir

    Examples:
        >>> secure_path_join(Path("/var/www"), "posts/my-post.md")
        Path("/var/www/posts/my-post.md")
        >>> secure_path_join(Path("/var/www"), "../etc/passwd")
        ValueError: Path traversal detected

    """
    # Join paths and resolve to absolute path
    full_path = (base_dir / user_path).resolve()

    # Verify the resolved path is still within base_dir
    try:
        full_path.relative_to(base_dir.resolve())
    except ValueError as e:
        msg = f"Path traversal detected: {user_path!r} escapes base directory {base_dir}"
        raise ValueError(msg) from e

    return full_path


# ============================================================================
# MkDocs Storage Implementations
# ============================================================================
# These classes implement the storage protocols for MkDocs filesystem structure.
# They are used internally by MkDocsOutputAdapter and should not be imported directly.


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

    def __init__(self, site_root: Path, output_format: OutputAdapter | None = None) -> None:
        """Initialize MkDocs post storage.

        Args:
            site_root: Root directory for MkDocs site
            output_format: OutputAdapter instance for utilities (normalize_slug, etc.)
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
            Uses OutputAdapter utilities for:
            - Slug normalization (URL-safe, lowercase, hyphens)
            - Date extraction (handles window labels, ISO timestamps, defaults to today)
            - Unique filename generation (prevents silent overwrites)
            - Frontmatter slug sync (updates metadata to match normalized filename)

        Important:
            The metadata dict is MUTATED to keep frontmatter slug in sync with filename.
            If filename is "2025-01-10-my-post-2.md" (collision suffix added),
            metadata["slug"] will be updated to "my-post-2" to match.

        """
        # Extract date from metadata (optional, defaults to today via extract_date_prefix)
        date_str = metadata.get("date", "")

        # Apply data integrity validations if OutputAdapter is available
        if self.output_format:
            # Normalize slug to URL-safe format
            normalized_slug = self.output_format.normalize_slug(slug)

            # Extract clean YYYY-MM-DD date prefix (handles empty string → today's date)
            date_prefix = self.output_format.extract_date_prefix(str(date_str))

            # Generate unique filename with date prefix
            filename_pattern = f"{date_prefix}-{normalized_slug}.md"
            path = self.output_format.generate_unique_filename(self.posts_dir, filename_pattern)

            # Extract final slug from path (may have collision suffix)
            # Example: "2025-01-10-my-post-2.md" → "my-post-2"
            final_filename = path.stem  # Remove .md extension
            # Remove date prefix: "2025-01-10-my-post-2" → "my-post-2"
            if final_filename.startswith(date_prefix):
                final_slug = final_filename[len(date_prefix) + 1 :]  # +1 for the hyphen
            else:
                final_slug = final_filename

            # CRITICAL: Update metadata slug to match final filename
            # This ensures frontmatter stays in sync with filename
            # URLs, RAG chunk IDs, and all downstream tools depend on this
            metadata = metadata.copy()  # Don't mutate caller's dict
            metadata["slug"] = final_slug
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
            msg = f"Invalid YAML frontmatter: {e}"
            raise ValueError(msg) from e

        return metadata, body


class MkDocsProfileStorage:
    """Filesystem-based profile storage with YAML frontmatter and .authors.yml support.

    Structure:
        site_root/profiles/{uuid}.md
        site_root/.authors.yml

    Profiles are stored with YAML frontmatter containing metadata (name, alias, avatar, bio, social).
    The .authors.yml file is automatically updated for MkDocs blog plugin compatibility.
    """

    def __init__(self, site_root: Path) -> None:
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
        """Write profile to filesystem with YAML frontmatter and .authors.yml update.

        Preserves existing profile metadata (alias, avatar, bio, social) by extracting
        it from the existing profile file before writing the new content. Updates
        .authors.yml for MkDocs blog plugin compatibility.

        Args:
            author_uuid: Anonymized author UUID
            content: Markdown profile content (without frontmatter)

        Returns:
            Relative path string (e.g., "profiles/abc-123.md")

        Side Effects:
            - Writes profile with YAML frontmatter
            - Updates .authors.yml in site root

        """
        # Use write_profile_content to ensure proper YAML frontmatter and .authors.yml update
        absolute_path = write_profile_content(author_uuid, content, self.profiles_dir)
        return str(Path(absolute_path).relative_to(self.site_root))

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

    def __init__(self, site_root: Path) -> None:
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
        site_root/docs/media/{filename}.md         # Media enrichments

    URL enrichments are stored in media/urls/ and published via mkdocs.yml configuration.
    Media enrichments are stored inside docs/media/ for automatic publication.

    To publish URL enrichments, configure mkdocs.yml with:
        docs_dir: '.'  # Publish from site root

    Or add media/ to your navigation structure.

    URL enrichments use deterministic UUIDs based on the URL.
    Media enrichments are stored next to the media file with .md extension.
    """

    def __init__(self, site_root: Path) -> None:
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
            Relative path string (e.g., "media/urls/example-com-article-a1b2c3d4.md")

        Note:
            Uses readable prefix (40 chars) + hash suffix (16 chars) for collision-free,
            partially human-readable filenames. The hash ensures uniqueness even when
            URLs share the same prefix (e.g., long query strings, different fragments).

        Examples:
            - https://example.com/article
              → media/urls/https-example-com-article-a1b2c3d4e5f6g7h8.md
            - https://docs.python.org/3/library/pathlib.html
              → media/urls/https-docs-python-org-3-library-pathl-b2c3d4e5f6g7h8i9.md
            - https://example.com/article?id=12345678901234567890  (collision-prone with slug-only)
              → media/urls/https-example-com-article-id-123456-c3d4e5f6g7h8i9j0.md

        """
        # Create human-readable prefix (40 chars) + collision-proof hash suffix (8 chars)
        # Uses UUID5 for deterministic, discoverable hash (same as document_id)
        url_prefix = slugify(url, max_len=40)
        url_uuid = str(uuid_lib.uuid5(uuid_lib.NAMESPACE_URL, url))
        url_hash = url_uuid.replace("-", "")[:8]  # Take first 8 hex chars (32 bits)
        filename = f"{url_prefix}-{url_hash}.md"

        path = self.urls_dir / filename
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(self.site_root))

    def write_media_enrichment(self, filename: str, content: str) -> str:
        """Write media enrichment to filesystem.

        Args:
            filename: Path to media file relative to site_root (e.g., "media/images/abc.jpg")
            content: Markdown enrichment content

        Returns:
            Relative path string (e.g., "media/images/abc.jpg.md")

        Note:
            Enrichment is stored next to the media file with .md extension.
            Parent directories are created if needed.

            Modern MkDocs layout uses `docs_dir: '.'` so media files are at
            site_root/media/... and enrichments go to site_root/media/.../file.md

        """
        # Media enrichment goes next to the media file
        # Use secure_path_join to prevent path traversal attacks
        media_path = secure_path_join(self.site_root, filename)
        enrichment_path = media_path.with_suffix(media_path.suffix + ".md")

        # Ensure parent directory exists
        enrichment_path.parent.mkdir(parents=True, exist_ok=True)

        enrichment_path.write_text(content, encoding="utf-8")
        return str(enrichment_path.relative_to(self.site_root))


__all__ = [
    # Storage implementations
    "MkDocsPostStorage",
    "MkDocsProfileStorage",
    "MkDocsJournalStorage",
    "MkDocsEnrichmentStorage",
    # Helper functions
    "secure_path_join",
    "_extract_clean_date",
    "_write_mkdocs_post",
]
