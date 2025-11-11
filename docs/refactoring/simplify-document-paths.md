# Refactor: Simplify Document Path Resolution

## Problem

Current `MkDocsDocumentStorage` has **457 lines** with type-specific complexity:

- **6 separate path methods**: `_determine_post_path()`, `_determine_profile_path()`, etc.
- **Scattered collision logic**: Three layers (OutputFormat utils, in-memory index, per-document checks)
- **Format coupling**: Storage layer knows about frontmatter, `.authors.yml`, directory structure
- **Type branching**: `if document.type == POST: ... elif document.type == PROFILE: ...`

**Code smell**: Adding a new document type requires modifying multiple methods in storage.

## Solution

Introduce **uniform path resolution** via output format:

```python
@dataclass(frozen=True)
class PathResolution:
    """Result of resolving a document's intended path."""
    path: Path                      # Where document should be written
    occupied: bool                  # True if path exists with different content
    existing_doc_id: str | None     # Document ID at path (if occupied)
    collision_strategy: str         # "suffix" | "replace" | "error"

class OutputFormat:
    """Base protocol for output format conventions."""

    def resolve_path(
        self,
        metadata: dict[str, Any],
        doc_type: DocumentType,
        content_hash: str  # For deduplication
    ) -> PathResolution:
        """
        Given document metadata and type, return intended path and occupancy.

        This single method handles ALL document types uniformly.
        """
        ...

class MkDocsOutputFormat(OutputFormat):
    """MkDocs-specific path conventions."""

    def resolve_path(self, metadata, doc_type, content_hash) -> PathResolution:
        # Determine base path by type
        if doc_type == DocumentType.POST:
            date = metadata.get("date", datetime.now())
            slug = self._slugify(metadata.get("title", "untitled"))
            path = self.posts_dir / f"{date.strftime('%Y-%m-%d')}-{slug}.md"
        elif doc_type == DocumentType.PROFILE:
            uuid = metadata["author_id"]
            path = self.profiles_dir / f"{uuid}.md"
        elif doc_type == DocumentType.JOURNAL:
            label = metadata.get("window_label", "unknown")
            path = self.journal_dir / f"journal_{self._safe_label(label)}.md"
        # ... other types

        # Check occupancy once, in one place
        if path.exists():
            existing_hash = self._read_content_hash(path)
            if existing_hash == content_hash:
                # Same content - idempotent
                return PathResolution(path, occupied=False, existing_doc_id=None, collision_strategy="skip")
            else:
                # Different content - collision
                existing_id = self._read_doc_id(path)
                return PathResolution(path, occupied=True, existing_doc_id=existing_id, collision_strategy="suffix")

        return PathResolution(path, occupied=False, existing_doc_id=None, collision_strategy="skip")
```

**Storage layer becomes simple:**

```python
class MkDocsDocumentStorage(DocumentStorage):
    def __init__(self, base_path: Path, output_format: OutputFormat):
        self.base_path = base_path
        self.format = output_format  # Inject format conventions

    def add(self, document: Document) -> Path:
        # 1. Resolve path (single call for all types)
        resolution = self.format.resolve_path(
            document.metadata,
            document.type,
            document.document_id  # Content hash
        )

        # 2. Handle collision if needed
        final_path = resolution.path
        if resolution.occupied:
            if resolution.collision_strategy == "suffix":
                final_path = self._add_suffix(resolution.path)
            elif resolution.collision_strategy == "error":
                raise DocumentCollision(...)

        # 3. Write document
        self._write_file(final_path, document)

        return final_path

    def _write_file(self, path: Path, document: Document):
        """Format-agnostic write (delegates formatting to Document)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document.content)

        # Post-write hooks (if needed)
        if document.type == DocumentType.PROFILE:
            self._update_authors_yml(document)
```

## Benefits

### 1. **Uniformity**
- Single path resolution interface for all document types
- No more `if doc_type == POST: ... elif doc_type == PROFILE: ...`
- Adding new types only requires extending `resolve_path()` switch

### 2. **Clarity**
- Occupancy semantics explicit: `occupied` + `existing_doc_id` + `collision_strategy`
- Path logic consolidated in one place
- Storage concerns separated from format conventions

### 3. **Testability**
- Mock `OutputFormat.resolve_path()` to test storage without filesystem
- Test path conventions independently of storage operations
- Test collision handling without document creation

### 4. **Flexibility**
- Swap output formats without changing storage: `HugoOutputFormat`, `ObsidianOutputFormat`
- Different collision strategies per document type: suffix for posts, replace for media
- Per-project customization: inject custom format implementation

### 5. **Simplification**
- **Remove in-memory index** - occupancy checked directly via format
- **Remove 6 type-specific methods** - replaced by single `resolve_path()`
- **Remove three-layer collision detection** - consolidated in format
- **~200 line reduction** in storage implementation

## Migration Plan

### Phase 1: Introduce PathResolution (No Breaking Changes)

**Files to create:**
- `src/egregora/storage/path_resolution.py` - PathResolution dataclass + OutputFormat protocol
- `src/egregora/storage/mkdocs_format.py` - MkDocsOutputFormat implementation

**Steps:**
1. Define `PathResolution` dataclass (frozen, slots)
2. Define `OutputFormat` protocol with `resolve_path()` method
3. Implement `MkDocsOutputFormat`:
   - Extract path logic from current `_determine_*_path()` methods
   - Consolidate collision detection
   - Return `PathResolution` with occupancy info
4. Add tests for `MkDocsOutputFormat` in `tests/unit/storage/test_mkdocs_format.py`

**Deliverable:** New format abstraction working alongside existing storage (no integration yet).

### Phase 2: Refactor MkDocsDocumentStorage

