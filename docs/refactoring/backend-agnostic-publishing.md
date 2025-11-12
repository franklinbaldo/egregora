# Refactor: Backend-Agnostic Document Publishing

## Problem

Current storage is **tightly coupled to filesystem/MkDocs**:

- `MkDocsDocumentStorage` (457 lines) knows about paths, directories, frontmatter, `.authors.yml`
- 6 type-specific path methods, 3-layer collision detection
- **No abstraction for URLs** - paths are exposed, not permalinks
- **Cannot support alternative backends** - DB, S3, headless CMS require rewrite
- **Core knows about storage** - publish/update/create status, idempotency, collisions

**Root cause**: Core is trying to manage persistence concerns that should be internal to the output format.

## Solution: Radical Simplification

### Core Principle

**Core doesn't publish. Core doesn't know about storage. Core only asks for URLs and hands over documents.**

```
Core:     "What's the URL for this document?"
Format:   "/posts/2025-01-11-my-post/"

Core:     "Ensure this document is available at that URL."
Format:   [writes file / saves to DB / uploads to S3 - INTERNALLY]

Core:     Uses URL in content, cross-references, etc.
```

### Architecture

1. **UrlConvention** - Defines URL policy (pure function, no I/O)
2. **OutputAdapter** - Adopts a convention, ensures documents are served at those URLs
3. **Core** - Asks for URLs, requests availability, uses URLs

**Key insight**: Separate URL generation (policy) from document persistence (mechanism).

## Minimal Interface

### 1. UrlConvention (URL Policy)

```python
from typing import Protocol
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class UrlContext:
    """Context for URL generation."""
    base_url: str = ""
    site_prefix: str = ""
    base_path: Path | None = None
    locale: str | None = None

class UrlConvention(Protocol):
    """Defines how URLs are generated for documents.

    Pure function: same document -> same URL (deterministic, stable).
    No I/O, no side effects - just URL calculation.

    Conventions are identified by name/version for compatibility checking.
    """

    @property
    def name(self) -> str:
        """Convention identifier (e.g., 'legacy-mkdocs')."""
        ...

    @property
    def version(self) -> str:
        """Convention version (e.g., 'v1', '2024-01')."""
        ...

    def canonical_url(self, document: Document, ctx: UrlContext) -> str:
        """
        Generate canonical URL for a document.

        Must be deterministic: same document -> same URL.
        Must be stable: re-generating doesn't change URL.
        """
        ...
```

**Implementation: `legacy-mkdocs-v1`**

Maintains current URL rules exactly:
- Posts: `/posts/{YYYY-MM-DD}-{slug}/`
- Profiles: `/profiles/{author_id}/`
- Journals: `/journals/{window_label}/`
- Media: `/media/{uuid}.{ext}`

Nothing changes externally. Agents continue to get identical URLs.

### 2. OutputAdapter (Persistence Mechanism)

```python
class OutputAdapter(Protocol):
    """Handles document persistence at URLs defined by convention.

    Adopts a UrlConvention (shared with Core) and ensures documents
    are served at the URLs that convention generates.

    Backend-agnostic: can use filesystem, S3, DB, CMS - whatever.
    Core never sees implementation details.
    """

    @property
    def url_convention(self) -> UrlConvention:
        """
        The URL convention this format uses.

        Must match Core's convention (verified by name/version).
        """
        ...

    def serve(self, document: Document) -> None:
        """
        Ensures document is served at the URL defined by url_convention.

        Does NOT return URL (Core calculates URL independently).
        Does NOT return status (idempotency internal).

        Internally:
        - Calculates URL using self.url_convention.canonical_url()
        - Converts URL to backend-specific location (path, key, ID, etc.)
        - Persists document (write file, save to DB, upload, queue, etc.)
        - Handles idempotency, collisions, versioning internally

        Strategy (sync/async/batch/lazy) is format's choice.
        """
        ...
```

**That's it. Just 1 method + 1 property. Zero coupling to Core.**

### 3. Core Responsibilities (Perfect Separation)

