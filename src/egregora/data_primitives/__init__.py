"""Fundamental data primitives for Egregora pipeline.

This module consolidates all essential, universal data structures that define
the core objects flowing through the system:

- **Document types**: Document, DocumentType, DocumentCollection


These primitives form the foundation of the data model, used by both
input adapters (to produce standardized data) and output adapters (to
consume and publish it).
"""

from egregora.data_primitives.document import Document, DocumentCollection, DocumentType, MediaAsset
from egregora.data_primitives.protocols import (
    DocumentMetadata,
    OutputAdapter,
    OutputSink,
    SiteScaffolder,
    UrlContext,
    UrlConvention,
)

__all__ = [
    # Document types
    "Document",
    "DocumentCollection",
    "DocumentMetadata",
    "DocumentType",
    # Type aliases
    "MediaAsset",
    # Protocols (ISP-compliant)
    "OutputSink",
    "SiteScaffolder",
    # Protocols (legacy/backward compatibility)
    "OutputAdapter",
    "OutputSink",
    "SiteScaffolder",
    "UrlContext",
    "UrlConvention",
]
