"""Storage protocols for backend-agnostic document persistence.

DEPRECATED: This module re-exports protocols from data_primitives for backward compatibility.
New code should import directly from data_primitives.protocols:

    from egregora.data_primitives.protocols import OutputAdapter, UrlConvention, UrlContext

The old storage protocols (PostStorage, ProfileStorage, JournalStorage) have been
removed in favor of the unified OutputAdapter protocol that handles all document types.

Architecture:
- OutputAdapter.serve(Document) - Unified write interface for all document types
- OutputAdapter.read_document(type, id) - Unified read interface (Phase 6)
- OutputAdapter.list_documents(type?) - Unified list interface (Phase 6)
- Document.type - Discriminates between posts, profiles, journals, enrichments, media
- UrlConvention - Determines URLs for documents
- UrlContext - Provides context for URL generation

Migration Guide:
- PostStorage.write() → output_format.serve(Document(type=POST, ...))
- ProfileStorage.write() → output_format.serve(Document(type=PROFILE, ...))
- JournalStorage.write() → output_format.serve(Document(type=JOURNAL, ...))
- ProfileStorage.read() → output_format.read_document(DocumentType.PROFILE, uuid)
"""

# Re-export from data_primitives for backward compatibility
from egregora.data_primitives.protocols import OutputAdapter, UrlContext, UrlConvention

__all__ = [
    # Backend-agnostic abstractions (Phase 4+5)
    "OutputAdapter",
    "UrlConvention",
    "UrlContext",
]
