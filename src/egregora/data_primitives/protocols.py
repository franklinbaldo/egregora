"""Defines the protocols for data primitives."""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from egregora.data_primitives.document import Document


class OutputSink(Protocol):
    """A protocol for components that can persist documents."""

    def publish(self, doc: "Document") -> None:
        """Persists a single document to the output destination."""
        ...


class UrlContext(Protocol):
    """A protocol for components that can resolve canonical URLs for documents."""

    def get_url(self, doc: "Document") -> str:
        """Returns the canonical, site-relative URL for a document."""
        ...


class ContentLibrary(Protocol):
    """A protocol for a unified content storage and retrieval system."""

    def save(self, doc: "Document") -> None:
        """Saves or updates a document in the library."""
        ...
