# Document Abstraction: Content-Addressed Storage Plan

**Status**: DRAFT
**Created**: 2025-11-11
**Priority**: P0 - Architectural Foundation

## Problem Statement

The current architecture has several design flaws:

1. **Core has opinions about storage**: Pipeline stages and agents know about filesystem paths, filename conventions, and storage locations
2. **Tight coupling**: Writer agent directly calls storage methods with format-specific knowledge
3. **No unified identity**: Different document types use different ID schemes (slugs, UUIDs, filenames)
4. **Parent relationships unclear**: URL enrichments reference media, but this relationship is implicit
5. **Output format locked in**: Hard to add new output formats (Hugo, Astro, etc.) because core assumes MkDocs conventions

## Proposed Solution

Introduce a **Document abstraction** that:
- Represents all content produced by the pipeline (posts, profiles, journals, enrichments, media)
- Uses **content-addressed IDs** (UUID v5 of content hash)
- Declares **parent relationships** explicitly (enrichments → media)
- Has **no storage opinions** - output formats decide where to save
- Is **extensible** for future document types

## Core Abstraction

### Document Dataclass

```python
# src/egregora/core/document.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid5, NAMESPACE_DNS

NAMESPACE_DOCUMENT = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # Well-known namespace


class DocumentType(Enum):
    """Types of documents in the Egregora pipeline."""
    POST = "post"
    PROFILE = "profile"
    JOURNAL = "journal"
    ENRICHMENT_URL = "enrichment_url"
    ENRICHMENT_MEDIA = "enrichment_media"
    MEDIA = "media"  # Future: downloaded images, videos


@dataclass(frozen=True, slots=True)
class Document:
    """Content-addressed document produced by the pipeline.

    Core abstraction for all generated content. The document ID is deterministic
    based on content, enabling deduplication and cache invalidation.

    Output formats decide storage paths and filenames. Core has no opinions.
    """

    # Core identity
    content: str
    type: DocumentType

    # Content-addressed ID (computed from content hash)
    @property
    def document_id(self) -> str:
        """UUID v5 of content hash. Deterministic and deduplicatable."""
        content_hash = hashlib.sha256(self.content.encode('utf-8')).hexdigest()
        return str(uuid5(NAMESPACE_DOCUMENT, content_hash))

    # Metadata (format-agnostic)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Parent relationship (for enrichments)
    parent_id: str | None = None  # Document ID of parent (e.g., media file)

    # Provenance
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_window: str | None = None  # Window label if from windowed pipeline

    # Hints for output formats (optional)
    suggested_path: str | None = None  # E.g., "posts/2025-01-10-my-post.md"

    def with_parent(self, parent_id: str) -> "Document":
        """Return new document with parent relationship."""
        return Document(
            content=self.content,
            type=self.type,
            metadata=self.metadata.copy(),
            parent_id=parent_id,
            created_at=self.created_at,
            source_window=self.source_window,
            suggested_path=self.suggested_path,
        )
```

### Document Collection

```python
@dataclass
class DocumentCollection:
    """Batch of documents produced by a single operation (e.g., one window)."""

    documents: list[Document]
    window_label: str | None = None

    def by_type(self, doc_type: DocumentType) -> list[Document]:
        """Filter documents by type."""
        return [doc for doc in self.documents if doc.type == doc_type]

    def find_children(self, parent_id: str) -> list[Document]:
        """Find all documents with given parent."""
        return [doc for doc in self.documents if doc.parent_id == parent_id]
```

## Changes Required

### Phase 1: Core Document Model (P0)

**Files to create:**
- `src/egregora/core/document.py` - Document, DocumentType, DocumentCollection
- `tests/core/test_document.py` - Document identity, parent relationships, deduplication

**Changes:**
- No breaking changes yet - this is purely additive

**Timeline**: 2-4 hours

---

### Phase 2: Update Writer Agent (P0)

**Current behavior:**
```python
# Writer agent directly calls storage
ctx.deps.posts.write(slug=metadata.slug, metadata=..., content=...)
ctx.deps.profiles.write(author_uuid=..., content=...)
```

