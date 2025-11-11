"""Abstract base class for output formats (MkDocs, Hugo, Jekyll, etc.)."""

import datetime
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from egregora.storage import EnrichmentStorage, JournalStorage, PostStorage, ProfileStorage


@dataclass
class SiteConfiguration:
    """Configuration for a documentation/blog site."""

    site_root: Path
    site_name: str
    docs_dir: Path
    posts_dir: Path
    profiles_dir: Path
    media_dir: Path
    config_file: Path | None
    additional_paths: dict[str, Path] | None = None


class OutputFormat(ABC):
    """Abstract base class for output formats.

    Output formats are responsible for:
    1. Scaffolding new sites with proper directory structure
    2. Writing blog posts in the appropriate format
    3. Managing author profiles
    4. Resolving site paths and configuration
    5. Generating any format-specific files (config, templates, etc.)

    Directory Structure Properties:
        These properties define the conventional directory names for this format.
        Subclasses should override these to match their format's conventions.
        For example, Hugo might use "static" instead of "media", "authors" instead of "profiles".
    """

    @property
    def docs_dir_name(self) -> str:
        """Default name for the documentation directory."""
        return "docs"

    @property
    def blog_dir_name(self) -> str:
        """Default name for the blog directory (relative to docs_dir)."""
        return "."

    @property
    def profiles_dir_name(self) -> str:
        """Name for the author profiles directory."""
        return "profiles"

    @property
    def media_dir_name(self) -> str:
        """Name for the media/assets directory."""
        return "media"

    def get_media_dir(self, site_root: Path) -> Path:
        """Get the media directory for this site.

        Args:
            site_root: Root directory of the site

        Returns:
            Path to media directory

        """
        site_config = self.resolve_paths(site_root)
        return site_config.media_dir

    def get_profiles_dir(self, site_root: Path) -> Path:
        """Get the profiles directory for this site.

        Args:
            site_root: Root directory of the site

        Returns:
            Path to profiles directory

        """
        site_config = self.resolve_paths(site_root)
        return site_config.profiles_dir

    def get_posts_dir(self, site_root: Path) -> Path:
        """Get the posts directory for this site.

        Args:
            site_root: Root directory of the site

        Returns:
            Path to posts directory

        """
        site_config = self.resolve_paths(site_root)
        return site_config.posts_dir

    def get_docs_dir(self, site_root: Path) -> Path:
        """Get the docs directory for this site.

        Args:
            site_root: Root directory of the site

        Returns:
            Path to docs directory

        """
        site_config = self.resolve_paths(site_root)
        return site_config.docs_dir

    @abstractmethod
    def scaffold_site(self, site_root: Path, site_name: str, **kwargs: object) -> tuple[Path, bool]:
        """Create the initial site structure.

        Args:
            site_root: Root directory for the site
            site_name: Display name for the site
            **kwargs: Format-specific options

        Returns:
            tuple of (config_file_path, was_created)
            - config_file_path: Path to the main config file
            - was_created: True if new site was created, False if existed

        Raises:
            RuntimeError: If scaffolding fails

        """

    @abstractmethod
    def resolve_paths(self, site_root: Path) -> SiteConfiguration:
        """Resolve all paths for an existing site.

        Args:
            site_root: Root directory of the site

        Returns:
            SiteConfiguration with all resolved paths

        Raises:
            ValueError: If site_root is not a valid site
            FileNotFoundError: If required directories don't exist

        """

    @abstractmethod
    def write_post(self, content: str, metadata: dict[str, Any], output_dir: Path, **kwargs: object) -> str:
        """Write a blog post in the appropriate format.

        Args:
            content: Markdown content of the post
            metadata: Post metadata (title, date, tags, authors, etc.)
                Required keys: title, date, slug
                Optional keys: tags, authors, summary, etc.
            output_dir: Directory to write the post to
            **kwargs: Format-specific options

        Returns:
            Path to the written file (as string)

        Raises:
            ValueError: If required metadata is missing
            RuntimeError: If writing fails

        """

    @abstractmethod
    def write_profile(
        self, author_id: str, profile_data: dict[str, Any], profiles_dir: Path, **kwargs: object
    ) -> str:
        """Write an author profile page.

        Args:
            author_id: Unique identifier for the author
            profile_data: Profile information (name, bio, avatar, etc.)
            profiles_dir: Directory to write the profile to
            **kwargs: Format-specific options

        Returns:
            Path to the written file (as string)

        Raises:
            ValueError: If author_id is invalid
            RuntimeError: If writing fails

        """

    @abstractmethod
    def load_config(self, site_root: Path) -> dict[str, Any]:
        """Load site configuration.

        Args:
            site_root: Root directory of the site

        Returns:
            Dictionary of configuration values

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid

        """

    @abstractmethod
    def supports_site(self, site_root: Path) -> bool:
        """Check if this output format can handle the given site.

        Args:
            site_root: Path to check

        Returns:
            True if this format can handle the site, False otherwise

        """

    @property
    @abstractmethod
    def format_type(self) -> str:
        """Return the type identifier for this format (e.g., 'mkdocs', 'hugo')."""

    @abstractmethod
    def get_markdown_extensions(self) -> list[str]:
        """Get list of supported markdown extensions for this format.

        Returns:
            List of markdown extension identifiers
            Example: ["tables", "fenced_code", "admonitions"]

        """

    @abstractmethod
    def get_format_instructions(self) -> str:
        """Generate format-specific instructions for the writer agent.

        Returns plain text that gets injected into the writer prompt to teach
        the LLM about this output format's conventions (front-matter style,
        file naming, special features, etc.).

        This enables the writer agent to adapt to different formats without
        code changes - the LLM learns format conventions through instructions.

        Returns:
            Markdown-formatted instructions for the writer prompt

        Example output:
            '''
            ## Output Format: MkDocs Material

            Your posts will be rendered using MkDocs with the Material theme.

            **Front-matter format**: YAML (between --- markers)
            **Required fields**: title, date, slug, authors, tags, summary
            **File naming**: {date}-{slug}.md (e.g., 2025-01-10-my-post.md)

            **Special features**:
            - Author attribution via .authors.yml (use UUIDs only)
            - Blog plugin for post listing and RSS
            - Tags create automatic taxonomy pages

            **Markdown extensions enabled**:
            - Admonitions: !!! note, !!! warning, !!! tip
            - Code blocks with syntax highlighting
            - Math: $inline$ and $$block$$
            '''

        """

    @abstractmethod
    def list_documents(self) -> "Table":
        """List all documents managed by this output format as an Ibis table.

        Returns an Ibis table with storage identifiers and modification times.
        This enables efficient delta detection using Ibis joins/filters.

        Storage identifiers are format-specific and opaque to callers:
        - MkDocs: relative paths like "posts/2025-01-10-post.md"
        - Hugo: content paths like "content/blog/my-post.md"
        - Database: record IDs like "post:123", "media:456"
        - S3: object keys like "s3://bucket/posts/my-post.md"

        To resolve identifiers to filesystem paths, use resolve_document_path().

        Returns:
            Ibis table with schema:
                - storage_identifier: string (format-specific document ID)
                - mtime_ns: int64 (modification time in nanoseconds)
                Empty table if no documents exist

        Example:
            >>> format = MkDocsOutputFormat()
            >>> format.initialize(site_root)
            >>> docs = format.list_documents()
            >>> docs.head(3).execute()
               storage_identifier                mtime_ns
            0  posts/2025-01-10-post.md         1704067200000000000
            1  profiles/user-123.md             1704070800000000000
            2  docs/media/video.mp4.md          1704074400000000000

        Note:
            - Returns Ibis table for efficient joins/filtering
            - Storage identifiers are format-specific (not necessarily filesystem paths)
            - mtime_ns is nanosecond timestamp for consistency with stat()
            - Subclasses must implement based on their document structure

        """

    @abstractmethod
    def resolve_document_path(self, identifier: str) -> Path:
        """Resolve storage identifier to absolute filesystem path.

        Takes a storage identifier from list_documents() and returns the absolute
        filesystem path where the document can be read. This abstraction allows
        different storage backends (filesystem, database, S3) to work uniformly.

        Args:
            identifier: Storage identifier from list_documents()

        Returns:
            Path: Absolute filesystem path to the document

        Examples:
            >>> # MkDocs (relative path identifier)
            >>> format.resolve_document_path("posts/2025-01-10-post.md")
            Path("/path/to/site/posts/2025-01-10-post.md")

            >>> # Database (record ID identifier)
            >>> format.resolve_document_path("post:123")
            Path("/tmp/egregora-cache/post-123.md")  # Exported to temp file

            >>> # S3 (object key identifier)
            >>> format.resolve_document_path("s3://bucket/posts/my-post.md")
            Path("/tmp/egregora-cache/my-post.md")  # Downloaded to temp file

        Note:
            - Always returns absolute paths (no CWD assumptions)
            - For non-filesystem backends, may export to temporary files
            - Caller is responsible for reading the returned path

        """

    # ===== Storage Protocol Properties (Abstract) =====

    @property
    @abstractmethod
    def posts(self) -> "PostStorage":
        """Get post storage implementation for this format.

        Returns:
            PostStorage implementation (MkDocs, Hugo, Database, etc.)

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """

    @property
    @abstractmethod
    def profiles(self) -> "ProfileStorage":
        """Get profile storage implementation for this format.

        Returns:
            ProfileStorage implementation

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """

    @property
    @abstractmethod
    def journals(self) -> "JournalStorage":
        """Get journal storage implementation for this format.

        Returns:
            JournalStorage implementation

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """

    @property
    @abstractmethod
    def enrichments(self) -> "EnrichmentStorage":
        """Get enrichment storage implementation for this format.

        Returns:
            EnrichmentStorage implementation

        Raises:
            RuntimeError: If format not initialized (call initialize() first)

        """

    @abstractmethod
    def initialize(self, site_root: Path) -> None:
        """Initialize storage implementations for a specific site.

        Must be called before accessing storage properties (posts, profiles, etc.).
        Creates necessary directories and sets up storage backends.

        Args:
            site_root: Root directory of the site

        Raises:
            RuntimeError: If initialization fails
            ValueError: If site_root is invalid

        Example:
            >>> format = MkDocsOutputFormat()
            >>> format.initialize(Path("/path/to/site"))
            >>> posts = format.posts  # Now safe to access

        """

    # ===== Common Utility Methods (Concrete) =====

    @staticmethod
    def normalize_slug(slug: str) -> str:
        """Normalize slug to be URL-safe and filesystem-safe.

        Converts to lowercase, replaces spaces/special chars with hyphens.
        All output formats should use this for consistent slug handling.

        Args:
            slug: Raw slug from metadata (may contain spaces, capitals, etc.)

        Returns:
            Normalized slug (lowercase, hyphens only)

        Examples:
            >>> OutputFormat.normalize_slug("My Great Post!")
            'my-great-post'
            >>> OutputFormat.normalize_slug("AI & Machine Learning")
            'ai-machine-learning'

        """
        from egregora.utils import slugify

        return slugify(slug)

    @staticmethod
    def extract_date_prefix(date_str: str) -> str:
        """Extract clean YYYY-MM-DD date from various formats.

        Handles:
        - Clean dates: "2025-03-02"
        - ISO timestamps: "2025-03-02T10:30:00"
        - Window labels: "2025-03-02 08:01 to 12:49"
        - Datetimes: "2025-03-02 10:30:45"

        All output formats should use this for consistent date handling.

        Args:
            date_str: Date string in various formats

        Returns:
            Clean date in YYYY-MM-DD format, or today's date if parsing fails

        Examples:
            >>> OutputFormat.extract_date_prefix("2025-03-02")
            '2025-03-02'
            >>> OutputFormat.extract_date_prefix("2025-03-02 10:00 to 12:00")
            '2025-03-02'

        """
        if not date_str:
            return datetime.date.today().isoformat()

        date_str = date_str.strip()

        # Try ISO date first (YYYY-MM-DD)
        if len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-":
            try:
                datetime.date.fromisoformat(date_str)
                return date_str
            except (ValueError, AttributeError):
                pass

        # Extract YYYY-MM-DD pattern from longer strings
        match = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
        if match:
            clean_date = match.group(1)
            try:
                datetime.date.fromisoformat(clean_date)
                return clean_date
            except (ValueError, AttributeError):
                pass

        # Fallback: use today's date
        return datetime.date.today().isoformat()

    @staticmethod
    def generate_unique_filename(base_dir: Path, filename_pattern: str, max_attempts: int = 1000) -> Path:
        """Generate unique filename by adding suffix if file exists.

        Pattern for preventing silent overwrites - all formats should use this.

        Args:
            base_dir: Directory where file will be created
            filename_pattern: Filename template with optional {suffix} placeholder
                             e.g., "2025-01-10-my-post.md" or "2025-01-10-my-post{suffix}.md"
            max_attempts: Maximum number of suffix attempts (default 1000)

        Returns:
            Unique filepath that doesn't exist

        Raises:
            RuntimeError: If unique filename cannot be generated after max_attempts

        Examples:
            >>> # If file doesn't exist
            >>> generate_unique_filename(Path("/posts"), "my-post.md")
            Path("/posts/my-post.md")

            >>> # If file exists, adds -2, -3, etc.
            >>> generate_unique_filename(Path("/posts"), "my-post.md")
            Path("/posts/my-post-2.md")

        """
        from egregora.utils import safe_path_join

        # Try original filename first
        if "{suffix}" not in filename_pattern:
            # Add suffix placeholder before extension
            parts = filename_pattern.rsplit(".", 1)
            if len(parts) == 2:
                filename_pattern = f"{parts[0]}{{suffix}}.{parts[1]}"
            else:
                filename_pattern = f"{filename_pattern}{{suffix}}"

        # Try without suffix first
        original_filename = filename_pattern.replace("{suffix}", "")
        filepath = safe_path_join(base_dir, original_filename)

        if not filepath.exists():
            return filepath

        # Generate with suffix
        for suffix in range(2, max_attempts + 2):
            filename = filename_pattern.replace("{suffix}", f"-{suffix}")
            filepath = safe_path_join(base_dir, filename)

            if not filepath.exists():
                return filepath

        msg = f"Could not generate unique filename after {max_attempts} attempts: {filename_pattern}"
        raise RuntimeError(msg)

    def parse_frontmatter(self, content: str) -> tuple[dict, str]:
        """Parse frontmatter from markdown content.

        Default implementation handles YAML frontmatter (used by MkDocs, Jekyll).
        Override in subclasses for format-specific frontmatter (Hugo uses TOML).

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

    def prepare_window(
        self, window_label: str, window_data: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Pre-processing hook called before writer agent processes a window.

        Template Method pattern - base implementation does nothing, subclasses
        override to perform format-specific preparation tasks.

        Examples of format-specific preparation:
        - Database: Begin transaction, lock tables
        - S3: Download existing posts for modification
        - MkDocs: Validate .authors.yml before starting

        Args:
            window_label: Window identifier (e.g., "2025-01-10 10:00 to 12:00")
            window_data: Optional metadata about the window (message count, date range, etc.)

        Returns:
            Optional context dict to pass to finalize_window()

        Note:
            This method is called even for empty windows.
            Implementations should be idempotent and handle errors gracefully.

        Examples:
            >>> # Database implementation
            >>> def prepare_window(self, window_label, window_data):
            >>>     self.connection.begin()
            >>>     return {"transaction_id": self.connection.transaction_id}

        """
        # Base implementation does nothing - subclasses override for specific tasks
        return None

    def finalize_window(
        self,
        window_label: str,
        posts_created: list[str],
        profiles_updated: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Post-processing hook called after writer agent completes a window.

        Template Method pattern - base implementation does nothing, subclasses
        override to perform format-specific finalization tasks.

        Examples of format-specific finalization:
        - MkDocs: Update .authors.yml, regenerate navigation, update tags index
        - Hugo: Run Hugo build to regenerate site, update taxonomies
        - Database: Commit transaction, update search indexes, vacuum
        - S3: Upload changed files to S3, invalidate CloudFront cache

        Args:
            window_label: Window identifier (e.g., "2025-01-10 10:00 to 12:00")
            posts_created: List of post identifiers created during this window
            profiles_updated: List of profile identifiers updated during this window
            metadata: Optional metadata about the window (duration, token count, context from prepare_window)

        Note:
            This method is called even if no posts/profiles were created.
            Implementations should be idempotent and handle empty lists gracefully.

        Examples:
            >>> # MkDocs implementation
            >>> def finalize_window(self, window_label, posts_created, profiles_updated, metadata):
            >>>     self._update_authors_yml(profiles_updated)
            >>>     self._regenerate_tags_index(posts_created)
            >>>     logger.info(f"Finalized MkDocs window: {window_label}")

            >>> # Database implementation
            >>> def finalize_window(self, window_label, posts_created, profiles_updated, metadata):
            >>>     self.connection.commit()
            >>>     self._update_search_index(posts_created)
            >>>     logger.info(f"Committed database window: {window_label}")

        """
        # Base implementation does nothing - subclasses override for specific tasks


class OutputFormatRegistry:
    """Registry for managing available output formats."""

    def __init__(self) -> None:
        self._formats: dict[str, type[OutputFormat]] = {}

    def register(self, format_class: type[OutputFormat]) -> None:
        """Register an output format class.

        Args:
            format_class: Class inheriting from OutputFormat

        """
        instance = format_class()
        self._formats[instance.format_type] = format_class

    def get_format(self, format_type: str) -> OutputFormat:
        """Get an output format by type.

        Args:
            format_type: Type identifier (e.g., 'mkdocs')

        Returns:
            Instance of the requested output format

        Raises:
            KeyError: If format_type is not registered

        """
        if format_type not in self._formats:
            available = ", ".join(self._formats.keys())
            msg = f"Output format '{format_type}' not found. Available: {available}"
            raise KeyError(msg)
        return self._formats[format_type]()

    def detect_format(self, site_root: Path) -> OutputFormat | None:
        """Auto-detect the appropriate output format for a given site.

        Args:
            site_root: Path to analyze

        Returns:
            Instance of detected output format, or None if no match

        """
        for format_class in self._formats.values():
            instance = format_class()
            if instance.supports_site(site_root):
                return instance
        return None

    def list_formats(self) -> list[str]:
        """List all registered output format types."""
        return list(self._formats.keys())


output_registry = OutputFormatRegistry()


def create_output_format(site_root: Path, format_type: str = "mkdocs") -> OutputFormat:
    """Create and initialize an OutputFormat based on configuration.

    This is the main factory function for creating output formats. It uses the
    output_registry to get the appropriate format class and initializes it.

    Industry standard: Configuration-driven factory pattern.
    Format type specified in .egregora/config.yml, defaults to mkdocs.

    Args:
        site_root: Root directory for the site
        format_type: Output format type from config ('mkdocs', 'hugo', etc.)

    Returns:
        Initialized OutputFormat instance

    Raises:
        KeyError: If format_type is not registered
        RuntimeError: If format initialization fails

    Examples:
        >>> # From config: output.format = "mkdocs"
        >>> fmt = create_output_format(site_root, format_type="mkdocs")
        >>> # From config: output.format = "hugo"
        >>> fmt = create_output_format(site_root, format_type="hugo")

    Note:
        This function automatically ensures the registry is populated by
        importing egregora.rendering (which registers MkDocs and Hugo formats).

    """
    # Ensure registry is populated by importing rendering module
    # This triggers registration in rendering/__init__.py
    import egregora.rendering  # noqa: F401, PLC0415

    # Get format class from registry
    output_format = output_registry.get_format(format_type)

    # Initialize with site_root
    output_format.initialize(site_root)

    return output_format
