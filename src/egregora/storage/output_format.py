"""Output format abstraction for document persistence.

Output formats handle document persistence at URLs defined by conventions.
They adopt a UrlConvention (shared with Core) and ensure documents are served
at those URLs.

Backend-agnostic: can use filesystem, S3, DB, CMS, or any other storage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from egregora.core.document import Document
    from egregora.storage.url_convention import UrlConvention


class OutputFormat(Protocol):
    """Protocol for output format implementations.

    Handles document persistence at URLs defined by a UrlConvention.
    The format adopts a convention (shared with Core) and ensures documents
    are available at the URLs that convention generates.

    Backend-agnostic: implementations can use any storage mechanism (filesystem,
    database, object storage, CMS API, etc.). Core never sees implementation details.

    Key design: Format does NOT return URLs to Core. Core calculates URLs
    independently using the same convention. This achieves perfect separation.
    """

    @property
    def url_convention(self) -> UrlConvention:
        """The URL convention this format uses.

        Must match Core's convention (verified by name/version at startup).
        Both Core and Format calculate URLs independently using this convention.

        Returns:
            The UrlConvention instance used by this format

        Examples:
            >>> format.url_convention.name
            'legacy-mkdocs'
            >>> format.url_convention.version
            'v1'
        """
        ...

    def serve(self, document: Document) -> None:
        """Ensure document is served at the URL defined by url_convention.

        Does NOT return URL (Core calculates URL independently).
        Does NOT return status (idempotency is internal concern).

        Internally:
        1. Calculates URL using self.url_convention.canonical_url()
        2. Converts URL to backend-specific location (path, key, ID, etc.)
        3. Persists document (write file, save to DB, upload, queue, etc.)
        4. Handles idempotency, collisions, versioning internally

        Strategy (synchronous/asynchronous/batch/lazy) is format's choice.
        Core never knows HOW persistence happens, only requests it.

        Args:
            document: The document to serve

        Examples:
            >>> # Core flow
            >>> url = url_convention.canonical_url(document, ctx)  # Core calculates
            >>> output_format.serve(document)  # Format persists (fire-and-forget)
            >>> # Use url in content, cross-refs, etc.

        Note:
            This method should be idempotent: calling it multiple times with the
            same document should be a safe no-op (no errors, no duplicates).
        """
        ...
