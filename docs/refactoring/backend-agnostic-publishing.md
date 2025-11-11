# Refactor: Backend-Agnostic Document Publishing

## Problem

Current storage is **tightly coupled to filesystem/MkDocs**:

- `MkDocsDocumentStorage` (457 lines) knows about paths, directories, frontmatter, `.authors.yml`
- 6 type-specific path methods, 3-layer collision detection
- **No abstraction for URLs** - paths are exposed, not permalinks
- **Cannot support alternative backends** - DB, S3, headless CMS require rewrite
- **Assets are second-class** - handled separately from documents
- **No idempotency contract** - retries may duplicate or fail

**Core insight**: The core should generate domain Documents, and the OutputFormat should be sovereign over persistence, URL generation, and publication.

## Solution

### Architecture Principles

1. **Clear Boundary**
   - **Core**: validates, applies privacy gate, enriches, delivers Document + assets for publication
   - **OutputFormat**: decides storage, performs I/O, defines/maintains URL policy, returns publication result

2. **URL is Law**
   - Permalink is defined by OutputFormat
   - Core never calculates paths or derives URLs
   - Core displays what OutputFormat returns (`canonical_url`)

3. **Backend-Agnostic**
   - OutputFormat can use filesystem, S3, DB, headless CMS
   - Core has no dependency on local paths
   - For file-based (MkDocs): uses paths internally, returns URLs
   - For DB-based: stores in DB, returns URLs served by app/renderer

4. **Idempotency by Key**
   - Core provides `idempotency_key` (hash of normalized Document + assets) on every publish
   - OutputFormat treats retries as safe no-ops when content hasn't changed

5. **Stable Permalinks**
   - Permalink policy must be **deterministic** and **stable**
   - Based on slug+date or doc_id (not random)
   - Re-publishing doesn't change permalink, unless policy explicitly changed

### OutputFormat Contract

```python
from typing import Protocol, TypedDict, Literal
from dataclasses import dataclass, field
from datetime import datetime

class PublishOptions(TypedDict, total=False):
    """Options for document publication."""
    collision: Literal["suffix", "replace", "fail"]  # Internal format policy
    visibility: Literal["public", "private", "draft"]
    dry_run: bool

@dataclass(frozen=True)
class PublishResult:
    """Result of publishing a document."""
    status: Literal["created", "updated", "noop"]
    canonical_url: str              # Public permalink to display to user
    public_id: str                  # Stable resource ID in this format
    etag: str | None                # Hash/version for cache/consistency
    modified_at: datetime
    warnings: list[str] = field(default_factory=list)
    asset_urls: dict[str, str] = field(default_factory=dict)  # logical name -> public URL

class OutputFormat(Protocol):
    """Protocol for output format implementations.

    Handles document persistence, URL generation, and asset management.
    Backend-agnostic: can use filesystem, S3, DB, CMS, etc.
    """

    def publish(
        self,
        document: "Document",
        *,
        assets: dict[str, bytes] | None = None,  # logical key -> content
        idempotency_key: str,
        options: PublishOptions | None = None,
    ) -> PublishResult:
        """
        Publish a document with optional assets.

        Must be idempotent: same idempotency_key -> same public_id/canonical_url.
        Returns status reflecting actual action (created/updated/noop).
        """
        ...

    def resolve_url(
        self,
        *,
        public_id: str | None = None,
        doc_ref: str | None = None
    ) -> str:
        """
        Resolve a document reference to its canonical URL.

        Args:
            public_id: Stable resource ID from PublishResult
            doc_ref: Alternative reference (slug, path, etc.)

        Returns canonical URL for the document.
        """
        ...

    def unpublish(
        self,
        *,
        public_id: str | None = None,
        doc_ref: str | None = None
    ) -> bool:
        """
        Remove or mark document as private.

        Returns True if unpublished, False if not found.
        """
        ...

    def capabilities(self) -> set[str]:
        """
        Declare format capabilities.

        Examples: {"assets", "transactions", "batch", "search", "previews"}
        """
        ...

    # Optional: transactional support
    def begin(self) -> None:
        """Begin transaction (if supported)."""
        ...

    def commit(self) -> None:
        """Commit transaction (if supported)."""
        ...

    def rollback(self) -> None:
        """Rollback transaction (if supported)."""
        ...
```

