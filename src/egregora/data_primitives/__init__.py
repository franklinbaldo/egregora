"""Fundamental data primitives for Egregora pipeline.

This module consolidates all essential, universal data structures that define
the core objects flowing through the system:

- **Document types**: Document, DocumentType, DocumentCollection
- **Type aliases**: PostSlug

These primitives form the foundation of the data model, used by both
input adapters (to produce standardized data) and output adapters (to
consume and publish it).
"""

from typing import NewType

from egregora.data_primitives.document import Document, DocumentCollection, DocumentType, MediaAsset
from egregora.data_primitives.protocols import (
    DocumentMetadata,
    OutputSink,
    SiteScaffolder,
    UrlContext,
    UrlConvention,
)

# Type aliases
GroupSlug = NewType("GroupSlug", str)
PostSlug = NewType("PostSlug", str)

__all__ = [
    # Document types
    "Document",
    "DocumentCollection",
    "DocumentMetadata",
    "DocumentType",
    # Type aliases
    "GroupSlug",
    "MediaAsset",
    # Protocols (ISP-compliant)
    "OutputSink",
    "PostSlug",
    "SiteScaffolder",
    "UrlContext",
    "UrlConvention",
]