**New behavior:**
```python
# Writer agent produces Documents
from egregora.data_primitives.document import Document, DocumentType

@agent.tool
def write_post_tool(ctx: RunContext[WriterAgentState], metadata: PostMetadata, content: str) -> WritePostResult:
    doc = Document(
        content=content,
        type=DocumentType.POST,
        metadata=metadata.model_dump(exclude_none=True),
        source_window=ctx.deps.window_label,
        suggested_path=f"posts/{metadata.date}-{metadata.slug}.md",  # Hint only
    )

    # Store via document storage (new abstraction)
    doc_id = ctx.deps.document_storage.add(doc)
    return WritePostResult(status="success", document_id=doc_id)
```

**Files to change:**
- `src/egregora/agents/writer/agent.py` - Tools produce Documents
- `src/egregora/agents/writer/core.py` - Accept DocumentStorage dependency

**Timeline**: 4-6 hours

---

### Phase 3: Document Storage Protocol (P0)

**New storage abstraction:**

```python
# src/egregora/storage/documents.py

from egregora.data_primitives.document import Document, DocumentType

@runtime_checkable
class DocumentStorage(Protocol):
    """Storage interface for content-addressed documents.

    Output formats implement this protocol to decide storage paths and filenames.
    Core pipeline only works with Document objects - no filesystem knowledge.
    """

    def add(self, document: Document) -> str:
        """Store document. Returns document_id.

        Implementation decides:
        - Where to save (path)
        - What filename to use
        - Whether to add frontmatter
        - Whether to update registries (.authors.yml, etc.)

        Args:
            document: Content-addressed document

        Returns:
            Document ID (content hash)
        """
        ...

    def get(self, document_id: str) -> Document | None:
        """Retrieve document by ID."""
        ...

    def exists(self, document_id: str) -> bool:
        """Check if document exists."""
        ...

    def list_by_type(self, doc_type: DocumentType) -> list[Document]:
        """List all documents of given type."""
        ...

    def find_children(self, parent_id: str) -> list[Document]:
        """Find all enrichments for a parent document."""
        ...
```

**MkDocs implementation:**

```python
# src/egregora/rendering/mkdocs.py

class MkDocsDocumentStorage:
    """MkDocs-specific document storage with opinionated paths."""

    def __init__(self, site_root: Path):
        self.site_root = site_root

    def add(self, document: Document) -> str:
        """Store document in MkDocs-specific location."""

        # MkDocs decides storage path based on document type
        if document.type == DocumentType.POST:
            path = self._post_path(document)
            self._write_with_frontmatter(path, document)

        elif document.type == DocumentType.PROFILE:
            path = self._profile_path(document)
            self._write_with_frontmatter(path, document)
            self._update_authors_yml(document)

        elif document.type == DocumentType.ENRICHMENT_URL:
            path = self._url_enrichment_path(document)
            self._write_plain_markdown(path, document)

        elif document.type == DocumentType.JOURNAL:
            path = self._journal_path(document)
            self._write_with_frontmatter(path, document)

        return document.document_id

    def _post_path(self, doc: Document) -> Path:
        """MkDocs convention: posts/{date}-{slug}.md"""
        date = doc.metadata.get("date", datetime.now(UTC).strftime("%Y-%m-%d"))
        slug = self._normalize_slug(doc.metadata.get("slug", doc.document_id[:8]))
        return self.site_root / "posts" / f"{date}-{slug}.md"

    def _profile_path(self, doc: Document) -> Path:
        """MkDocs convention: profiles/{uuid}.md"""
        author_uuid = doc.metadata["uuid"]
        return self.site_root / "profiles" / f"{author_uuid}.md"

    def _url_enrichment_path(self, doc: Document) -> Path:
        """MkDocs convention: docs/media/urls/{uuid}.md"""
        # Use document_id as filename (content-addressed)
        return self.site_root / "docs" / "media" / "urls" / f"{doc.document_id}.md"
```

**Files to create:**
- `src/egregora/storage/documents.py` - DocumentStorage protocol
- `src/egregora/rendering/mkdocs_documents.py` - MkDocsDocumentStorage

**Files to deprecate** (after migration):
- `src/egregora/storage/__init__.py` - Old PostStorage, ProfileStorage protocols
- `src/egregora/rendering/mkdocs.py` - Old storage classes (keep output format)

