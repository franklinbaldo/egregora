"""Abstract base class for output formats (MkDocs, Hugo, Jekyll, etc.)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SiteConfiguration:
    """Configuration for a documentation/blog site."""

    site_root: Path  # Root directory of the site
    site_name: str  # Display name
    docs_dir: Path  # Where content lives
    posts_dir: Path  # Where blog posts go
    profiles_dir: Path  # Where author profiles go
    media_dir: Path  # Where media files go
    config_file: Path | None  # Path to config file (if exists)
    additional_paths: dict[str, Path] | None = None  # Format-specific paths


class OutputFormat(ABC):
    """Abstract base class for output formats.

    Output formats are responsible for:
    1. Scaffolding new sites with proper directory structure
    2. Writing blog posts in the appropriate format
    3. Managing author profiles
    4. Resolving site paths and configuration
    5. Generating any format-specific files (config, templates, etc.)
    """

    @abstractmethod
    def scaffold_site(self, site_root: Path, site_name: str, **kwargs) -> tuple[Path, bool]:
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
        pass

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
        pass

    @abstractmethod
    def write_post(
        self,
        content: str,
        metadata: dict[str, Any],
        output_dir: Path,
        **kwargs,
    ) -> str:
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
        pass

    @abstractmethod
    def write_profile(
        self,
        author_id: str,
        profile_data: dict[str, Any],
        profiles_dir: Path,
        **kwargs,
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
        pass

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
        pass

    @abstractmethod
    def supports_site(self, site_root: Path) -> bool:
        """Check if this output format can handle the given site.

        Args:
            site_root: Path to check

        Returns:
            True if this format can handle the site, False otherwise
        """
        pass

    @property
    @abstractmethod
    def format_type(self) -> str:
        """Return the type identifier for this format (e.g., 'mkdocs', 'hugo')."""
        pass

    @abstractmethod
    def get_markdown_extensions(self) -> list[str]:
        """Get list of supported markdown extensions for this format.

        Returns:
            List of markdown extension identifiers
            Example: ["tables", "fenced_code", "admonitions"]
        """
        pass


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
            raise KeyError(f"Output format '{format_type}' not found. Available: {available}")
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


# Global registry instance
output_registry = OutputFormatRegistry()