```python
# Core flow - perfect separation of concerns
def publish_document(
    document: Document,
    url_convention: UrlConvention,
    output_format: OutputAdapter,
    ctx: UrlContext
) -> str:
    # Verify format uses same convention (safety check)
    assert output_format.url_convention.name == url_convention.name, \
        f"Format uses {output_format.url_convention.name}, expected {url_convention.name}"

    # 1. Core calculates URL directly from convention
    url = url_convention.canonical_url(document, ctx)

    # 2. Request format to serve document (format calculates same URL internally)
    output_format.serve(document)

    # 3. Use URL in content, cross-refs, etc.
    return url
```

**That's it. Two independent operations using shared convention.**

**Core does NOT:**
- Know if document was created or updated (format's job)
- Handle idempotency (format's job)
- Deal with collisions (format's job)
- Calculate paths (format's job)
- Know about storage (format's job)
- Ask format for URLs (calculates independently)
- Wait for persistence confirmation (fire-and-forget)

**Core ONLY:**
- Generates Documents (validation, privacy, enrichment)
- Calculates URLs from convention
- Requests serving (delegates to format)
- Uses URLs

**OutputAdapter does NOT:**
- Return URLs to Core (Core calculates independently)
- Return status (idempotency internal)
- Expose paths, IDs, or backend details

**OutputAdapter ONLY:**
- Receives documents
- Calculates URLs from same convention
- Persists documents at those URLs

## Implementation Examples

### MkDocsOutputAdapter (Filesystem)

```python
from pathlib import Path

class MkDocsOutputAdapter:
    """MkDocs format using filesystem storage."""

    def __init__(self, base_path: Path, base_url: str = ""):
        self.base_path = base_path
        self._url_convention = LegacyMkDocsUrlConvention()
        self._ctx = UrlContext(base_url=base_url, base_path=base_path)

    @property
    def url_convention(self) -> UrlConvention:
        """Returns the convention this format uses."""
        return self._url_convention

    def serve(self, document: Document) -> None:
        """
        Ensures document is served at URL defined by convention.

        Does NOT return URL (Core calculates independently).
        All persistence logic is internal.
        """
        # 1. Calculate URL using convention (same as Core)
        url = self._url_convention.canonical_url(document, self._ctx)

        # 2. Convert URL to local path (INTERNAL detail)
        path = self._url_to_path(url, document.type)

        # 3. Check if already served with same content (idempotency)
        if self._is_already_served(path, document):
            return  # No-op

        # 4. Write atomically
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self._format_content(document)
        atomic_write(path, content)

        # 5. Post-write hooks (format-specific)
        if document.type == DocumentType.PROFILE:
            self._update_authors_yml(document)

    def _url_to_path(self, url: str, doc_type: DocumentType) -> Path:
        """Convert canonical URL to filesystem path (internal)."""
        rel_url = url.removeprefix(self._ctx.base_url).strip("/")
        if doc_type in (DocumentType.POST, DocumentType.PROFILE, DocumentType.JOURNAL):
            rel_url = f"{rel_url}.md" if not rel_url.endswith(".md") else rel_url
        return self.base_path / rel_url

    def _is_already_served(self, path: Path, document: Document) -> bool:
        """Check if document is already served with same content (internal)."""
        if not path.exists():
            return False
        existing_hash = self._extract_doc_id(path)
        return existing_hash == document.document_id

    def _format_content(self, document: Document) -> str:
        """Format document with frontmatter and metadata."""
        if document.type in (DocumentType.POST, DocumentType.JOURNAL):
            frontmatter = self._generate_frontmatter(document)
            return f"{frontmatter}\n\n{document.content}"
        else:
            return f"<!-- doc_id: {document.document_id} -->\n{document.content}"
```

### HeadlessDBOutputFormat (Database)

```python
class HeadlessDBOutputFormat:
    """Database-backed output format for headless CMS."""

    def __init__(self, db_url: str, base_url: str):
        self.db = Database(db_url)
        self._url_convention = LegacyMkDocsUrlConvention()  # Or custom
        self._ctx = UrlContext(base_url=base_url)

    @property
    def url_convention(self) -> UrlConvention:
        """Returns the convention this format uses."""
        return self._url_convention

    def serve(self, document: Document) -> None:
        """
        Ensures document is served at URL defined by convention.

        Does NOT return URL (Core calculates independently).
        All persistence logic is internal.
        """
        # 1. Calculate URL using convention (same as Core)
        url = self._url_convention.canonical_url(document, self._ctx)

        # 2. Check if already exists with same content (idempotency)
        existing = self.db.query(
            "SELECT doc_id FROM documents WHERE canonical_url = ?",
            (url,)
        )

        if existing and existing[0]["doc_id"] == document.document_id:
            return  # Already served with same content

        # 3. Upsert document
        self.db.execute(
            """
            INSERT INTO documents (canonical_url, doc_id, type, content, metadata, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(canonical_url) DO UPDATE SET
                doc_id = excluded.doc_id,
                content = excluded.content,
                metadata = excluded.metadata,
                updated_at = excluded.updated_at
            """,
            (
                url,
                document.document_id,
                document.type.value,
                document.content,
                json.dumps(document.metadata),
                datetime.now()
            )
        )
```

## LegacyMkDocsUrlConvention

```python
class LegacyMkDocsUrlConvention:
    """
    Legacy MkDocs URL convention (v1).

    Maintains exact same URLs as current implementation.
    Agents continue to get identical URLs for cross-references.
    """

    @property
    def name(self) -> str:
        return "legacy-mkdocs"

    @property
    def version(self) -> str:
        return "v1"

    def canonical_url(self, document: Document, ctx: UrlContext) -> str:
        """Generate URL using legacy MkDocs rules."""
        base = ctx.base_url.rstrip("/")

        if document.type == DocumentType.POST:
            date = document.metadata.get("date", document.created_at)
            slug = self._slugify(document.metadata.get("title", "untitled"))
            return f"{base}/posts/{date.strftime('%Y-%m-%d')}-{slug}/"

        elif document.type == DocumentType.PROFILE:
            author_id = document.metadata["author_id"]
            return f"{base}/profiles/{author_id}/"

        elif document.type == DocumentType.JOURNAL:
            label = document.metadata.get("window_label", "unknown")
            safe = self._safe_label(label)
            return f"{base}/journals/{safe}/"

        elif document.type == DocumentType.ENRICHMENT_URL:
            return f"{base}/media/urls/{document.document_id}/"

        elif document.type == DocumentType.ENRICHMENT_MEDIA:
            # Use suggested_path if available, else doc_id
            filename = document.suggested_path or f"{document.document_id}.md"
            return f"{base}/media/{filename}"

        else:
            # Fallback
            return f"{base}/documents/{document.document_id}/"

    def _slugify(self, text: str) -> str:
        """Convert text to URL-safe slug."""
        # Implementation same as current
        ...

    def _safe_label(self, label: str) -> str:
        """Sanitize window label for URL."""
        # Implementation same as current
        ...
```

## Media as Documents

**No special "assets" handling.** Media is just another document type:

```python
# Media document (image, video, etc.)
media_doc = Document(
    content=b"...",  # Binary content
    type=DocumentType.MEDIA,
    metadata={"filename": "photo.jpg", "mime_type": "image/jpeg"},
    document_id=hash_of_content,
    ...
)

# Same flow as posts
url = url_convention.canonical_url(media_doc, ctx)  # /media/abc123.jpg
output_format.serve(media_doc)  # Persisted internally

# Use URL in post content
post_content = f"![Photo]({url})"
```

**Benefit**: Uniform treatment. No separate asset pipeline. Core and format both use convention.

## Testing: Conformance Kit

```python
# tests/unit/storage/test_output_format_conformance.py

def test_convention_name_and_version(output_format: OutputAdapter):
    """OutputAdapter exposes convention name and version."""
    assert output_format.url_convention.name
    assert output_format.url_convention.version
    # e.g., "legacy-mkdocs" and "v1"

def test_url_determinism(url_convention: UrlConvention, ctx: UrlContext, sample_doc: Document):
    """Same document always returns same URL from convention."""
    url1 = url_convention.canonical_url(sample_doc, ctx)
    url2 = url_convention.canonical_url(sample_doc, ctx)

    assert url1 == url2
    assert url1.startswith("http") or url1.startswith("/")

def test_idempotency(output_format: OutputAdapter, sample_doc: Document):
    """Multiple serve() calls are safe no-ops."""
    # First call
    output_format.serve(sample_doc)

    # Second call should be no-op (no error, no duplicate)
    output_format.serve(sample_doc)

    # Format-specific check that document is actually served
    convention = output_format.url_convention
    ctx = UrlContext()  # Format-specific context
    url = convention.canonical_url(sample_doc, ctx)
    assert output_format._is_served(url)  # Format implements this helper

def test_different_documents_different_urls(url_convention: UrlConvention, ctx: UrlContext):
    """Different documents get different URLs."""
    doc1 = Document(content="A", type=DocumentType.POST, metadata={"title": "A"}, ...)
    doc2 = Document(content="B", type=DocumentType.POST, metadata={"title": "B"}, ...)

    url1 = url_convention.canonical_url(doc1, ctx)
    url2 = url_convention.canonical_url(doc2, ctx)

    assert url1 != url2

def test_core_and_format_use_same_convention(
    url_convention: UrlConvention,
    output_format: OutputAdapter,
    sample_doc: Document,
    ctx: UrlContext
):
    """Core and format calculate same URL from same convention."""
    # Core calculates URL
    url_from_core = url_convention.canonical_url(sample_doc, ctx)

    # Format calculates URL (internally)
    output_format.serve(sample_doc)

    # Both should result in same URL
    url_from_format = output_format.url_convention.canonical_url(sample_doc, ctx)
    assert url_from_core == url_from_format

def test_media_documents(url_convention: UrlConvention, output_format: OutputAdapter, ctx: UrlContext):
    """Media documents work same as other documents."""
    media = Document(
        content=b"fake-image-data",
        type=DocumentType.MEDIA,
        metadata={"filename": "photo.jpg", "mime_type": "image/jpeg"},
        ...
    )

    # Core calculates URL
    url = url_convention.canonical_url(media, ctx)
    assert ".jpg" in url or "photo" in url

    # Format serves document
    output_format.serve(media)
    # No error - media treated like any other document

def test_serve_makes_document_available(output_format: OutputAdapter, sample_doc: Document):
    """serve() ensures document is available at convention URL."""
    output_format.serve(sample_doc)

    # Format-specific check that document is actually served
    # (e.g., file exists for MkDocs, DB entry exists for HeadlessDB)
    convention = output_format.url_convention
    ctx = UrlContext()  # Format-specific context
    url = convention.canonical_url(sample_doc, ctx)
    assert output_format._is_served(url)  # Format implements this helper
```

## Migration Plan

### Phase 1: Introduce Abstractions

**Files to create:**
- `src/egregora/storage/url_convention.py` - UrlConvention protocol, UrlContext
- `src/egregora/storage/output_format.py` - OutputAdapter protocol
- `src/egregora/rendering/legacy_mkdocs_url_convention.py` - LegacyMkDocsUrlConvention
- `tests/unit/storage/test_url_convention.py` - Tests for URL generation
- `tests/unit/storage/test_output_format_conformance.py` - Conformance tests

**Steps:**
1. Define `UrlConvention` protocol (with name/version properties)
2. Define `OutputAdapter` protocol (just serve() + url_convention property)
3. Implement `LegacyMkDocsUrlConvention` with current rules
4. Write conformance tests

**Deliverable:** New abstractions with tests, no integration yet.

### Phase 2: Implement MkDocsOutputAdapter

**Files to create:**
- `src/egregora/rendering/mkdocs_output_format.py` - New implementation

**Steps:**
1. Extract path logic from current `MkDocsDocumentStorage`
2. Implement `serve()` that:
   - Uses `LegacyMkDocsUrlConvention` to calculate URL internally
   - Converts URL to path
   - Handles persistence (write file, idempotency check, etc.)
   - Returns nothing (void)
3. Move format-specific logic (frontmatter, .authors.yml) into internal methods
4. Run conformance tests

**Deliverable:** Working `MkDocsOutputAdapter` passing all tests.

### Phase 3: Update Core

**Files to modify:**
- `src/egregora/agents/writer/writer_agent.py` - Use convention + serve()
- `src/egregora/cli.py` - Inject UrlConvention + OutputAdapter
- Agent tools - Use URLs from convention

**Steps:**
1. Replace storage calls with:
   ```python
   # Verify format uses expected convention
   assert output_format.url_convention.name == "legacy-mkdocs"

   # Calculate URL from convention
   url = url_convention.canonical_url(document, ctx)

   # Request serving
   output_format.serve(document)
   ```
2. Remove status handling (created/updated/noop)
3. Remove idempotency_key calculation (format's job now)
4. Update agent tools to calculate URLs from convention

**Deliverable:** Core using new architecture, perfect separation.

### Phase 4: Remove Legacy Storage

**Files to remove:**
- `src/egregora/rendering/mkdocs_documents.py` (457 lines)
- `src/egregora/storage/protocols.py` (old PostStorage, ProfileStorage, etc.)
- `src/egregora/storage/legacy_adapter.py`

**Steps:**
1. Verify all consumers migrated
2. Delete old storage classes
3. Clean up imports

**Deliverable:** Clean codebase, ~500 line reduction.

### Phase 5: Documentation

**Files to create/modify:**
- `docs/architecture/output-formats.md` - Document pattern
- `.egregora/config.yml` - Add output format config
- `CLAUDE.md` - Update architecture section

**Example config:**
```yaml
output:
  format: mkdocs              # or "db", "s3"
  base_url: ""                # For canonical URLs

  mkdocs:
    base_path: ./output

  db:
    url: "postgresql://localhost/egregora"
    base_url: "https://api.example.com"
```

**Deliverable:** Complete documentation.

## Why This Design is Superior

### 1. **Perfect Separation of Concerns**
- **UrlConvention**: URL policy (pure, deterministic, versionable)
- **OutputAdapter**: Persistence (internal, format-specific, opaque)
- **Core**: Orchestration (calculates URLs, requests serving, uses URLs)
- Core and Format both use convention, but independently
- No coupling between Core and Format - only via shared convention

### 2. **Absolute Minimum Interface**
- Core: **2 independent operations** (calculate URL, request serving)
- OutputAdapter: **1 method** (`serve`) + **1 property** (`url_convention`)
- No publish(), no url_for(), no status, no options, no result objects
- ~80% less interface surface area than original proposal

### 3. **Backend-Agnostic (For Real)**
- OutputAdapter can use ANY backend
- Core never sees paths, storage, or implementation
- `ensure_served()` does whatever's needed internally

### 4. **Idempotency Where It Belongs**
- Format decides how to handle duplicates
- Core doesn't track status
- Retry-safe by design

### 5. **Media as First-Class**
- Same flow for posts and media
- No separate asset pipeline
- Uniform Document treatment

### 6. **Easy Migration**
- `LegacyMkDocsUrlConvention` maintains exact current URLs
- No external changes - only internal simplification
- Incremental: introduce, migrate, remove

### 7. **Testability**
- Mock `url_for()` for tests (no I/O)
- Conformance tests ensure any format works
- URL generation testable independently

## Comparison: Before vs After

### Before (Current - 457 lines)

```python
# Complex storage interface
storage = MkDocsDocumentStorage(base_path)
path = storage.add(document)  # Returns path
# Core knows about paths, collisions, status

# 6 type-specific methods
_determine_post_path()
_determine_profile_path()
_determine_journal_path()
...

# 3-layer collision detection
# In-memory index
# Format-specific logic scattered
```

### After (New - ~200 lines)

```python
# Perfect separation - Core and Format both use convention
url_convention = LegacyMkDocsUrlConvention()
output_format = MkDocsOutputAdapter(base_path)

# Verify compatibility
assert output_format.url_convention.name == url_convention.name

# Core calculates URL from convention
url = url_convention.canonical_url(document, ctx)

# Format serves document (calculates same URL internally)
output_format.serve(document)

# That's it. Core never sees paths, status, or persistence.
# Format never returns URLs to Core.
```

**Reduction: ~250 lines + perfect decoupling (Core and Format independent).**

## Success Criteria

- [ ] `UrlConvention` protocol defined (with name/version properties)
- [ ] `OutputAdapter` protocol with **only `serve()` + `url_convention` property**
- [ ] `LegacyMkDocsUrlConvention` maintains exact current URLs
- [ ] `MkDocsOutputAdapter` passes conformance tests
- [ ] Core calculates URLs **directly from convention** (not from format)
- [ ] Core uses **only `url_convention.canonical_url()` + `output_format.serve()`**
- [ ] Convention compatibility check at startup
- [ ] Legacy `MkDocsDocumentStorage` removed (457 lines)
- [ ] All tests pass (unit, integration, E2E)
- [ ] No URL changes (agents continue to work)
- [ ] Documentation complete

## References

- Current implementation: `src/egregora/rendering/mkdocs_documents.py` (457 lines)
- Document abstraction: `src/egregora/core/document.py`
- CLAUDE.md: Architecture section
