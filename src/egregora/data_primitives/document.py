"""Data primitive placeholders."""

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class Author:
    """Represents a content author."""

    id: str
    name: str | None = None


@dataclass(frozen=True, slots=True)
class Category:
    """Represents a content category or tag."""

    term: str


class Document:
    pass


class DocumentType(Enum):
    POST = "POST"


class OutputSink:
    pass


class DocumentMetadata:
    pass


@dataclass
class UrlContext:
    """Context for URL generation.

    Attributes:
        base_url: The base URL for the site (e.g., "https://example.com")
        site_prefix: Optional site prefix/path (e.g., "blog")
    """

    base_url: str | None = None
    site_prefix: str | None = None


class UrlConvention:
    pass


class MediaAsset:
    pass
