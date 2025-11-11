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
2. **OutputFormat** - Adopts a convention, ensures documents are served at those URLs
3. **Core** - Asks for URLs, requests availability, uses URLs

**Key insight**: Separate URL generation (policy) from document persistence (mechanism).

## Minimal Interface

### 1. UrlConvention (URL Policy)

```python
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class UrlContext:
    """Context for URL generation."""
    base_url: str = ""
    locale: str | None = None

class UrlConvention(Protocol):
    """Defines how URLs are generated for documents.

    Pure function: same document -> same URL (deterministic, stable).
    No I/O, no side effects - just URL calculation.
    """

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

### 2. OutputFormat (Persistence Mechanism)

```python
class OutputFormat(Protocol):
    """Handles document persistence and serves documents at URLs.

    Adopts a UrlConvention and guarantees documents are available
    at the URLs that convention generates.

    Backend-agnostic: can use filesystem, S3, DB, CMS - whatever.
    Core never sees implementation details.
    """

    @property
    def url_convention(self) -> UrlConvention:
        """The URL convention this format uses."""
        ...

    def url_for(self, document: Document) -> str:
        """
        Returns the canonical URL for this document.

        GUARANTEES: The returned URL will be valid/servable.

        Internally does whatever is necessary to make that guarantee:
        - Write file to disk (MkDocs)
        - Save to database (HeadlessDB)
        - Upload to S3 (S3Storage)
        - Queue for batch processing
        - Post to CMS API (HeadlessCMS)
        - Or any other strategy

        Idempotency, collision handling, versioning - all INTERNAL.
        Core never knows HOW it's done, only gets the URL.

        The format decides when/how to persist (sync, async, batch, lazy).
        """
        ...
```

**That's it. Just 1 method + 1 property. Absolute minimum interface.**

### 3. Core Responsibilities (Absolute Minimum)

```python
# Core flow - cannot be simpler
def publish_document(document: Document, output_format: OutputFormat) -> str:
    # Get URL (format handles persistence internally)
    url = output_format.url_for(document)

    # Use URL in content, cross-refs, etc.
    return url
```

**That's it. One method call.**

**Core does NOT:**
- Know if document was created or updated
- Handle idempotency (format's job)
- Deal with collisions (format's job)
- Calculate paths (format's job)
- Know about storage (format's job)
- Trigger persistence (format's job)
- Wait for writes (format's job)

**Core ONLY:**
- Generates Documents (validation, privacy, enrichment)
- Asks for URLs
- Uses URLs

## Implementation Examples

### MkDocsOutputFormat (Filesystem)

```python
from pathlib import Path

class MkDocsOutputFormat:
    """MkDocs format using filesystem storage."""

    def __init__(self, base_path: Path, base_url: str = ""):
        self.base_path = base_path
        self._url_convention = LegacyMkDocsUrlConvention()
        self._ctx = UrlContext(base_url=base_url)

    @property
    def url_convention(self) -> UrlConvention:
        return self._url_convention

    def url_for(self, document: Document) -> str:
        """
        Get canonical URL and ensure document is served.

        All persistence logic happens here, internally.
        Core never sees how it's done.
        """
        # 1. Calculate URL using convention
        url = self._url_convention.canonical_url(document, self._ctx)

        # 2. Ensure document is served at that URL (INTERNAL)
        self._ensure_served_internal(url, document)

        # 3. Return URL (guaranteed valid)
        return url

    def _ensure_served_internal(self, url: str, document: Document) -> None:
        """Internal persistence logic - core never calls this."""
        # Convert URL to local path
        path = self._url_to_path(url, document.type)

        # Check if already served with same content (idempotency)
        if self._is_already_served(path, document):
            return  # No-op

        # Write atomically
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self._format_content(document)
        atomic_write(path, content)

        # Post-write hooks (format-specific)
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
        return self._url_convention

    def url_for(self, document: Document) -> str:
        """Get canonical URL and persist to database."""
        # 1. Calculate URL using convention
        url = self._url_convention.canonical_url(document, self._ctx)

        # 2. Persist to database (INTERNAL - core never sees this)
        self._persist_internal(url, document)

        # 3. Return URL (guaranteed valid)
        return url

    def _persist_internal(self, url: str, document: Document) -> None:
        """Internal persistence logic - core never calls this."""
        # Check if already exists with same content (idempotency)
        existing = self.db.query(
            "SELECT doc_id FROM documents WHERE canonical_url = ?",
            (url,)
        )

        if existing and existing[0]["doc_id"] == document.document_id:
            return  # Already served with same content

        # Upsert document
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

# Same flow as posts - just get URL
url = output_format.url_for(media_doc)  # /media/abc123.jpg (persisted internally)

# Use URL in post content
post_content = f"![Photo]({url})"
```

**Benefit**: Uniform treatment. No separate asset pipeline. Single method call.

## Testing: Conformance Kit

```python
# tests/unit/storage/test_output_format_conformance.py

def test_url_determinism(output_format: OutputFormat, sample_doc: Document):
    """Same document always returns same URL."""
    url1 = output_format.url_for(sample_doc)
    url2 = output_format.url_for(sample_doc)

    assert url1 == url2
    assert url1.startswith("http") or url1.startswith("/")

def test_idempotency(output_format: OutputFormat, sample_doc: Document):
    """Multiple url_for calls are safe (idempotent persistence)."""
    # First call
    url1 = output_format.url_for(sample_doc)

    # Second call should return same URL (no error, no duplicate)
    url2 = output_format.url_for(sample_doc)

    assert url1 == url2

