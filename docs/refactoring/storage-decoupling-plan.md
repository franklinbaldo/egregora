# Storage Decoupling Implementation Plan

## Epic: Decouple Core Logic from Storage Implementation

**Goal**: Make Egregora extensible and easier to maintain by separating business logic from storage implementation, enabling support for multiple static site generators (Hugo, Jekyll, etc.) without modifying core pipeline code.

**Status**: Planning Phase
**Created**: 2025-01-11
**Related**: Phase 4 OutputAdapter refactoring (completed)

---

## User Stories Summary

### Story 1: Supporting a New Static Site Generator (Hugo)
**As a Developer**, I want to add Hugo support by implementing a single `HugoOutputAdapter` class without modifying core pipeline logic.

### Story 2: Unit Testing the Writer Agent in Isolation
**As a DevOps Operator**, I want fast, reliable unit tests for the writer agent using in-memory storage without touching the filesystem.

### Story 3: Simplifying Pipeline Function Signatures
**As a Developer**, I want the pipeline to accept a single `ProcessConfig` object instead of 15+ individual parameters.

### Story 4: Consolidating Format-Specific Logic
**As a Developer**, I want all MkDocs-specific logic (like `.authors.yml`) isolated within `MkDocsOutputAdapter`, not in shared modules.

---

## Current Architecture Analysis

### Coupling Points Identified

#### 1. **Format-Specific Logic in Shared Modules** (HIGH PRIORITY)

**Location**: `src/egregora/agents/shared/profiler.py:602-654`

```python
def write_profile(...) -> str:
    # ... write profile ...

    # ❌ MkDocs-specific logic in generic module
    _update_authors_yml(profiles_dir.parent, author_uuid, front_matter)

    return str(profile_path)

def _update_authors_yml(site_root: Path, author_uuid: str, front_matter: dict) -> None:
    """Update or create .authors.yml for MkDocs blog plugin."""
    # 53 lines of MkDocs-specific YAML manipulation
```

**Problem**:
- Generic `profiler.py` module contains MkDocs blog plugin logic
- Makes it impossible to support other formats without breaking this module
- Violates separation of concerns

**User Story**: Story 4

---

#### 2. **Document Storage Field Never Used** (MEDIUM PRIORITY)

**Location**: `src/egregora/agents/writer/agent.py:107, 210`

```python
@dataclass(frozen=True, slots=True)
class WriterAgentContext:
    # ...

    # ❌ DEPRECATED: Never read, only written
    document_storage: DocumentStorage

    # ✅ MODERN Phase 4: Actually used
    url_convention: UrlConvention
    output_format: OutputAdapter
```

**Problem**:
- `document_storage` field is assigned but never read (269 lines of dead code)
- Already replaced by `output_format` in Phase 4
- Confuses developers about which pattern to use

**User Story**: N/A (Technical debt from Phase 4)

---

#### 3. **Complex Function Signatures** (LOW PRIORITY)

**Location**: `src/egregora/pipeline/runner.py:687-696`

```python
def run_source_pipeline(
    source: str,
    input_path: Path,
    output_dir: Path,
    config: EgregoraConfig,  # ✅ Already uses config object
    *,
    api_key: str | None = None,
    model_override: str | None = None,
    client: genai.Client | None = None,
) -> dict[str, dict[str, list[str]]]:
```

**Current State**: Already significantly improved in Phase 2 (reduced from 16 to 7 parameters)

**Problem**:
- Still has optional parameters that could be in `ProcessConfig`
- Client injection is good for testing but could be cleaner

**User Story**: Story 3

---

#### 4. **Direct Filesystem Access in Tools** (ADDRESSED IN PHASE 4)

**Location**: `src/egregora/agents/writer/agent.py:607-656`

```python
@agent.tool
def write_post_tool(ctx: RunContext[WriterAgentState], metadata: PostMetadata, content: str):
    # ✅ MODERN Phase 4: Already uses protocols
    doc = Document(content=content, type=DocumentType.POST, metadata=...)
    url = ctx.deps.url_convention.canonical_url(doc, ctx.deps.url_context)
    ctx.deps.output_format.serve(doc)
    return WritePostResult(status="success", path=url)
```

**Current State**: ✅ Already decoupled via OutputAdapter protocol

**User Story**: Stories 1 & 2 (already complete for posts/profiles)