**Files to modify:**
- `src/egregora/rendering/mkdocs_documents.py` - simplify storage implementation

**Steps:**
1. Update `MkDocsDocumentStorage.__init__()` to accept `output_format: OutputFormat`
2. Replace `add()` implementation:
   - Remove direct calls to `_determine_*_path()`
   - Call `format.resolve_path()` instead
   - Simplify collision handling using `resolution.collision_strategy`
3. Remove old methods:
   - Delete 6 `_determine_*_path()` methods
   - Delete `_index` dict (no longer needed)
   - Delete redundant collision utilities
4. Update `_write_document()` to be simpler (path already resolved)

**Deliverable:** Storage implementation using new format abstraction (~250 lines instead of 457).

### Phase 3: Update Consumers

**Files to modify:**
- `src/egregora/cli.py` - inject `MkDocsOutputFormat` into storage
- `src/egregora/agents/writer/writer_agent.py` - update storage initialization
- Integration tests

**Steps:**
1. Update storage factory/initialization:
   ```python
   format = MkDocsOutputFormat(base_path=output_dir)
   storage = MkDocsDocumentStorage(base_path=output_dir, output_format=format)
   ```
2. Run integration tests: `uv run pytest tests/integration/storage/`
3. Run E2E tests: `uv run pytest tests/e2e/`
4. Fix any regressions

**Deliverable:** Full system using new path resolution, all tests passing.

### Phase 4: Cleanup & Documentation

**Files to modify:**
- `docs/architecture/document-storage.md` - document new approach
- `CLAUDE.md` - update storage guidance

**Steps:**
1. Remove unused utilities from `storage/base.py` (if any)
2. Add docstrings explaining path resolution pattern
3. Update architecture docs
4. Add examples of custom format implementation

**Deliverable:** Clean codebase with documented pattern.

## Testing Strategy

### Unit Tests

**Format tests** (`tests/unit/storage/test_mkdocs_format.py`):
```python
def test_resolve_post_path_new_document():
    format = MkDocsOutputFormat(base_path=tmp_path)
    metadata = {"title": "My Post", "date": datetime(2025, 1, 11)}

    resolution = format.resolve_path(metadata, DocumentType.POST, "hash-123")

    assert resolution.path == tmp_path / "posts/2025-01-11-my-post.md"
    assert not resolution.occupied
    assert resolution.collision_strategy == "skip"

def test_resolve_post_path_collision():
    format = MkDocsOutputFormat(base_path=tmp_path)
    # Create existing file with different hash
    existing = tmp_path / "posts/2025-01-11-my-post.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("<!-- doc_id: old-hash -->")

    resolution = format.resolve_path(
        {"title": "My Post", "date": datetime(2025, 1, 11)},
        DocumentType.POST,
        "new-hash"
    )

    assert resolution.occupied
    assert resolution.existing_doc_id == "old-hash"
    assert resolution.collision_strategy == "suffix"

def test_resolve_profile_path():
    format = MkDocsOutputFormat(base_path=tmp_path)

    resolution = format.resolve_path(
        {"author_id": "uuid-456"},
        DocumentType.PROFILE,
        "hash-789"
    )

    assert resolution.path == tmp_path / "profiles/uuid-456.md"
```

**Storage tests** (`tests/unit/storage/test_mkdocs_storage.py`):
```python
def test_add_document_uses_format_resolution(mocker):
    mock_format = mocker.Mock(spec=OutputFormat)
    mock_format.resolve_path.return_value = PathResolution(
        path=Path("posts/test.md"),
        occupied=False,
        existing_doc_id=None,
        collision_strategy="skip"
    )
    storage = MkDocsDocumentStorage(tmp_path, output_format=mock_format)

    doc = Document(content="Test", type=DocumentType.POST, metadata={}, ...)
    path = storage.add(doc)

    mock_format.resolve_path.assert_called_once_with(
        doc.metadata,
        doc.type,
        doc.document_id
    )
    assert path == tmp_path / "posts/test.md"
```

### Integration Tests

- Verify collision handling with real filesystem
- Test idempotency (same document written twice)
- Test all document types end-to-end
- Verify `.authors.yml` updates for profiles

### E2E Tests

- Run full pipeline with new storage
- Compare output against golden fixtures
- Verify no regressions in generated MkDocs sites

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Breaking change in path generation** | Phase 1 validates format logic matches current behavior via unit tests |
| **Performance regression** | Benchmark path resolution (likely faster without index) |
| **Collision handling edge cases** | Extensive tests for collision scenarios (same hash, different hash, missing file) |
| **Format-specific hooks** (`.authors.yml`) | Keep post-write hooks in storage, document in OutputFormat protocol |

## Future Extensions

Once refactored:

1. **Custom formats**: Users can inject custom `OutputFormat` implementations
2. **Per-type strategies**: Different collision strategies per document type (replace media, suffix posts)
3. **Path templates**: Configurable path patterns in `.egregora/config.yml`
4. **Alternative outputs**: Hugo, Obsidian, Notion via different formats
5. **Path validation**: Format can validate paths before write (length limits, reserved names)

## Success Criteria

- [ ] `MkDocsDocumentStorage` reduced from ~457 to ~250 lines
- [ ] All 6 `_determine_*_path()` methods removed
- [ ] Single `resolve_path()` call handles all document types
- [ ] In-memory index removed
- [ ] All tests pass (unit, integration, E2E)
- [ ] No regressions in generated MkDocs sites
- [ ] Documentation updated

## References

- Current implementation: `src/egregora/rendering/mkdocs_documents.py`
- Document abstraction: `src/egregora/core/document.py`
- Storage protocols: `src/egregora/storage/__init__.py`
- CLAUDE.md: Architecture section on Document abstraction