**Timeline**: 6-8 hours

---

### Phase 4: Parent Relationships for Enrichments (P1)

**Problem**: URL enrichments reference media, but relationship is implicit

**Solution**: Enrichments are Documents with parent_id

```python
# When enriching a URL
url = "https://example.com/article"
enrichment_content = "# Article Title\n\nSummary..."

# Create enrichment document with parent
enrichment = Document(
    content=enrichment_content,
    type=DocumentType.ENRICHMENT_URL,
    metadata={"url": url, "enriched_at": datetime.now(UTC)},
    parent_id=parent_media_id,  # Link to parent media document
)

# Storage can now:
# 1. Find all enrichments for a media file
# 2. Clean up orphaned enrichments
# 3. Update enrichments when media changes
```

**Use cases enabled:**
- `storage.find_children(media_doc_id)` → list all enrichments
- RAG indexing: associate enrichments with source media
- Cleanup: delete enrichments when parent media removed

**Files to change:**
- `src/egregora/enrichment/core.py` - Produce Documents with parent_id
- `src/egregora/rendering/mkdocs_documents.py` - Store parent relationships

**Timeline**: 3-4 hours

---

### Phase 5: RAG Integration (P1)

**Current RAG indexing:**
```python
# Assumes filesystem paths and formats
index_documents_for_rag(output_format, rag_dir, embedding_model)
```

**New RAG indexing:**
```python
# Works with Document abstraction
def index_documents(
    documents: list[Document],
    rag_store: VectorStore,
    embedding_model: str,
) -> int:
    """Index documents in RAG store.

    Uses document_id as chunk identifier. Parent relationships preserved.
    """
    chunks = []
    for doc in documents:
        # Chunk document content
        doc_chunks = chunk_document(doc.content, chunk_size=1000)

        for i, chunk_text in enumerate(doc_chunks):
            chunks.append({
                "chunk_id": f"{doc.document_id}:{i}",
                "document_id": doc.document_id,
                "document_type": doc.type.value,
                "parent_id": doc.parent_id,  # Preserve relationships
                "content": chunk_text,
                "metadata": doc.metadata,
            })

    return rag_store.add_chunks(chunks)
```

**Benefits:**
- No filesystem knowledge in RAG indexing
- Parent relationships enable "find enrichments for media"
- Content-addressed IDs enable deduplication

**Files to change:**
- `src/egregora/agents/shared/rag/indexing.py` - Accept Documents instead of paths
- `src/egregora/agents/shared/rag/store.py` - Store parent_id in chunks

**Timeline**: 4-5 hours

---

### Phase 6: Migration Path (P2)

**Backward compatibility strategy:**

1. **Dual storage**: Write to both old and new storage during transition
2. **Adapter pattern**: Wrap old storage in DocumentStorage interface
3. **Gradual migration**: One document type at a time (posts → profiles → journals → enrichments)

```python
class LegacyStorageAdapter(DocumentStorage):
    """Adapter: Make old PostStorage/ProfileStorage look like DocumentStorage."""

    def __init__(self, post_storage: PostStorage, profile_storage: ProfileStorage):
        self.post_storage = post_storage
        self.profile_storage = profile_storage

    def add(self, document: Document) -> str:
        if document.type == DocumentType.POST:
            # Convert Document → old storage format
            self.post_storage.write(
                slug=document.metadata["slug"],
                metadata=document.metadata,
                content=document.content,
            )
        elif document.type == DocumentType.PROFILE:
            self.profile_storage.write(
                author_uuid=document.metadata["uuid"],
                content=document.content,
            )

        return document.document_id
```

**Timeline**: 3-4 hours

---

## Benefits

### 1. Clean Separation of Concerns

**Before:**
```python
# Core knows about MkDocs paths
write_profile(author_uuid, content, profiles_dir=Path("output/profiles"))
```

**After:**
```python
# Core produces documents, output decides storage
doc = Document(content=content, type=DocumentType.PROFILE, metadata={...})
storage.add(doc)  # MkDocs decides profiles/{uuid}.md, Hugo decides authors/{uuid}.html
```