### Mandatory Invariants

1. **Determinism**: Same `Document` + `idempotency_key` ⇒ same `public_id`/`etag`/`canonical_url` (unless content actually changed)
2. **Security**: Sanitize asset names, prevent path traversal, enforce size/MIME limits
3. **Consistency**: `status` reflects real action (created/updated/noop), `canonical_url` always present

### Canonical URL Policy (Default)

To enable agents to reference documents correctly, we define a **standard URL scheme** that formats can override if needed:

```python
# Posts: /posts/{YYYY-MM-DD}-{slug}/
# Profiles: /profiles/{author_id}/
# Journals: /journals/{window_label}/
# URL enrichments: /media/urls/{doc_id}/
# Media enrichments: /media/{filename}

def canonical_url_for(document: Document, base_url: str = "") -> str:
    """
    Generate canonical URL using standard scheme.

    Formats can override this, but must maintain stability (same doc -> same URL).
    """
    if document.type == DocumentType.POST:
        date = document.metadata.get("date", document.created_at)
        slug = slugify(document.metadata.get("title", "untitled"))
        return f"{base_url}/posts/{date.strftime('%Y-%m-%d')}-{slug}/"

    elif document.type == DocumentType.PROFILE:
        author_id = document.metadata["author_id"]
        return f"{base_url}/profiles/{author_id}/"

    elif document.type == DocumentType.JOURNAL:
        label = document.metadata.get("window_label", "unknown")
        return f"{base_url}/journals/{safe_label(label)}/"

    elif document.type == DocumentType.ENRICHMENT_URL:
        return f"{base_url}/media/urls/{document.document_id}/"

    elif document.type == DocumentType.ENRICHMENT_MEDIA:
        filename = document.suggested_path or f"{document.document_id}.md"
        return f"{base_url}/media/{filename}"

    else:
        # Fallback: use document ID
        return f"{base_url}/documents/{document.document_id}/"
```

**Why this matters:**
- Agents need stable URLs to reference documents in content
- Cross-references break if URLs change between formats
- Standard scheme allows format-agnostic reasoning about URLs

**Format customization:**
- Formats can override URL generation (e.g., `/blog/` instead of `/posts/`)
- Must document differences in `.egregora/config.yml`
- Must maintain determinism and stability

## Core Responsibilities

### Before Publishing

1. **Validate** Document (schema, required fields)
2. **Apply privacy gate** + PII cleanup
3. **Package assets** with logical names (e.g., `cover.jpg`, `avatar.png`)
4. **Calculate idempotency_key** (stable hash of normalized doc + assets)

### Publishing

```python
# Core publishing flow
result = output_format.publish(
    document,
    assets=assets,
    idempotency_key=idempotency_key,
    options={"collision": "suffix", "visibility": "public"}
)

# Store mapping (optional cache for performance)
doc_cache[document.document_id] = {
    "public_id": result.public_id,
    "canonical_url": result.canonical_url,
    "etag": result.etag
}
```

### After Publishing

1. Display/return `canonical_url` to user/agent
2. If format declares `invalidation` capability, call cache/CDN hooks

## Media/Assets Policy

- **Deduplication by hash** (if format supports)
- **Collision strategy** configurable via `PublishOptions.collision`
- **Typing**: `assets` as `dict[str, bytes]`
- **Output**: Format returns `asset_urls` mapping logical name -> public URL

## Example Implementations

### MkDocsOutputFormat (Filesystem)

