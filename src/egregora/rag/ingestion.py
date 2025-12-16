"""Document chunking and ingestion for RAG.

DEPRECATED: This module is a compatibility shim for V3 infrastructure.
"""

from __future__ import annotations

from egregora_v3.core.ingestion import chunks_from_document, chunks_from_documents

__all__ = [
    "chunks_from_document",
    "chunks_from_documents",
]
