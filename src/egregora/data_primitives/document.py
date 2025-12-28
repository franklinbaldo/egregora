"""Data primitive placeholders."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass(frozen=True, slots=True)
class Author:
    """Represents a content author."""

    id: str
    name: str | None = None


@dataclass(frozen=True, slots=True)
class Category:
    """Represents a content category or tag."""

    term: str


class DocumentType(str, Enum):
    """Document type enumeration (copied from V3 for V2 compatibility)."""

    RECAP = "recap"
    NOTE = "note"
    PLAN = "plan"
    POST = "post"
    MEDIA = "media"
    PROFILE = "profile"
    ENRICHMENT = "enrichment"
    ENRICHMENT_URL = "enrichment_url"
    ENRICHMENT_MEDIA = "enrichment_media"
    ENRICHMENT_IMAGE = "enrichment_image"
    ENRICHMENT_VIDEO = "enrichment_video"
    ENRICHMENT_AUDIO = "enrichment_audio"
    CONCEPT = "concept"
    JOURNAL = "journal"
    ANNOTATION = "annotation"


@dataclass
class Document:
    """Simplified Document class for V2 (copied from V3 for compatibility).

    This is a simplified version that doesn't use Pydantic, maintaining V2/V3 separation.
    """

    id: str
    title: str
    doc_type: DocumentType
    content: str | bytes
    metadata: dict[str, Any] = field(default_factory=dict)
    url_path: str | None = None
    parent: "Document | None" = None


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