```python
class MkDocsOutputFormat:
    """MkDocs-specific output format using filesystem."""

    def __init__(self, base_path: Path, base_url: str = ""):
        self.base_path = base_path
        self.base_url = base_url
        self.posts_dir = base_path / "posts"
        self.profiles_dir = base_path / "profiles"
        self.media_dir = base_path / "docs" / "media"

    def publish(
        self,
        document: Document,
        *,
        assets: dict[str, bytes] | None = None,
        idempotency_key: str,
        options: PublishOptions | None = None
    ) -> PublishResult:
        options = options or {}

        # 1. Determine file path (internal detail)
        path = self._resolve_path(document)

        # 2. Check idempotency
        if path.exists():
            existing_etag = self._read_etag(path)
            if existing_etag == idempotency_key:
                # Same content - no-op
                return PublishResult(
                    status="noop",
                    canonical_url=self._path_to_url(path, document.type),
                    public_id=str(path.relative_to(self.base_path)),
                    etag=idempotency_key,
                    modified_at=datetime.fromtimestamp(path.stat().st_mtime)
                )

        # 3. Handle collision if needed
        if path.exists() and options.get("collision") == "suffix":
            path = self._add_suffix(path)

        # 4. Write document
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self._format_content(document, idempotency_key)
        path.write_text(content)

        # 5. Write assets
        asset_urls = {}
        if assets:
            for name, data in assets.items():
                asset_path = self._write_asset(name, data, document)
                asset_urls[name] = self._path_to_url(asset_path, None)

        # 6. Post-write hooks
        if document.type == DocumentType.PROFILE:
            self._update_authors_yml(document)

        status = "created" if not path.exists() else "updated"

        return PublishResult(
            status=status,
            canonical_url=self._path_to_url(path, document.type),
            public_id=str(path.relative_to(self.base_path)),
            etag=idempotency_key,
            modified_at=datetime.now(),
            asset_urls=asset_urls
        )

    def _resolve_path(self, document: Document) -> Path:
        """Determine filesystem path (internal to MkDocs format)."""
        if document.type == DocumentType.POST:
            date = document.metadata.get("date", document.created_at)
            slug = self._slugify(document.metadata.get("title", "untitled"))
            return self.posts_dir / f"{date.strftime('%Y-%m-%d')}-{slug}.md"

        elif document.type == DocumentType.PROFILE:
            author_id = document.metadata["author_id"]
            return self.profiles_dir / f"{author_id}.md"

        elif document.type == DocumentType.JOURNAL:
            label = document.metadata.get("window_label", "unknown")
            return self.posts_dir / "journal" / f"journal_{self._safe_label(label)}.md"

        elif document.type == DocumentType.ENRICHMENT_URL:
            return self.media_dir / "urls" / f"{document.document_id}.md"

        elif document.type == DocumentType.ENRICHMENT_MEDIA:
            filename = document.suggested_path or f"{document.document_id}.md"
            return self.media_dir / filename

        else:
            raise ValueError(f"Unknown document type: {document.type}")

    def _path_to_url(self, path: Path, doc_type: DocumentType | None) -> str:
        """Convert filesystem path to canonical URL."""
        rel_path = path.relative_to(self.base_path)
        # Remove .md extension, convert to URL path
        url_path = str(rel_path).replace("\\", "/").removesuffix(".md")
        return f"{self.base_url}/{url_path}/"

    def _format_content(self, document: Document, etag: str) -> str:
        """Format document content with frontmatter and etag."""
        if document.type in (DocumentType.POST, DocumentType.JOURNAL):
            frontmatter = self._generate_frontmatter(document, etag)
            return f"{frontmatter}\n\n{document.content}"
        else:
            # Embed etag in HTML comment for idempotency checking
            return f"<!-- etag: {etag} -->\n{document.content}"

    def resolve_url(self, *, public_id: str | None = None, doc_ref: str | None = None) -> str:
        """Resolve to canonical URL."""
        if public_id:
            # public_id is relative path
            path = self.base_path / public_id
            # Determine doc type from path (heuristic)
            if path.parent == self.posts_dir:
                doc_type = DocumentType.POST
            elif path.parent == self.profiles_dir:
                doc_type = DocumentType.PROFILE
            else:
                doc_type = None
            return self._path_to_url(path, doc_type)

        raise ValueError("Must provide public_id or doc_ref")

    def unpublish(self, *, public_id: str | None = None, doc_ref: str | None = None) -> bool:
        """Remove document file."""
        if public_id:
            path = self.base_path / public_id
            if path.exists():
                path.unlink()
                return True
        return False

    def capabilities(self) -> set[str]:
        return {"assets", "frontmatter"}
```

### HeadlessDBOutputFormat (Database)