---

## Implementation Phases

### Phase 5A: Move Format-Specific Logic to OutputAdapter ⚡ HIGH PRIORITY

**Goal**: Isolate all MkDocs-specific logic within `MkDocsOutputAdapter`

**Tasks**:

1. **Create ProfileStorage Protocol**
   ```python
   # src/egregora/storage/profile_storage.py

   from typing import Protocol

   class ProfileStorage(Protocol):
       """Protocol for profile persistence."""

       def read(self, author_uuid: str) -> str:
           """Read profile content."""
           ...

       def write(self, author_uuid: str, content: str, metadata: dict) -> str:
           """Write profile with metadata.

           Returns:
               Opaque profile identifier (could be UUID, path, URL, etc.)
           """
           ...
   ```

2. **Implement MkDocsProfileStorage**
   ```python
   # src/egregora/rendering/mkdocs_profile_storage.py

   from pathlib import Path
   import yaml

   class MkDocsProfileStorage:
       """MkDocs-specific profile storage with .authors.yml support."""

       def __init__(self, profiles_dir: Path, site_root: Path):
           self._profiles_dir = profiles_dir
           self._site_root = site_root

       def read(self, author_uuid: str) -> str:
           path = self._profiles_dir / f"{author_uuid}.md"
           if not path.exists():
               return ""
           return path.read_text(encoding="utf-8")

       def write(self, author_uuid: str, content: str, metadata: dict) -> str:
           # 1. Write profile markdown with YAML frontmatter
           path = self._profiles_dir / f"{author_uuid}.md"
           yaml_front = yaml.dump(metadata, ...)
           full_content = f"---\n{yaml_front}---\n\n{content}"
           path.write_text(full_content, encoding="utf-8")

           # 2. Update .authors.yml (MkDocs blog plugin requirement)
           self._update_authors_yml(author_uuid, metadata)

           return str(path)

       def _update_authors_yml(self, author_uuid: str, metadata: dict) -> None:
           """Update .authors.yml for MkDocs blog plugin."""
           # Move the 53 lines from profiler.py here
           authors_yml_path = self._site_root / ".authors.yml"
           # ... (existing logic from _update_authors_yml)
   ```

3. **Refactor profiler.py to be generic**
   ```python
   # src/egregora/agents/shared/profiler.py

   def write_profile(
       author_uuid: str,
       content: str,
       storage: ProfileStorage,  # ✅ Protocol, not Path
   ) -> str:
       """Write profile using storage protocol."""
       metadata = _build_profile_metadata(author_uuid, content)
       return storage.write(author_uuid, content, metadata)

   # ❌ DELETE: _update_authors_yml() - moved to MkDocsProfileStorage
   ```

4. **Update writer agent integration**
   ```python
   # src/egregora/agents/writer/core.py

   from egregora.output_adapters.mkdocs_profile_storage import MkDocsProfileStorage

   # Create storage instances
   profile_storage = MkDocsProfileStorage(
       profiles_dir=profiles_dir,
       site_root=site_root
   )

   runtime_context = WriterAgentContext(
       profiles=profile_storage,  # ✅ Inject protocol implementation
       # ...
   )
   ```

**Benefits**:
- ✅ `profiler.py` becomes truly generic
- ✅ Hugo support only needs `HugoProfileStorage` implementation
- ✅ No changes to agent tools required

**Estimated Time**: 4 hours

**Tests Required**:
- Unit tests for `MkDocsProfileStorage.write()` verifying `.authors.yml` update
- Integration test ensuring profiles + .authors.yml work end-to-end
- Verify no regression in existing profile functionality

---

### Phase 5B: Remove Dead Code from Phase 4 📦 MEDIUM PRIORITY

**Goal**: Clean up unused `document_storage` field and related code

**Tasks**:

1. **Remove document_storage from contexts**
   ```python
   # src/egregora/agents/writer/agent.py

   @dataclass(frozen=True, slots=True)
   class WriterAgentContext:
       # ... other fields ...

       # ❌ DELETE THIS FIELD
       # document_storage: DocumentStorage

       # ✅ KEEP THESE (Phase 4 replacements)
       url_convention: UrlConvention
       url_context: UrlContext
       output_format: OutputAdapter
   ```

