"""Fundamental data primitives for Egregora pipeline.

This module consolidates all essential, universal data structures that define
the core objects flowing through the system:

- **Document types**: Document, DocumentType, DocumentCollection
- **Type aliases**: GroupSlug, PostSlug

These primitives form the foundation of the data model, used by both
input adapters (to produce standardized data) and output adapters (to
consume and publish it).
"""

from egregora.data_primitives.base_types import GroupSlug, PostSlug
from egregora.data_primitives.document import Document, DocumentCollection, DocumentType
from egregora.data_primitives.protocols import OutputAdapter, UrlContext, UrlConvention

__all__ = [
    # Document types
    "Document",
    "DocumentCollection",
    "DocumentType",
    # Type aliases
    "GroupSlug",
    # Protocols
    "OutputAdapter",
    "PostSlug",
    "UrlContext",
    "UrlConvention",
]
