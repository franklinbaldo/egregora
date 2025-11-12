"""URL convention abstraction for document addressing.

URL conventions define how documents are mapped to URLs. They are pure functions
with no I/O or side effects - just deterministic URL calculation.

Conventions are identified by name and version for compatibility checking between
Core and OutputFormats.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from egregora.core.document import Document


@dataclass(frozen=True, slots=True)
class UrlContext:
    """Context for URL generation.

    Provides environment information needed to generate URLs (base URL, paths, locale).
    Immutable to ensure deterministic URL generation.
    """

    base_url: str = ""
    """Base URL for the site (e.g., 'https://example.com' or '')."""

    site_prefix: str = ""
    """Optional path prefix for the site (e.g., '/blog')."""

    base_path: Path | None = None
    """Optional base filesystem path (for formats that need it)."""

    locale: str | None = None
    """Optional locale for internationalized URLs (e.g., 'en', 'pt-BR')."""


class UrlConvention(Protocol):
    """Protocol for URL conventions.

    Defines how documents are mapped to canonical URLs. Implementations must be:
    - **Deterministic**: Same document always produces same URL
    - **Stable**: Re-generating doesn't change URL (no timestamps, random IDs, etc.)
    - **Pure**: No I/O, no side effects, just URL calculation

    Conventions are identified by name/version for compatibility checking.
    """

    @property
    def name(self) -> str:
        """Convention identifier (e.g., 'legacy-mkdocs', 'flat', 'hugo-like').

        Used to verify Core and OutputFormat use the same convention.
        """
        ...

    @property
    def version(self) -> str:
        """Convention version (e.g., 'v1', '2024-01', 'latest').

        Used for compatibility checking and future migrations.
        """
        ...

    def canonical_url(self, document: Document, ctx: UrlContext) -> str:
        """Generate canonical URL for a document.

        Must be deterministic and stable:
        - Same document + context -> same URL
        - No random components, no timestamps (unless from document metadata)
        - URL should not change on re-generation

        Args:
            document: The document to generate URL for
            ctx: Context with base URL, paths, locale, etc.

        Returns:
            Canonical URL as string (e.g., '/posts/2025-01-11-my-post/')

        Examples:
            >>> ctx = UrlContext(base_url="https://example.com")
            >>> convention.canonical_url(post_doc, ctx)
            'https://example.com/posts/2025-01-11-my-post/'

        """
        ...