### 2. Content-Addressed Identity

**Benefits:**
- Deduplication: Same content → same ID
- Cache invalidation: Content changes → ID changes
- Reproducibility: Re-running pipeline produces same IDs

**Example:**
```python
doc1 = Document(content="Alice's profile", type=DocumentType.PROFILE)
doc2 = Document(content="Alice's profile", type=DocumentType.PROFILE)

assert doc1.document_id == doc2.document_id  # Same content = same ID
```

### 3. Explicit Parent Relationships

**Before:** Implicit, filename-based
```
docs/media/urls/{uuid}.md  # Which media does this enrich?
```

**After:** Explicit parent_id
```python
enrichment = Document(
    content="...",
    type=DocumentType.ENRICHMENT_URL,
    parent_id="abc-123",  # Points to parent media document
)
```

### 4. Output Format Flexibility

**Easy to add new formats:**

```python
# Hugo implementation
class HugoDocumentStorage:
    def _post_path(self, doc: Document) -> Path:
        # Hugo convention: content/posts/{slug}/index.md
        return self.site_root / "content" / "posts" / doc.metadata["slug"] / "index.md"

    def _profile_path(self, doc: Document) -> Path:
        # Hugo convention: content/authors/{uuid}/_index.md
        return self.site_root / "content" / "authors" / doc.metadata["uuid"] / "_index.md"
```

No core changes needed - just implement DocumentStorage protocol.

### 5. Testability

**Before:** Hard to test storage without filesystem
```python
def test_write_profile():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = MkDocsProfileStorage(Path(tmpdir))
        storage.write(...)  # Filesystem operations
```

**After:** Easy to test with in-memory storage
```python
def test_write_profile():
    storage = InMemoryDocumentStorage()
    doc = Document(content="...", type=DocumentType.PROFILE)
    doc_id = storage.add(doc)
    assert storage.get(doc_id) == doc  # No filesystem
```

## Migration Strategy

### Step 1: Introduce Document abstraction (non-breaking)
- Add `core/document.py`
- Add tests
- No changes to existing code

### Step 2: Add DocumentStorage protocol (non-breaking)
- Add `storage/documents.py`
- Implement MkDocsDocumentStorage
- Keep old storage classes for now

### Step 3: Update writer agent to produce Documents
- Change tools to return Documents
- Use LegacyStorageAdapter for backward compatibility
- Both old and new storage write simultaneously

### Step 4: Migrate RAG indexing
- Update to accept Documents instead of paths
- Remove filesystem assumptions

### Step 5: Deprecate old storage protocols
- Remove PostStorage, ProfileStorage, JournalStorage
- Remove old MkDocs storage classes
- Update all consumers

### Step 6: Clean up
- Remove LegacyStorageAdapter
- Remove deprecated code paths
- Update documentation

## Open Questions

1. **Document versioning**: Should we track document versions (content changes over time)?
2. **Metadata schema**: Should each DocumentType have a strict metadata schema?
3. **Caching**: Should DocumentStorage have a caching layer for content-addressed lookups?
4. **Garbage collection**: How do we clean up orphaned enrichments when parent deleted?
5. **Cross-format migration**: How do we convert documents from MkDocs → Hugo?

## Success Criteria

- [ ] Core pipeline has zero filesystem knowledge
- [ ] Output formats decide all storage paths
- [ ] Content-addressed IDs enable deduplication
- [ ] Parent relationships explicit in Document model
- [ ] Easy to add new output formats (Hugo, Astro)
- [ ] All existing tests pass
- [ ] No breaking changes for end users

## Timeline Estimate

- Phase 1 (Core model): 2-4 hours
- Phase 2 (Writer agent): 4-6 hours
- Phase 3 (Storage protocol): 6-8 hours
- Phase 4 (Parent relationships): 3-4 hours
- Phase 5 (RAG integration): 4-5 hours
- Phase 6 (Migration): 3-4 hours

**Total**: 22-31 hours (~3-4 days)

## References

- Content-addressed storage: IPFS, Git, CAS
- Document abstraction: Pandoc, Sphinx
- Parent relationships: FHIR DocumentReference
- Output format flexibility: Pandoc, Hugo, Docusaurus