```python
class HeadlessDBOutputFormat:
    """Database-backed output format for headless CMS."""

    def __init__(self, db_url: str, base_url: str):
        self.db = Database(db_url)
        self.base_url = base_url

    def publish(
        self,
        document: Document,
        *,
        assets: dict[str, bytes] | None = None,
        idempotency_key: str,
        options: PublishOptions | None = None
    ) -> PublishResult:
        # Check if document exists by idempotency_key
        existing = self.db.query(
            "SELECT * FROM documents WHERE idempotency_key = ?",
            (idempotency_key,)
        )

        if existing:
            # Same content - no-op
            row = existing[0]
            return PublishResult(
                status="noop",
                canonical_url=row["canonical_url"],
                public_id=row["public_id"],
                etag=row["etag"],
                modified_at=row["modified_at"]
            )

        # Generate stable public_id from document
        public_id = self._generate_public_id(document)
        canonical_url = canonical_url_for(document, self.base_url)

        # Check if public_id exists (update case)
        existing_by_id = self.db.query(
            "SELECT * FROM documents WHERE public_id = ?",
            (public_id,)
        )

        status = "updated" if existing_by_id else "created"

        # Store document
        self.db.execute(
            """
            INSERT OR REPLACE INTO documents
            (public_id, document_id, type, content, metadata, idempotency_key, etag, canonical_url, modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                public_id,
                document.document_id,
                document.type.value,
                document.content,
                json.dumps(document.metadata),
                idempotency_key,
                idempotency_key,  # etag = idempotency_key
                canonical_url,
                datetime.now()
            )
        )

        # Store assets
        asset_urls = {}
        if assets:
            for name, data in assets.items():
                asset_id = f"{public_id}/{name}"
                self.db.execute(
                    "INSERT OR REPLACE INTO assets (asset_id, document_id, name, data) VALUES (?, ?, ?, ?)",
                    (asset_id, public_id, name, data)
                )
                asset_urls[name] = f"{self.base_url}/assets/{asset_id}"

        return PublishResult(
            status=status,
            canonical_url=canonical_url,
            public_id=public_id,
            etag=idempotency_key,
            modified_at=datetime.now(),
            asset_urls=asset_urls
        )

    def _generate_public_id(self, document: Document) -> str:
        """Generate stable public ID from document metadata."""
        if document.type == DocumentType.POST:
            date = document.metadata.get("date", document.created_at)
            slug = slugify(document.metadata.get("title", "untitled"))
            return f"posts/{date.strftime('%Y-%m-%d')}-{slug}"

        elif document.type == DocumentType.PROFILE:
            return f"profiles/{document.metadata['author_id']}"

        else:
            return f"documents/{document.document_id}"

    def resolve_url(self, *, public_id: str | None = None, doc_ref: str | None = None) -> str:
        """Resolve to canonical URL."""
        if public_id:
            row = self.db.query("SELECT canonical_url FROM documents WHERE public_id = ?", (public_id,))
            if row:
                return row[0]["canonical_url"]

        raise ValueError("Document not found")

    def unpublish(self, *, public_id: str | None = None, doc_ref: str | None = None) -> bool:
        """Mark document as private or delete."""
        if public_id:
            self.db.execute("DELETE FROM documents WHERE public_id = ?", (public_id,))
            return True
        return False

    def capabilities(self) -> set[str]:
        return {"assets", "transactions", "search", "batch"}
```

## Testing: Test Compatibility Kit (TCK)

Create a conformance test suite that any `OutputFormat` implementation must pass:

