# Adapter Pattern Refactoring Plan

**Status**: ✅ COMPLETE (with PR #638 fix applied)
**Date**: 2025-01-10
**Completed**: 2025-11-10
**Last Updated**: 2025-11-10 (OutputFormat Coordinator Fix Applied)
**Scope**: Major architectural refactor to decouple agents from I/O structure

## ✅ PR #638 FIX APPLIED (2025-11-10)

**Issue**: Adapter pattern refactoring bypassed OutputFormat coordinator and lost data integrity validations.

**Fix Applied** (7 phases): Restored OutputFormat coordinator pattern with data integrity validations.

### Phase 1-2: OutputFormat Common Utilities
- Added abstract storage protocol properties to OutputFormat base class
  - `posts`, `profiles`, `journals`, `enrichments` (return Protocol instances)
  - `initialize(site_root)` method for two-step initialization
- Added common utility static methods:
  - `normalize_slug()` - URL-safe slug normalization using slugify
  - `extract_date_prefix()` - handles window labels, ISO timestamps, clean dates
  - `generate_unique_filename()` - prevents silent overwrites
  - `parse_frontmatter()` - YAML parsing
- Added template method hooks:
  - `prepare_window()` - pre-processing before writer agent runs
  - `finalize_window()` - post-processing after writer agent completes

### Phase 3: MkDocsPostStorage Data Integrity
- Updated `write()` to use OutputFormat utilities:
  - Slug normalization for URL-safe filenames
  - Date extraction for `{date}-{slug}.md` format
  - Unique filename generation to prevent overwrites
- Updated `read()` and `exists()` to handle both formats:
  - New: `{date}-{slug}.md` (with validation)
  - Legacy: `{slug}.md` (backwards compatibility)

### Phase 4: Writer Agent Integration
- Replaced `_create_storage_implementations()` with `_create_output_format()`
- Writer agent now uses OutputFormat coordinator:
  - Single format detection (no duplicate calls)
  - Extract storage from `output_format` properties
  - Call `finalize_window()` hook after completion

### Phase 5: HugoOutputFormat
- Added storage protocol implementation
- Currently reuses MkDocs storage as placeholder (Hugo not priority)

### Phase 6: Comprehensive Tests
- Added 24 validation tests for OutputFormat utilities
- Tests cover normalization, date extraction, unique filenames, integration

### Phase 7: Documentation
- Updated REFACTOR_ADAPTER_PATTERN.md (this file)
- CLAUDE.md updates pending

**Test Results**:
- 35 agent tests passing
- 17 storage protocol contract tests passing
- 24 OutputFormat validation tests passing
- All formats (MkDocs, Hugo) instantiate successfully

**Architecture Benefits**:
- WriterAgent → OutputFormat → Storage Protocols (proper layering)
- Data integrity: slug normalization, date prefixes, unique filenames
- Format-specific hooks: `prepare_window()`, `finalize_window()`
- All formats benefit from common validation utilities

**Commits**: ba6e09b, fae828a, 3d5ea08 (3 commits for fix)

## ✅ ORIGINAL IMPLEMENTATION COMPLETE (2025-11-10)

All phases of the adapter pattern refactoring were successfully implemented and tested:

- ✅ **Phase 1**: Storage protocols defined (`PostStorage`, `ProfileStorage`, `JournalStorage`)
- ✅ **Phase 2**: `WriterRuntimeContext` and `WriterAgentState` updated to use storage protocols
- ✅ **Phase 3**: All writer agent tools refactored to use storage protocols
- ✅ **Phase 4**: Prompt template system migrated to use `prompts_dir` parameter
- ✅ **Phase 5**: CLI/Pipeline verified (already using correct abstractions)
- ✅ **Phase 6**: Journal tests updated for storage adapters
- ✅ **Bonus**: Contract tests added to validate protocol implementations

**Original Test Results**:
- 35 agent tests passing
- 17 storage protocol contract tests passing
- Both MkDocs and in-memory implementations validated

**Original Commits**: a9edf16..fbb12af (8 commits)

## ⚠️ MAJOR REVISION (2025-11-10)

This plan has been significantly revised based on architectural review. Key changes:

1. **Interface Segregation**: Split mega-interface into focused storage protocols
2. **No Path Leakage**: Return string IDs instead of Path objects
3. **Direct Store Injection**: Inject VectorStore, AnnotationStore directly (not directories)
4. **Cleaner Contracts**: Simpler, more testable protocols

**Previous version** had OutputAdapter with 14 methods returning Path objects.
**New version** uses focused protocols (PostStorage, ProfileStorage, etc.) returning string IDs.

See "Design Decisions" section for rationale.

---

## Problem Statement

### Current Architecture Issues

Agents currently make **structure assumptions** throughout the codebase:

```python
# BAD - Agent decides directory structure
enrichment_path = docs_dir / "media" / "urls" / f"{enrichment_id}.md"
post_path = output_dir / "posts" / f"{slug}.md"
profile_path = profiles_dir / f"{uuid}.md"
prompts_dir = site_root / ".egregora" / "prompts"
```

**Issues:**
1. **Tight coupling** - Agents know about MkDocs structure (`.egregora/`, `posts/`, `docs/media/`)
2. **No abstraction** - Can't swap output formats (database, S3, different file structure)
3. **Path leakage** - Returning Path objects prevents true abstraction
4. **Testing complexity** - Hard to test with mock file systems
5. **Violates SOLID** - Agents have too many responsibilities

### Design Problems with Previous Approach

The original plan had a mega-interface `OutputAdapter` with 14 methods:

```python
class OutputAdapter(Protocol):
    # Posts
    def write_post(...) -> Path  # ❌ Returns Path
    def get_posts_dir() -> Path  # ❌ Exposes directory structure

    # Profiles
    def write_profile(...) -> Path
    def read_profile(...) -> str | None
    def get_profiles_dir() -> Path

    # ... 9 more methods for enrichments, journals, RAG, annotations, rankings
```

**Problems:**
1. **Interface Segregation Violation** - Every adapter must implement ALL methods
2. **Path Leakage** - Returning Path defeats abstraction (can't do database/S3)
3. **Too Wide** - Writer agent gets `get_rankings_dir()` even though it doesn't need it
4. **Directory Getters** - Agents still construct paths from directories

---

## Solution: Focused Storage Protocols

### Architecture Overview

```
┌─────────────────────┐
│   Source Adapter    │  (WhatsApp, Slack, Discord)
│ - get_messages()    │
│ - get_media_path()  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│      Agents         │  (Pure business logic)
│ - Writer            │
│ - Editor            │
│ - Enrichment        │
│ - Ranking           │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│   Focused Storage Protocols                  │
│                                               │
│  PostStorage  │  ProfileStorage │  Journal... │
│  (write,      │  (write,        │  (write)    │
│   read,       │   read)         │             │
│   exists)     │                 │             │
└──────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│   Implementations                             │
│                                               │
│  MkDocsPostStorage  │  InMemoryPostStorage   │
│  (filesystem)       │  (testing)             │
└──────────────────────────────────────────────┘
```

### Key Principles

1. **Interface Segregation** - Separate protocols for each concern (posts, profiles, etc.)
2. **No Path Leakage** - Return opaque string IDs, not Path objects
3. **Direct Injection** - Stores (VectorStore, AnnotationStore) injected directly
4. **Agents are pure** - No path construction, no I/O decisions
5. **Dependency injection** - Adapters composed into runtime contexts

---

## Design Decisions

### Decision 1: Multiple Protocols vs. Mega-Interface

**Chosen**: Multiple focused protocols (Interface Segregation Principle)

**Rationale**:
- Writer agent only needs PostStorage + ProfileStorage + JournalStorage
- Enrichment agent only needs EnrichmentStorage
- No agent needs ALL storage types
- Easier to test (mock only what you use)
- Follows SOLID principles

**Trade-off**: More protocols to manage, but cleaner separation of concerns

### Decision 2: Return String IDs vs. Path Objects

**Chosen**: Return opaque string identifiers

**Rationale**:
- Database adapters don't have "paths" (they have row IDs)
- S3 adapters return keys like `s3://bucket/posts/slug.md`
- Filesystem adapters can return relative paths as strings
- True abstraction - agents don't know implementation details

**Trade-off**: Agents can't manipulate paths, but that's the point (no path knowledge)

### Decision 3: Directory Getters vs. No Getters

**Chosen**: NO directory getter methods (`get_posts_dir()`, etc.)

**Rationale**:
- Directory getters leak filesystem assumptions
- If agents need a directory, they're doing I/O (wrong layer)
- Stores should be injected directly, not constructed from directories

**Trade-off**: More setup at initialization, but cleaner runtime behavior

### Decision 4: Inject Stores vs. Inject Directories

**Chosen**: Inject VectorStore, AnnotationStore directly in RuntimeContext

**Before**:
```python
@dataclass(frozen=True)
class WriterRuntimeContext:
    rag_dir: Path  # ❌ Agent constructs VectorStore(rag_dir / "chunks.parquet")
    annotations_dir: Path  # ❌ Agent constructs AnnotationStore(annotations_dir)
```

**After**:
```python
@dataclass(frozen=True)
class WriterRuntimeContext:
    rag_store: VectorStore  # ✅ Pre-constructed and injected
    annotations_store: AnnotationStore | None  # ✅ Pre-constructed and injected
```

**Rationale**:
- Agents shouldn't construct storage objects (not their responsibility)
- Stores can be tested with in-memory implementations
- Adapter owns the store construction logic

### Decision 5: Sync vs. Async

**Chosen**: Start with sync, document async as Phase 7

**Rationale**:
- Current codebase is sync (prompt templates use sync LLM calls)
- Adding async is a breaking change requiring function rewrites
- Can be added later without changing protocols (just add async versions)

**Future**: Add `async def write_async(...)` variants in Phase 7

---

## Implementation Plan

### Phase 1: Define Storage Protocols

**Goal**: Create focused interfaces that storage implementations must satisfy

#### File: `src/egregora/storage/__init__.py` (NEW package)

```python
"""Storage protocols defining contracts for data persistence."""

from typing import Protocol


class PostStorage(Protocol):
    """Storage interface for blog posts.

    Implementations hide storage details (filesystem, database, S3).
    Return values are opaque identifiers (not Path objects).
    """

    def write(self, slug: str, metadata: dict, content: str) -> str:
        """Write a post. Returns post identifier (opaque).

        Args:
            slug: URL-friendly slug (lowercase, hyphenated)
            metadata: Post frontmatter (title, date, tags, authors, etc.)
            content: Markdown post content

        Returns:
            Opaque identifier (e.g., "posts/my-post.md" for filesystem,
            "1234" for database, "s3://bucket/posts/my-post.md" for S3)
        """
        ...

    def read(self, slug: str) -> tuple[dict, str] | None:
        """Read a post. Returns (metadata, content) or None if not found."""
        ...

    def exists(self, slug: str) -> bool:
        """Check if post exists."""
        ...


class ProfileStorage(Protocol):
    """Storage interface for author profiles."""

    def write(self, author_uuid: str, content: str) -> str:
        """Write profile. Returns profile identifier."""
        ...

    def read(self, author_uuid: str) -> str | None:
        """Read profile content by UUID."""
        ...

    def exists(self, author_uuid: str) -> bool:
        """Check if profile exists."""
        ...


class JournalStorage(Protocol):
    """Storage interface for agent journals (execution logs)."""

    def write(self, window_label: str, content: str) -> str:
        """Write journal entry. Returns journal identifier.

        Args:
            window_label: Human-readable window label (e.g., "2025-01-10 10:00 to 12:00")
            content: Markdown journal content (thinking + freeform + tool calls)
        """
        ...


class EnrichmentStorage(Protocol):
    """Storage for URL and media enrichments."""

    def write_url_enrichment(self, url: str, content: str) -> str:
        """Write URL enrichment. Returns enrichment identifier."""
        ...

    def write_media_enrichment(self, filename: str, content: str) -> str:
        """Write media enrichment. Returns enrichment identifier."""
        ...
```

#### File: `src/egregora/storage/mkdocs.py` (NEW - MkDocs implementations)

```python
"""MkDocs filesystem-based storage implementations."""

import uuid
from pathlib import Path


class MkDocsPostStorage:
    """Filesystem-based post storage following MkDocs conventions.

    Structure:
        site_root/posts/{slug}.md
    """

    def __init__(self, site_root: Path):
        self.posts_dir = site_root / "posts"
        self.posts_dir.mkdir(parents=True, exist_ok=True)

    def write(self, slug: str, metadata: dict, content: str) -> str:
        """Write post to filesystem."""
        import yaml

        path = self.posts_dir / f"{slug}.md"
        full_content = f"---\n{yaml.dump(metadata)}---\n\n{content}"
        path.write_text(full_content, encoding="utf-8")

        # Return relative path as identifier
        return str(path.relative_to(self.posts_dir.parent))

    def read(self, slug: str) -> tuple[dict, str] | None:
        """Read post from filesystem."""
        path = self.posts_dir / f"{slug}.md"
        if not path.exists():
            return None

        # Parse frontmatter (simplified - use existing utils)
        from egregora.utils.write_post import _parse_frontmatter
        return _parse_frontmatter(path.read_text(encoding="utf-8"))

    def exists(self, slug: str) -> bool:
        return (self.posts_dir / f"{slug}.md").exists()


class MkDocsProfileStorage:
    """Filesystem-based profile storage.

    Structure:
        site_root/profiles/{uuid}.md
    """

    def __init__(self, site_root: Path):
        self.profiles_dir = site_root / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def write(self, author_uuid: str, content: str) -> str:
        path = self.profiles_dir / f"{author_uuid}.md"
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(self.profiles_dir.parent))

    def read(self, author_uuid: str) -> str | None:
        path = self.profiles_dir / f"{author_uuid}.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def exists(self, author_uuid: str) -> bool:
        return (self.profiles_dir / f"{author_uuid}.md").exists()


class MkDocsJournalStorage:
    """Filesystem-based journal storage.

    Structure:
        site_root/posts/journal/journal_{safe_label}.md
    """

    def __init__(self, site_root: Path):
        self.journal_dir = site_root / "posts" / "journal"
        self.journal_dir.mkdir(parents=True, exist_ok=True)

    def write(self, window_label: str, content: str) -> str:
        # Convert window label to filename-safe format
        safe_label = window_label.replace(" ", "_").replace(":", "-")
        path = self.journal_dir / f"journal_{safe_label}.md"
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(self.journal_dir.parent.parent))


class MkDocsEnrichmentStorage:
    """Filesystem-based enrichment storage.

    Structure:
        site_root/media/urls/{enrichment_id}.md
        site_root/docs/{filename}.md (media enrichment next to file)
    """

    def __init__(self, site_root: Path):
        self.site_root = site_root
        self.urls_dir = site_root / "media" / "urls"
        self.urls_dir.mkdir(parents=True, exist_ok=True)

    def write_url_enrichment(self, url: str, content: str) -> str:
        enrichment_id = uuid.uuid5(uuid.NAMESPACE_URL, url)
        path = self.urls_dir / f"{enrichment_id}.md"
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(self.site_root))

    def write_media_enrichment(self, filename: str, content: str) -> str:
        # Media enrichment goes next to the media file with .md extension
        media_path = self.site_root / "docs" / filename
        enrichment_path = media_path.with_suffix(media_path.suffix + ".md")
        enrichment_path.parent.mkdir(parents=True, exist_ok=True)
        enrichment_path.write_text(content, encoding="utf-8")
        return str(enrichment_path.relative_to(self.site_root))
```

#### File: `src/egregora/storage/memory.py` (NEW - In-memory test implementations)

```python
"""In-memory storage implementations for testing."""


class InMemoryPostStorage:
    """In-memory post storage for testing (no filesystem)."""

    def __init__(self):
        self._posts: dict[str, tuple[dict, str]] = {}

    def write(self, slug: str, metadata: dict, content: str) -> str:
        self._posts[slug] = (metadata, content)
        return f"memory://posts/{slug}"

    def read(self, slug: str) -> tuple[dict, str] | None:
        return self._posts.get(slug)

    def exists(self, slug: str) -> bool:
        return slug in self._posts


class InMemoryProfileStorage:
    """In-memory profile storage for testing."""

    def __init__(self):
        self._profiles: dict[str, str] = {}

    def write(self, author_uuid: str, content: str) -> str:
        self._profiles[author_uuid] = content
        return f"memory://profiles/{author_uuid}"

    def read(self, author_uuid: str) -> str | None:
        return self._profiles.get(author_uuid)

    def exists(self, author_uuid: str) -> bool:
        return author_uuid in self._profiles


class InMemoryJournalStorage:
    """In-memory journal storage for testing."""

    def __init__(self):
        self._journals: dict[str, str] = {}

    def write(self, window_label: str, content: str) -> str:
        safe_label = window_label.replace(" ", "_").replace(":", "-")
        self._journals[safe_label] = content
        return f"memory://journal/{safe_label}"


class InMemoryEnrichmentStorage:
    """In-memory enrichment storage for testing."""

    def __init__(self):
        self._url_enrichments: dict[str, str] = {}
        self._media_enrichments: dict[str, str] = {}

    def write_url_enrichment(self, url: str, content: str) -> str:
        import uuid
        enrichment_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
        self._url_enrichments[enrichment_id] = content
        return f"memory://enrichments/urls/{enrichment_id}"

    def write_media_enrichment(self, filename: str, content: str) -> str:
        self._media_enrichments[filename] = content
        return f"memory://enrichments/media/{filename}"
```

---

### Phase 2: Update Runtime Contexts

**Goal**: Replace path fields with storage protocol references

#### Before (example from `WriterRuntimeContext`):

```python
@dataclass(frozen=True, slots=True)
class WriterRuntimeContext:
    start_time: datetime
    end_time: datetime
    output_dir: Path          # ❌ Agent constructs paths from this
    profiles_dir: Path        # ❌ Agent constructs paths from this
    rag_dir: Path            # ❌ Agent constructs VectorStore from this
    site_root: Path | None   # ❌ Agent constructs .egregora/prompts
    client: Any
    annotations_store: AnnotationStore | None = None
```

#### After:

```python
@dataclass(frozen=True, slots=True)
class WriterRuntimeContext:
    """Runtime context for writer agent execution.

    MODERN (Adapter Pattern): Uses storage protocols instead of directory paths.
    Stores are pre-constructed and injected (not built from directories).
    """
    # Time window
    start_time: datetime
    end_time: datetime

    # Storage protocols (injected)
    posts: PostStorage
    profiles: ProfileStorage
    journals: JournalStorage

    # Pre-constructed stores (injected, not built from paths)
    rag_store: VectorStore
    annotations_store: AnnotationStore | None

    # LLM client
    client: Any

    # Prompt templates directory (resolved by caller, not constructed here)
    prompts_dir: Path | None = None

    # NO MORE: output_dir, profiles_dir, rag_dir, site_root
```

#### Files to Update:

- `src/egregora/agents/writer/agent.py` → `WriterRuntimeContext`
- `src/egregora/agents/editor/agent.py` → `EditorAgentState`
- `src/egregora/enrichment/core.py` → `EnrichmentRuntimeContext`
- `src/egregora/agents/ranking/agent.py` → `ComparisonConfig`

---

### Phase 3: Update Agents to Use Storage Protocols

**Goal**: Replace all path construction with storage protocol calls

#### Example: Writer Agent

**Before:**

```python
# Writer agent constructs path
def write_post_tool(ctx: RunContext[WriterAgentState], metadata: PostMetadata, content: str):
    from egregora.utils.write_post import write_post

    path = write_post(
        content=content,
        metadata=metadata.model_dump(exclude_none=True),
        output_dir=ctx.deps.output_dir  # ❌ Passes directory
    )
    return WritePostResult(status="success", path=path)
```

**After:**

```python
# Storage protocol handles everything
def write_post_tool(ctx: RunContext[WriterAgentState], metadata: PostMetadata, content: str):
    post_id = ctx.deps.posts.write(
        slug=metadata.slug,
        metadata=metadata.model_dump(exclude_none=True),
        content=content
    )
    return WritePostResult(status="success", id=post_id)  # ✅ Opaque ID
```

#### Example: Profile Tool

**Before:**

```python
from egregora.agents.shared.profiler import read_profile

def read_profile_tool(ctx: RunContext[WriterAgentState], author_uuid: str):
    content = read_profile(author_uuid, ctx.deps.profiles_dir)  # ❌ Passes directory
    return ReadProfileResult(content=content or "No profile exists yet.")
```

**After:**

```python
def read_profile_tool(ctx: RunContext[WriterAgentState], author_uuid: str):
    content = ctx.deps.profiles.read(author_uuid)  # ✅ Uses storage protocol
    return ReadProfileResult(content=content or "No profile exists yet.")
```

#### Example: Enrichment

**Before:**

```python
# Enrichment constructs path
enrichment_id = uuid.uuid5(uuid.NAMESPACE_URL, url)
enrichment_path = docs_dir / "media" / "urls" / f"{enrichment_id}.md"  # ❌
enrichment_path.write_text(markdown, encoding="utf-8")
```

**After:**

```python
# Storage protocol handles everything
enrichment_id = context.enrichments.write_url_enrichment(url, markdown)  # ✅
```

#### Files to Update:

1. **Writer Agent** (`agents/writer/`)
   - `agent.py` → `write_post_tool`, `write_profile_tool`, journal saving
   - `handlers.py` → Handler functions

2. **Editor Agent** (`agents/editor/`)
   - `agent.py` → State initialization, profile reading

3. **Enrichment** (`enrichment/`)
   - `simple_runner.py` → URL enrichment, media enrichment writes
   - `core.py` → Context creation
   - `thin_agents.py` → Agent initialization

4. **Ranking Agent** (`agents/ranking/`)
   - `agent.py` → Config initialization

5. **Profiler** (`agents/shared/`)
   - `profiler.py` → Refactor `read_profile`, `write_profile` to be thin wrappers or remove

6. **Utilities** (`utils/`)
   - `write_post.py` → Move logic to MkDocsPostStorage or make it a thin wrapper

---

### Phase 4: Update Prompt Template System

**Goal**: Templates receive prompts directory directly (not site_root)

**Current State**: Templates accept `site_root` and internally resolve to `.egregora/prompts/`.

#### Before:

```python
@dataclass(slots=True)
class UrlEnrichmentPromptTemplate(PromptTemplate):
    url: str
    site_root: Path | None = None  # ❌ Internally constructs prompts_dir
```

#### After:

```python
@dataclass(slots=True)
class UrlEnrichmentPromptTemplate(PromptTemplate):
    url: str
    prompts_dir: Path | None = None  # ✅ Direct path (no construction)
```

**Note**: Prompts directory resolution happens at initialization time by caller:

```python
# Caller (in agent initialization)
prompts_dir = site_root / ".egregora" / "prompts" if site_root else None
template = UrlEnrichmentPromptTemplate(url=url, prompts_dir=prompts_dir)
```

Or if we create a PromptLoader protocol:

```python
class PromptLoader(Protocol):
    """Protocol for loading custom prompt templates."""

    def get_prompts_dir(self) -> Path | None:
        """Return custom prompts directory if exists."""
        ...
```

#### Files to Update:

- `src/egregora/prompt_templates.py` → All template classes
- All agent files that create templates → Pass `prompts_dir` directly

---

### Phase 5: Update Pipeline Orchestration

**Goal**: Create storage implementations at entry points, inject into contexts

#### Before (CLI):

```python
# CLI constructs paths
output_dir = Path(output)
profiles_dir = output_dir / "profiles"  # ❌
rag_dir = output_dir / ".egregora" / "rag"  # ❌

context = WriterRuntimeContext(
    output_dir=output_dir,
    profiles_dir=profiles_dir,
    rag_dir=rag_dir,
    # ...
)
```

#### After (CLI):

```python
# CLI creates storage implementations
site_root = Path(output)
posts_storage = MkDocsPostStorage(site_root)
profiles_storage = MkDocsProfileStorage(site_root)
journals_storage = MkDocsJournalStorage(site_root)

# Create stores (not from directories - from storage implementations)
rag_dir = site_root / ".egregora" / "rag"
rag_store = VectorStore(rag_dir / "chunks.parquet")

annotations_dir = site_root / ".egregora" / "annotations"
annotations_store = AnnotationStore(annotations_dir) if config.annotations_enabled else None

# Get prompts directory
prompts_dir = site_root / ".egregora" / "prompts" if (site_root / ".egregora" / "prompts").is_dir() else None

context = WriterRuntimeContext(
    posts=posts_storage,
    profiles=profiles_storage,
    journals=journals_storage,
    rag_store=rag_store,
    annotations_store=annotations_store,
    prompts_dir=prompts_dir,
    # ...
)
```

#### Files to Update:

- `src/egregora/cli.py` → All commands that run agents
- `src/egregora/pipeline/runner.py` → Pipeline orchestration functions
- Test files → Use in-memory storage implementations

---

### Phase 6: Testing Strategy

**Goal**: Comprehensive tests with in-memory storage implementations

#### Test Updates:

1. **Replace filesystem fixtures with in-memory storage**:

```python
# Before
@pytest.fixture
def output_dir(tmp_path):
    return tmp_path / "output"

# After
@pytest.fixture
def post_storage():
    return InMemoryPostStorage()

@pytest.fixture
def profile_storage():
    return InMemoryProfileStorage()
```

2. **Verify storage calls instead of filesystem checks**:

```python
# Before
def test_write_post(output_dir):
    result = write_post(content, metadata, output_dir)
    assert (output_dir / "posts" / "my-post.md").exists()  # ❌ Filesystem check

# After
def test_write_post(post_storage):
    result = write_post_tool(ctx_with_storage(post_storage), metadata, content)
    assert post_storage.exists("my-post")  # ✅ Storage protocol check
    assert "my-post" in post_storage._posts  # ✅ Direct access for testing
```

3. **Test storage implementations independently**:

```python
# Test MkDocs implementations
def test_mkdocs_post_storage(tmp_path):
    storage = MkDocsPostStorage(tmp_path)
    post_id = storage.write("test-post", {"title": "Test"}, "Content")
    assert storage.exists("test-post")
    metadata, content = storage.read("test-post")
    assert metadata["title"] == "Test"

# Test in-memory implementations
def test_memory_post_storage():
    storage = InMemoryPostStorage()
    post_id = storage.write("test-post", {"title": "Test"}, "Content")
    assert post_id == "memory://posts/test-post"
    assert storage.exists("test-post")
```

---

## Files Affected

### New Files (Create)

- `src/egregora/storage/__init__.py` → Storage protocols
- `src/egregora/storage/mkdocs.py` → MkDocs implementations
- `src/egregora/storage/memory.py` → In-memory test implementations
- `tests/storage/test_mkdocs_storage.py` → MkDocs storage tests
- `tests/storage/test_memory_storage.py` → Memory storage tests
- `tests/storage/test_protocols.py` → Protocol contract tests

### Modified Files (Update)

**Core:**
- `src/egregora/agents/writer/agent.py` → Update WriterRuntimeContext + tools
- `src/egregora/agents/writer/handlers.py` → Update tool handlers
- `src/egregora/agents/writer/core.py` → Update orchestration
- `src/egregora/agents/editor/agent.py` → Update EditorAgentState
- `src/egregora/agents/ranking/agent.py` → Update ComparisonConfig
- `src/egregora/enrichment/core.py` → Update EnrichmentRuntimeContext
- `src/egregora/enrichment/simple_runner.py` → Use EnrichmentStorage
- `src/egregora/enrichment/thin_agents.py` → Update agent creation
- `src/egregora/agents/shared/profiler.py` → Refactor or remove

**Prompts:**
- `src/egregora/prompt_templates.py` → Change site_root → prompts_dir

**Pipeline:**
- `src/egregora/cli.py` → Create storage implementations
- `src/egregora/pipeline/runner.py` → Pass storage to agents
- `src/egregora/pipeline/windowing.py` → No changes needed

**Tests:**
- `tests/agents/test_writer_pydantic_agent.py` → Use in-memory storage
- `tests/agents/test_editor_pydantic_agent.py` → Use in-memory storage
- `tests/agents/test_ranking_pydantic_agent.py` → Use in-memory storage
- `tests/integration/test_enrich_table_duckdb.py` → Use in-memory storage
- `tests/e2e/test_with_golden_fixtures.py` → May still use filesystem
- `tests/conftest.py` → Add storage fixtures

### Documentation Updates

- `CLAUDE.md` → Update architecture section, add storage protocol docs
- `docs/guides/architecture.md` → Add adapter pattern explanation
- `CONTRIBUTING.md` → Add storage implementation guide

---

## Benefits

### 1. **True Abstraction**
- Agents don't know storage implementation (filesystem, database, S3)
- String IDs work for all backends (not just filesystem paths)

### 2. **Interface Segregation**
- Writer agent only receives PostStorage + ProfileStorage + JournalStorage
- Enrichment agent only receives EnrichmentStorage
- No agent has capabilities it doesn't need

### 3. **Testability**
- In-memory storage for fast unit tests
- No filesystem operations in tests
- Easy to mock specific storage protocols

### 4. **Extensibility**
- Add DatabasePostStorage without touching agents
- Add S3PostStorage without touching agents
- Mix implementations (MkDocs posts + Database profiles)

### 5. **Maintainability**
- Clear separation: storage handles I/O, agents handle logic
- Small, focused protocols (3-4 methods each)
- Easy to understand and reason about

---

## Risks & Mitigation

### Risk 1: Breaking Changes

**Impact**: High - affects all agents
**Mitigation**:
- Phased implementation over multiple commits
- Alpha project - breaking changes acceptable
- Comprehensive test coverage before refactor

### Risk 2: Migration Complexity

**Impact**: Medium - need to update many files
**Mitigation**:
- Start with one agent (writer) as proof of concept
- Use compiler to find all usages (type checking)
- Run tests after each phase

### Risk 3: Learning Curve

**Impact**: Medium - new architecture for contributors
**Mitigation**:
- Update CLAUDE.md with clear examples
- Provide template storage implementations
- Document contracts clearly

---

## Success Criteria

### Must Have

- [ ] All storage protocols defined and documented
- [ ] MkDocs storage implementations complete
- [ ] In-memory storage implementations for testing
- [ ] Writer agent uses storage protocols (no path construction)
- [ ] All existing tests pass (with storage fixtures)
- [ ] Documentation updated

### Should Have

- [ ] All agents use storage protocols
- [ ] Enrichment pipeline uses EnrichmentStorage
- [ ] Performance benchmarks show no regression

### Nice to Have

- [ ] Database storage proof-of-concept
- [ ] S3 storage proof-of-concept
- [ ] Migration guide for custom deployments

---

## Timeline Estimate

| Phase | Estimated Time | Priority |
|-------|---------------|----------|
| Phase 1: Protocols + Implementations | 3-4 hours | P0 |
| Phase 2: Update RuntimeContexts | 2-3 hours | P0 |
| Phase 3: Update Writer Agent | 2-3 hours | P0 |
| Phase 3: Update Other Agents | 3-4 hours | P0 |
| Phase 4: Update Templates | 1-2 hours | P0 |
| Phase 5: Update Pipeline/CLI | 2-3 hours | P0 |
| Phase 6: Testing | 3-4 hours | P0 |
| Documentation | 2-3 hours | P1 |

**Total**: ~18-26 hours of focused development

---

## Next Steps

1. ✅ **Plan revised** with focused protocols, string IDs, direct store injection
2. **Start Phase 1** - Define storage protocols and implementations
3. **Verify** MkDocs storage preserves all current behavior
4. **Proceed** with Phase 2 (RuntimeContext updates)
5. **Commit after each phase** with clear messages

---

## Notes

- This refactor follows SOLID principles (especially Interface Segregation)
- No path leakage - true abstraction enables database/S3 backends
- Aligns with Phase 2-6 "MODERN" principles (alpha mindset, clean breaks)
- Makes codebase more testable and maintainable
- Enables future features: cloud deployment, hybrid storage, custom backends

---

**Author**: Claude (Revised Architecture)
**Review Status**: Ready for Implementation
**Target Version**: v0.X (next breaking release)
