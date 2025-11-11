"""Core abstractions for Egregora pipeline.

This module contains fundamental data structures that the pipeline uses
to represent content before it's serialized to an output format.

Key abstractions:
- Document: Content-addressed representation of generated content
- DocumentType: Enumeration of document types (posts, profiles, enrichments, etc.)
- DocumentCollection: Batch of documents from a single operation
"""

from egregora.core.document import Document, DocumentCollection, DocumentType

__all__ = ["Document", "DocumentCollection", "DocumentType"]