```python
# tests/unit/storage/test_output_format_tck.py

def test_idempotency(format: OutputFormat, sample_document: Document):
    """Two publishes with same idempotency_key -> noop on second."""
    key = "test-key-123"

    result1 = format.publish(sample_document, idempotency_key=key)
    assert result1.status in ("created", "updated")

    result2 = format.publish(sample_document, idempotency_key=key)
    assert result2.status == "noop"
    assert result2.public_id == result1.public_id
    assert result2.canonical_url == result1.canonical_url

def test_permalink_stability(format: OutputFormat, sample_document: Document):
    """Canonical URL doesn't change on update without key/policy change."""
    result1 = format.publish(sample_document, idempotency_key="key1")
    url1 = result1.canonical_url

    # Update with different content
    updated_doc = sample_document.with_metadata({"title": "Updated Title"})
    result2 = format.publish(updated_doc, idempotency_key="key2")
    url2 = result2.canonical_url

    # URL should be stable (same public_id)
    assert result2.public_id == result1.public_id
    # URL may change if slug changed, but public_id must be resolvable
    resolved = format.resolve_url(public_id=result2.public_id)
    assert resolved == url2

def test_assets(format: OutputFormat, sample_document: Document):
    """Assets upload and return valid URLs."""
    if "assets" not in format.capabilities():
        pytest.skip("Format doesn't support assets")

    assets = {
        "cover.jpg": b"fake-image-data",
        "avatar.png": b"fake-avatar-data"
    }

    result = format.publish(sample_document, assets=assets, idempotency_key="key1")

    assert "cover.jpg" in result.asset_urls
    assert "avatar.png" in result.asset_urls
    assert result.asset_urls["cover.jpg"].startswith("http")

def test_malicious_asset_names(format: OutputFormat, sample_document: Document):
    """Reject path traversal and dangerous filenames."""
    if "assets" not in format.capabilities():
        pytest.skip("Format doesn't support assets")

    malicious_assets = {
        "../../../etc/passwd": b"data",
        "..\\..\\windows\\system32": b"data",
        "name<script>alert(1)</script>.jpg": b"data"
    }

    with pytest.raises((ValueError, SecurityError)):
        format.publish(sample_document, assets=malicious_assets, idempotency_key="key1")

def test_unpublish(format: OutputFormat, sample_document: Document):
    """Unpublish removes public access."""
    result = format.publish(sample_document, idempotency_key="key1")

    success = format.unpublish(public_id=result.public_id)
    assert success

    # Should not be resolvable anymore (or return 404/private)
    with pytest.raises((ValueError, NotFoundError)):
        format.resolve_url(public_id=result.public_id)

def test_transactions(format: OutputFormat, sample_documents: list[Document]):
    """Rollback prevents all items from being visible."""
    if "transactions" not in format.capabilities():
        pytest.skip("Format doesn't support transactions")

    format.begin()

    results = []
    for doc in sample_documents:
        result = format.publish(doc, idempotency_key=f"key-{doc.document_id}")
        results.append(result)

    format.rollback()

    # None should be visible
    for result in results:
        with pytest.raises((ValueError, NotFoundError)):
            format.resolve_url(public_id=result.public_id)

def test_dry_run(format: OutputFormat, sample_document: Document):
    """Dry run produces preview without I/O."""
    if "previews" not in format.capabilities():
        pytest.skip("Format doesn't support dry-run")

    result = format.publish(
        sample_document,
        idempotency_key="key1",
        options={"dry_run": True}
    )

    # Should return valid result
    assert result.canonical_url
    assert result.public_id

    # But document shouldn't exist
    with pytest.raises((ValueError, NotFoundError)):
        format.resolve_url(public_id=result.public_id)
```

## Migration Plan

### Phase 1: Introduce OutputFormat Protocol (No Breaking Changes)

**Files to create:**
- `src/egregora/storage/output_format.py` - Protocol, PublishOptions, PublishResult
- `src/egregora/storage/canonical_urls.py` - Default URL policy
- `tests/unit/storage/test_output_format_tck.py` - TCK tests

**Steps:**
1. Define `OutputFormat` protocol with `publish()`, `resolve_url()`, `unpublish()`, `capabilities()`
2. Define `PublishOptions` and `PublishResult` dataclasses
3. Implement `canonical_url_for()` default URL scheme
4. Create TCK test suite

**Deliverable:** New abstractions with tests, no integration yet.

### Phase 2: Implement MkDocsOutputFormat

**Files to create:**
- `src/egregora/rendering/mkdocs_output_format.py` - New implementation

**Steps:**
1. Extract path logic from current `MkDocsDocumentStorage`
2. Implement `publish()` with idempotency checking
3. Implement `resolve_url()` for URL resolution
4. Implement `_format_content()` with etag embedding
5. Handle assets in `publish()`
6. Run TCK tests against `MkDocsOutputFormat`

**Deliverable:** Working `MkDocsOutputFormat` passing all TCK tests.

### Phase 3: Update Core Publishing

**Files to modify:**
- `src/egregora/agents/writer/writer_agent.py` - Use `publish()` instead of storage
- `src/egregora/cli.py` - Inject OutputFormat
- Agent tools - Use `canonical_url` from PublishResult