2. **Remove LegacyStorageAdapter instantiation**
   ```python
   # src/egregora/agents/writer/core.py

   # ❌ DELETE THESE LINES
   # from egregora.storage.legacy_adapter import LegacyStorageAdapter
   # legacy_adapter = LegacyStorageAdapter(...)
   # document_storage = legacy_adapter
   ```

3. **Update all WriterAgentContext instantiations**
   - Search: `WriterAgentContext(`
   - Remove: `document_storage=...` parameter
   - Files: `core.py`, test files

4. **Deprecate (not delete yet) unused classes**
   ```python
   # src/egregora/storage/legacy_adapter.py

   import warnings

   class LegacyStorageAdapter:
       """DEPRECATED: Use OutputAdapter protocol instead.

       This class will be removed in version 0.6.0.
       """

       def __init__(self, *args, **kwargs):
           warnings.warn(
               "LegacyStorageAdapter is deprecated, use OutputAdapter instead",
               DeprecationWarning,
               stacklevel=2
           )
   ```

5. **Mark MkDocsDocumentStorage for deprecation**
   ```python
   # src/egregora/storage/documents.py

   # Add deprecation notice to docstring
   class MkDocsDocumentStorage:
       """DEPRECATED: Use MkDocsOutputAdapter instead.

       This class will be removed in version 0.6.0.
       Migration: Use MkDocsOutputAdapter.serve() for document persistence.
       """
   ```

**Benefits**:
- ✅ Removes 269 lines of dead code
- ✅ Clarifies which pattern to use (OutputAdapter)
- ✅ Reduces cognitive load for new contributors

**Estimated Time**: 2 hours

**Tests Required**:
- All existing tests should still pass
- No new tests needed (removing unused code)
- Verify deprecation warnings appear if anyone uses old classes

---

### Phase 5C: Simplify Pipeline Configuration (OPTIONAL) 🔧 LOW PRIORITY

**Goal**: Further reduce parameter passing in pipeline functions

**Status**: Already 80% complete (Phase 2 reduced to EgregoraConfig)

**Remaining Work** (if desired):

1. **Create ProcessConfig for runtime overrides**
   ```python
   # src/egregora/config/process.py

   @dataclass(frozen=True, slots=True)
   class ProcessConfig:
       """Runtime configuration for a single pipeline run.

       Combines EgregoraConfig (persistent) with runtime overrides (CLI flags).
       """

       # Base configuration
       config: EgregoraConfig

       # Runtime overrides
       source: str
       input_path: Path
       output_dir: Path

       # Optional overrides (from CLI)
       api_key: str | None = None
       model_override: str | None = None
       client: genai.Client | None = None
   ```

2. **Refactor run_source_pipeline signature**
   ```python
   # src/egregora/pipeline/runner.py

   def run_source_pipeline(
       process_config: ProcessConfig,
   ) -> dict[str, dict[str, list[str]]]:
       """Run pipeline with unified configuration."""
       config = process_config.config
       client = process_config.client or genai.Client(api_key=process_config.api_key)
       # ...
   ```

**Benefits**:
- ✅ Single source of truth for configuration
- ✅ Easier to add new options (only update ProcessConfig)
- ✅ Cleaner CLI integration

**Estimated Time**: 3 hours

**Decision**: DEFER - Current signature (7 params) is already manageable

---

### Phase 5D: In-Memory Storage for Testing (OPTIONAL) 🧪 LOW PRIORITY

**Goal**: Enable fast unit tests without filesystem I/O

**Tasks**:

1. **Create InMemoryOutputFormat**
   ```python
   # tests/helpers/in_memory_storage.py

   from egregora.storage import OutputAdapter, UrlConvention, UrlContext
   from egregora.data_primitives.document import Document

   class InMemoryOutputFormat:
       """In-memory OutputAdapter for testing."""

       def __init__(self, url_convention: UrlConvention):
           self._url_convention = url_convention
           self._documents: dict[str, Document] = {}

       @property
       def url_convention(self) -> UrlConvention:
           return self._url_convention

       def serve(self, document: Document) -> None:
           """Store document in memory."""
           self._documents[document.document_id] = document

       def get_document(self, doc_id: str) -> Document | None:
           """Retrieve document by ID (test helper)."""
           return self._documents.get(doc_id)

       def list_documents(self) -> list[Document]:
           """List all documents (test helper)."""
           return list(self._documents.values())
   ```