def test_url_stability(output_format: OutputFormat, sample_doc: Document):
    """URL doesn't change across multiple calls."""
    url_before = output_format.url_for(sample_doc)
    url_after = output_format.url_for(sample_doc)

    assert url_after == url_before

def test_different_documents_different_urls(output_format: OutputFormat):
    """Different documents get different URLs."""
    doc1 = Document(content="A", type=DocumentType.POST, metadata={"title": "A"}, ...)
    doc2 = Document(content="B", type=DocumentType.POST, metadata={"title": "B"}, ...)

    url1 = output_format.url_for(doc1)
    url2 = output_format.url_for(doc2)

    assert url1 != url2

def test_url_convention_consistency(output_format: OutputFormat, sample_doc: Document):
    """url_for() uses the declared convention."""
    url_from_format = output_format.url_for(sample_doc)

    # Convention should generate same URL
    url_from_convention = output_format.url_convention.canonical_url(
        sample_doc,
        UrlContext(base_url="")  # Match format's context
    )

    # URLs should match (accounting for base_url differences)
    assert url_from_convention in url_from_format

def test_media_documents(output_format: OutputFormat):
    """Media documents work same as other documents."""
    media = Document(
        content=b"fake-image-data",
        type=DocumentType.MEDIA,
        metadata={"filename": "photo.jpg", "mime_type": "image/jpeg"},
        ...
    )

    url = output_format.url_for(media)
    assert ".jpg" in url or "photo" in url
    # No error - media treated like any other document

def test_url_validity_guarantee(output_format: OutputFormat, sample_doc: Document):
    """url_for() guarantees URL will be valid/servable."""
    url = output_format.url_for(sample_doc)

    # Format-specific check that document is actually served
    # (e.g., file exists for MkDocs, DB entry exists for HeadlessDB)
    assert output_format._is_served(url)  # Format implements this helper
```

## Migration Plan

### Phase 1: Introduce Abstractions

**Files to create:**
- `src/egregora/storage/url_convention.py` - UrlConvention protocol, UrlContext
- `src/egregora/storage/output_format.py` - OutputFormat protocol
- `src/egregora/rendering/legacy_mkdocs_url_convention.py` - LegacyMkDocsUrlConvention
- `tests/unit/storage/test_url_convention.py` - Tests for URL generation
- `tests/unit/storage/test_output_format_conformance.py` - Conformance tests

**Steps:**
1. Define `UrlConvention` protocol
2. Define `OutputFormat` protocol (just url_for + url_convention property)
3. Implement `LegacyMkDocsUrlConvention` with current rules
4. Write conformance tests

**Deliverable:** New abstractions with tests, no integration yet.

### Phase 2: Implement MkDocsOutputFormat

**Files to create:**
- `src/egregora/rendering/mkdocs_output_format.py` - New implementation

**Steps:**
1. Extract path logic from current `MkDocsDocumentStorage`
2. Implement `url_for()` that:
   - Uses `LegacyMkDocsUrlConvention` to calculate URL
   - Internally handles persistence (write file, idempotency check, etc.)
   - Returns URL
3. Move format-specific logic (frontmatter, .authors.yml) into internal methods
4. Run conformance tests

**Deliverable:** Working `MkDocsOutputFormat` passing all tests.

### Phase 3: Update Core

**Files to modify:**
- `src/egregora/agents/writer/writer_agent.py` - Use url_for only
- `src/egregora/cli.py` - Inject OutputFormat
- Agent tools - Use URLs from url_for()

**Steps:**
1. Replace storage calls with:
   ```python
   url = output_format.url_for(document)
   ```
2. Remove status handling (created/updated/noop)
3. Remove idempotency_key calculation (format's job now)
4. Update agent tools to use URLs

**Deliverable:** Core using new OutputFormat, radically simpler code.

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

### 1. **Absolute Minimum Interface**
- Core: **1 method call** (`url_for`)
- No publish(), no ensure_served(), no status, no options, no result objects
- ~75% less interface surface area than original proposal

### 2. **Perfect Separation**
- **UrlConvention**: URL policy (pure, testable, swappable)
- **OutputFormat**: Persistence (internal, opaque to core)
- **Core**: Orchestration (asks, uses - that's it)

### 3. **Backend-Agnostic (For Real)**
- OutputFormat can use ANY backend
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
# Absolute minimum interface
output_format = MkDocsOutputFormat(base_path)

url = output_format.url_for(document)        # Get URL (persistence internal)

# That's it. Core never sees paths, status, or persistence.
# All complexity internal to format.
```

**Reduction: ~250 lines + radical conceptual simplification (1 method call).**

## Success Criteria

- [ ] `UrlConvention` protocol defined
- [ ] `OutputFormat` protocol with **only `url_for()` + `url_convention` property**
- [ ] `LegacyMkDocsUrlConvention` maintains exact current URLs
- [ ] `MkDocsOutputFormat` passes conformance tests
- [ ] Core uses **only `url_for()`** (no status handling, no ensure_served)
- [ ] Legacy `MkDocsDocumentStorage` removed (457 lines)
- [ ] All tests pass (unit, integration, E2E)
- [ ] No URL changes (agents continue to work)
- [ ] Documentation complete

## References

- Current implementation: `src/egregora/rendering/mkdocs_documents.py` (457 lines)
- Document abstraction: `src/egregora/core/document.py`
- CLAUDE.md: Architecture section
