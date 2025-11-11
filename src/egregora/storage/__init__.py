"""Storage protocols for backend-agnostic document persistence.

MODERN (Phase 5): Consolidated to single OutputFormat abstraction.

The old storage protocols (PostStorage, ProfileStorage, JournalStorage) have been
removed in favor of the unified OutputFormat protocol that handles all document types.

Architecture:
- OutputFormat.serve(Document) - Unified write interface for all document types
- Document.type - Discriminates between posts, profiles, journals, enrichments, media
- UrlConvention - Determines URLs for documents
- UrlContext - Provides context for URL generation

Migration Guide:
- PostStorage.write() → output_format.serve(Document(type=POST, ...))
- ProfileStorage.write() → output_format.serve(Document(type=PROFILE, ...))
- JournalStorage.write() → output_format.serve(Document(type=JOURNAL, ...))
- Reading: Use direct filesystem access via paths (TODO: Phase 6 will add read methods)
"""

from egregora.storage.output_format import OutputFormat
from egregora.storage.url_convention import UrlContext, UrlConvention

__all__ = [
    # Backend-agnostic abstractions (Phase 4+5)
    "OutputFormat",
    "UrlConvention",
    "UrlContext",
]