**Steps:**
1. Update writer agent to call `output_format.publish()`
2. Calculate `idempotency_key` before publishing
3. Store `canonical_url` from result
4. Update agent tools to use URLs (not paths)
5. Remove old storage calls

**Deliverable:** Core using new OutputFormat, returning URLs.

### Phase 4: Remove Legacy Storage

**Files to modify:**
- `src/egregora/rendering/mkdocs_documents.py` - Delete or mark deprecated
- `src/egregora/storage/__init__.py` - Remove old protocols

**Steps:**
1. Verify all consumers migrated to OutputFormat
2. Remove `MkDocsDocumentStorage` (old 457-line class)
3. Remove `PostStorage`, `ProfileStorage`, etc. protocols
4. Remove `LegacyStorageAdapter`
5. Clean up imports

**Deliverable:** Clean codebase with only OutputFormat abstraction.

### Phase 5: Documentation & Config

**Files to create/modify:**
- `docs/architecture/output-formats.md` - Document OutputFormat pattern
- `.egregora/config.yml` - Add output format configuration
- `CLAUDE.md` - Update storage guidance

**Example config:**
```yaml
output:
  format: mkdocs                    # or "db", "s3", "custom"
  base_url: "https://example.com"  # For canonical URLs

  # Format-specific options
  mkdocs:
    base_path: ./output
    collision: suffix               # "suffix", "replace", "fail"

  db:
    url: "postgresql://localhost/egregora"
    base_url: "https://api.example.com"
```

**Deliverable:** Documented pattern with examples.

## Observability

- Core injects `trace_id` in publishing context
- OutputFormat propagates in logs/telemetry
- **Metrics**:
  - `publish_total{status,format}` - Publications by status
  - `publish_latency_ms{format}` - Latency per format
  - `asset_bytes_total{format}` - Asset upload volume

## Benefits

### 1. **Backend Flexibility**
- Swap filesystem for DB, S3, headless CMS without changing core
- Single format at a time (simplicity), but architecture supports multiple

### 2. **URL-First Design**
- URLs are first-class citizens (not paths)
- Agents can reference documents by canonical URL
- Cross-references work across backends

### 3. **Idempotency Built-In**
- Retry-safe publishing via `idempotency_key`
- Status accurately reflects action (created/updated/noop)

### 4. **Assets Integrated**
- Assets handled alongside documents
- Logical names map to public URLs
- Deduplication and collision handling

### 5. **Testability**
- TCK ensures conformance for any format
- Mock OutputFormat for core tests
- Each format tested independently

### 6. **Evolution**
- Add capabilities (search, previews, batch) without breaking core
- New document types only affect `publish()` implementation
- Format-specific features isolated

### 7. **Simplification**
- Core shrinks: no path logic, collision handling, or format details
- OutputFormat owns complexity appropriate to its backend
- Clear separation of concerns

## Future Extensions

Once refactored, we can:

1. **Multiple formats** (when needed) - publish to MkDocs + DB simultaneously
2. **Custom formats** - users inject custom OutputFormat implementations
3. **Format migration** - job to re-publish from one format to another
4. **Preview/staging** - dry-run mode for preview before publish
5. **Batch publishing** - transactional publish of multiple documents
6. **CDN integration** - invalidation capability for cache busting

## Success Criteria

- [ ] `OutputFormat` protocol defined with `publish()`, `resolve_url()`, `unpublish()`
- [ ] `PublishResult` includes `canonical_url`, `public_id`, `etag`, `status`
- [ ] Canonical URL policy defined for all document types
- [ ] TCK test suite passes for `MkDocsOutputFormat`
- [ ] Core uses `publish()` and returns URLs (not paths)
- [ ] Legacy `MkDocsDocumentStorage` (457 lines) removed
- [ ] All tests pass (unit, integration, E2E)
- [ ] No regressions in generated MkDocs sites
- [ ] Documentation complete

## References

- Current implementation: `src/egregora/rendering/mkdocs_documents.py` (457 lines)
- Document abstraction: `src/egregora/core/document.py`
- Storage protocols: `src/egregora/storage/__init__.py`
- CLAUDE.md: Architecture section