2. **Create InMemoryProfileStorage**
   ```python
   class InMemoryProfileStorage:
       """In-memory ProfileStorage for testing."""

       def __init__(self):
           self._profiles: dict[str, str] = {}

       def read(self, author_uuid: str) -> str:
           return self._profiles.get(author_uuid, "")

       def write(self, author_uuid: str, content: str, metadata: dict) -> str:
           profile_id = f"in-memory-profile:{author_uuid}"
           self._profiles[author_uuid] = content
           return profile_id
   ```

3. **Update writer agent tests**
   ```python
   # tests/unit/agents/test_writer_agent.py

   def test_writer_agent_with_in_memory_storage():
       """Test writer agent using in-memory storage (no filesystem)."""
       url_convention = LegacyMkDocsUrlConvention()
       output_format = InMemoryOutputFormat(url_convention)
       profile_storage = InMemoryProfileStorage()

       context = WriterAgentContext(
           url_convention=url_convention,
           url_context=UrlContext(),
           output_format=output_format,
           profiles=profile_storage,
           # ...
       )

       # Run agent
       result = write_posts_with_pydantic_agent(
           prompt="...",
           config=config,
           context=context,
       )

       # Assert using in-memory accessors (no filesystem checks!)
       assert len(output_format.list_documents()) == 1
       assert profile_storage._profiles["author-uuid"] == "expected content"
   ```

**Benefits**:
- ✅ Tests run 10-100x faster (no disk I/O)
- ✅ No cleanup needed (no temp directories)
- ✅ 100% reliable (no filesystem race conditions)
- ✅ Can test failure scenarios (read-only, out of space, etc.)

**Estimated Time**: 4 hours

**Decision**: RECOMMENDED for test suite improvement

---

## Implementation Order

### Recommended Sequence

1. **Phase 5A**: Move format-specific logic (HIGH PRIORITY)
   - **Why first**: Enables Hugo support, biggest architectural win
   - **Risk**: Medium (touches shared profiler module)
   - **Time**: 4 hours

2. **Phase 5B**: Remove dead code (MEDIUM PRIORITY)
   - **Why second**: Clean up after Phase 4, low risk
   - **Risk**: Low (removing unused code)
   - **Time**: 2 hours

3. **Phase 5D**: In-memory storage for tests (OPTIONAL)
   - **Why third**: Test infrastructure improvement
   - **Risk**: Low (only affects tests)
   - **Time**: 4 hours

4. **Phase 5C**: Simplify configuration (DEFERRED)
   - **Why last**: Current state is already good enough
   - **Risk**: Medium (touches CLI and pipeline entry point)
   - **Time**: 3 hours

---

## Success Criteria

### Phase 5A Complete When:
- ✅ `profiler.py` has zero MkDocs-specific code
- ✅ `.authors.yml` logic is in `MkDocsProfileStorage.write()`
- ✅ All existing profile tests pass
- ✅ Can implement `HugoProfileStorage` without touching `profiler.py`

### Phase 5B Complete When:
- ✅ `document_storage` field removed from contexts
- ✅ `LegacyStorageAdapter` marked deprecated
- ✅ `MkDocsDocumentStorage` marked deprecated
- ✅ All tests pass with no references to deleted code

### Phase 5D Complete When:
- ✅ Writer agent tests use `InMemoryOutputFormat`
- ✅ Profile tests use `InMemoryProfileStorage`
- ✅ Test suite runs <5 seconds (currently ~20 seconds)
- ✅ No temp directories created during unit tests

---

## P1 Issue: Slug Collision Behavior

### Current Behavior (Intentional)

**Location**: `src/egregora/rendering/mkdocs_output_format.py:132-143`

```python
def serve(self, document: Document) -> None:
    # ... calculate path ...

    # ✅ For slug-based paths (posts, profiles): OVERWRITE is intentional
    # A second post with same slug+date should replace the first

    # ✅ For content-addressed paths (ENRICHMENT_URL): Check collisions
    if path.exists() and document.type == DocumentType.ENRICHMENT_URL:
        existing_doc_id = self._get_document_id_at_path(path)
        if existing_doc_id and existing_doc_id != doc_id:
            path = self._resolve_collision(path, doc_id)

    # Write (may overwrite existing file for slug-based paths)
    self._write_document(document, path)
```

### Design Decision: Overwriting is Intentional

**Rationale**:
1. **Posts are identified by slug + date**, not content
   - If you write two posts with same slug "my-post" on same date "2025-01-11"
   - They should have the same path: `posts/2025-01-11-my-post.md`
   - Second write should **update/replace** the first (like a database UPDATE)

2. **Profiles are identified by UUID**
   - If you write profile for UUID "abc-123" twice
   - Both should write to: `profiles/abc-123.md`
   - Second write should **update** the profile (like PUT in REST)

3. **Only content-addressed paths need collision detection**
   - ENRICHMENT_URL uses content hash as filename
   - Two different contents could theoretically produce same hash (SHA256 collision)
   - This is the only case where collision detection is needed

### serve() Can Optionally Return Error (Future Enhancement)

**Current Signature**:
```python
def serve(self, document: Document) -> None:
    """Persist document (void return)."""
```

**Potential Future Signature** (if needed):
```python
def serve(self, document: Document) -> ServeResult:
    """Persist document with optional error reporting."""

@dataclass
class ServeResult:
    status: Literal["success", "collision", "error"]
    path: str
    error: str | None = None
```

**Decision**: DEFER - Current void design is sufficient. If collision reporting is needed in the future, we can:
1. Add optional return type (backward compatible)
2. Or use exceptions for error cases
3. Or use logging/metrics for observability

**Documentation**: Add docstring clarifying this is intentional behavior

```python
def serve(self, document: Document) -> None:
    """Persist document to storage (fire-and-forget).

    Behavior by document type:
    - POST: Path is slug+date based. Overwrites existing post with same slug+date.
    - PROFILE: Path is UUID based. Overwrites existing profile for same UUID.
    - ENRICHMENT_URL: Path is content-hash based. Detects collisions and adds suffix.

    This is intentional idempotent behavior:
    - Writing post "my-post" twice → updates the file
    - Writing profile "abc-123" twice → updates the file
    - Only hash-based paths check for collisions

    Returns:
        None (fire-and-forget pattern)

    Raises:
        IOError: If filesystem write fails
    """
```

---

## Testing Strategy

### Unit Tests

1. **Protocol Compliance Tests**
   ```python
   def test_mkdocs_profile_storage_implements_protocol():
       """Verify MkDocsProfileStorage implements ProfileStorage protocol."""
       storage = MkDocsProfileStorage(...)
       assert isinstance(storage, ProfileStorage)  # Runtime check
   ```

2. **Format Isolation Tests**
   ```python
   def test_profiler_does_not_import_mkdocs():
       """Ensure profiler.py has no MkDocs imports."""
       import egregora.agents.shared.profiler as profiler
       import sys

       # Check imports
       assert 'yaml' not in sys.modules  # Before import
       # ... trigger profiler functions ...
       # YAML should only be imported in MkDocsProfileStorage, not profiler
   ```

3. **In-Memory Storage Tests**
   ```python
   def test_in_memory_output_format_protocol_compliance():
       """Verify InMemoryOutputFormat implements OutputAdapter."""
       fmt = InMemoryOutputFormat(LegacyMkDocsUrlConvention())

       doc = Document(content="test", type=DocumentType.POST, metadata={"slug": "test"})
       fmt.serve(doc)

       assert len(fmt.list_documents()) == 1
       assert fmt.get_document(doc.document_id).content == "test"
   ```

### Integration Tests

1. **End-to-End Profile Creation**
   ```python
   def test_profile_creation_updates_authors_yml(tmp_path):
       """Verify profile write updates .authors.yml."""
       site_root = tmp_path / "site"
       profiles_dir = site_root / "profiles"
       profiles_dir.mkdir(parents=True)

       storage = MkDocsProfileStorage(profiles_dir, site_root)
       storage.write("test-uuid", "Profile content", {"alias": "Test User"})

       # Check profile file
       assert (profiles_dir / "test-uuid.md").exists()

       # Check .authors.yml
       authors_yml = site_root / ".authors.yml"
       assert authors_yml.exists()

       import yaml
       authors = yaml.safe_load(authors_yml.read_text())
       assert "test-uuid" in authors
       assert authors["test-uuid"]["name"] == "Test User"
   ```

2. **Hugo Support Validation** (future)
   ```python
   def test_hugo_output_format_integration():
       """Verify HugoOutputAdapter works with writer agent."""
       hugo_format = HugoOutputAdapter(site_root=tmp_path)

       # Use Hugo format instead of MkDocs
       context = WriterAgentContext(
           output_format=hugo_format,
           # ...
       )

       result = write_posts_with_pydantic_agent(...)

       # Verify Hugo-specific structure
       assert (tmp_path / "content" / "posts" / "test-post" / "index.md").exists()
       # TOML frontmatter, not YAML
       content = (tmp_path / "content" / "posts" / "test-post" / "index.md").read_text()
       assert content.startswith("+++")
   ```

---

## Migration Path

### For External Contributors Adding New Formats

**Before** (would require modifying core):
```python
# ❌ Have to modify profiler.py to add Hugo support
def write_profile(...):
    # ... write profile ...

    if format == "mkdocs":
        _update_authors_yml(...)
    elif format == "hugo":
        _update_hugo_taxonomy(...)  # ❌ Modifying core
```

**After** (just implement protocol):
```python
# ✅ Implement protocol, zero core changes
class HugoProfileStorage:
    """Hugo-specific profile storage."""

    def write(self, author_uuid: str, content: str, metadata: dict) -> str:
        # Hugo-specific logic in isolation
        path = self._profiles_dir / f"authors/{author_uuid}/_index.md"

        # TOML frontmatter (Hugo uses TOML, not YAML)
        toml_front = toml.dumps(metadata)
        full_content = f"+++\n{toml_front}+++\n\n{content}"
        path.write_text(full_content)

        # Update Hugo taxonomy (isolated in this class)
        self._update_hugo_taxonomy(author_uuid, metadata)

        return str(path)
```

### For Existing Deployments

**No breaking changes** - All existing MkDocs sites continue to work:
- `MkDocsOutputAdapter` remains default
- `.authors.yml` continues to be updated
- All file paths stay the same
- Only internal refactoring, no API changes

---

## Appendix: Slug Collision Documentation

### Add to CLAUDE.md

```markdown
## Slug Collision Behavior (P1 Badge Response)

### Intended Design

The `serve()` method in OutputAdapter has **intentional overwriting behavior** for slug-based paths:

**Posts** (slug + date):
- Path: `posts/YYYY-MM-DD-{slug}.md`
- Collision: **Overwrites** (second post with same slug+date replaces first)
- Rationale: Posts are identified by slug+date, not content (like UPDATE in SQL)

**Profiles** (UUID):
- Path: `profiles/{uuid}.md`
- Collision: **Overwrites** (updating profile for same UUID)
- Rationale: Profiles are identified by UUID (like PUT in REST)

**Enrichment URLs** (content hash):
- Path: `enrichments/{hash}.md`
- Collision: **Detects and resolves** with suffix (`{hash}-1.md`)
- Rationale: Hash collisions are rare but theoretically possible

### Error Reporting (Future)

Currently `serve()` returns `None` (fire-and-forget). If collision reporting is needed:

**Option 1**: Add optional return type (backward compatible)
```python
def serve(self, document: Document) -> ServeResult | None:
    """Returns ServeResult if error, None if success."""
```

**Option 2**: Use exceptions for errors
```python
def serve(self, document: Document) -> None:
    """Raises ServeError on collision (if strict mode enabled)."""
    if strict and path.exists():
        raise SlugCollisionError(...)
```

**Decision**: DEFER until needed. Current overwriting behavior is correct for idempotent publishing.
```

---

## Summary

### Recommended Implementation

1. **Implement Phase 5A** (4 hours) - Biggest architectural win
   - Move `.authors.yml` logic to `MkDocsProfileStorage`
   - Make `profiler.py` truly generic
   - Enable Hugo/Jekyll support without core changes

2. **Implement Phase 5B** (2 hours) - Clean up Phase 4
   - Remove `document_storage` dead code
   - Deprecate unused classes
   - Clarify migration path

3. **Document P1 slug collision** (30 minutes)
   - Add docstring explaining intentional behavior
   - Update CLAUDE.md with design rationale
   - No code changes needed

**Total Time**: 6.5 hours

**Phases 5C and 5D**: OPTIONAL (defer until needed)

**Result**: Clean, extensible architecture supporting multiple formats without modifying core pipeline.
