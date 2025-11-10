# Adapter Pattern Refactoring Plan

**Status**: Planning
**Date**: 2025-01-10
**Scope**: Major architectural refactor to decouple agents from I/O structure

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
3. **Testing complexity** - Hard to test with mock file systems
4. **Violates SOLID** - Agents have too many responsibilities

### Where Decisions Are Made Today

| Decision | Current Location | Should Be |
|----------|------------------|-----------|
| Post directory structure | Writer agent | Output adapter |
| Profile directory structure | Profiler tool | Output adapter |
| Media enrichment paths | Enrichment runner | Output adapter |
| Prompt template paths | Template system | Output adapter |
| Journal paths | Writer agent | Output adapter |
| Cache directory | Multiple places | Configuration |
| Rankings directory | Ranking agent | Output adapter |

---

## Solution: Adapter Pattern

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
┌─────────────────────┐
│   Output Adapter    │  (MkDocs, Database, S3)
│ - write_post()      │
│ - write_profile()   │
│ - get_prompts_dir() │
└─────────────────────┘
```

### Key Principles

1. **Agents are pure** - No path construction, no I/O decisions
2. **Adapters own structure** - All directory layouts decided by adapters
3. **Dependency injection** - Adapters passed into runtime contexts
4. **Interface-based** - Protocols define adapter contracts

---

## Implementation Plan

### Phase 1: Define Adapter Protocols

**Goal**: Create abstract interfaces that adapters must implement

#### File: `src/egregora/adapters/__init__.py`

```python
from typing import Protocol
from pathlib import Path
from ibis.expr.types import Table

class SourceAdapter(Protocol):
    """Adapter for reading conversation data from various sources."""

    def get_messages(self, start: datetime, end: datetime) -> Table:
        """Retrieve messages within time window."""
        ...

    def get_media_path(self, filename: str) -> Path:
        """Resolve media file path from filename."""
        ...

    def get_source_metadata(self) -> dict[str, Any]:
        """Return source-specific metadata."""
        ...


class OutputAdapter(Protocol):
    """Adapter for writing outputs to various destinations."""

    # Post operations
    def write_post(self, slug: str, metadata: dict, content: str) -> Path:
        """Write post to output, return resolved path."""
        ...

    def get_posts_dir(self) -> Path:
        """Return directory where posts are stored."""
        ...

    # Profile operations
    def write_profile(self, uuid: str, content: str) -> Path:
        """Write profile to output, return resolved path."""
        ...

    def read_profile(self, uuid: str) -> str | None:
        """Read profile content by UUID."""
        ...

    def get_profiles_dir(self) -> Path:
        """Return directory where profiles are stored."""
        ...

    # Enrichment operations
    def write_url_enrichment(self, url: str, content: str) -> Path:
        """Write URL enrichment, return resolved path."""
        ...

    def write_media_enrichment(self, filename: str, content: str) -> Path:
        """Write media enrichment, return resolved path."""
        ...

    def get_media_urls_dir(self) -> Path:
        """Return directory for URL enrichments."""
        ...

    # Journal operations
    def write_journal(self, window_label: str, content: str) -> Path:
        """Write journal entry for window."""
        ...

    def get_journal_dir(self) -> Path:
        """Return directory for journal entries."""
        ...

    # Prompt operations
    def get_prompts_dir(self) -> Path | None:
        """Return custom prompts directory if exists."""
        ...

    # RAG operations
    def get_rag_dir(self) -> Path:
        """Return RAG vector store directory."""
        ...

    # Annotations
    def get_annotations_dir(self) -> Path:
        """Return annotations storage directory."""
        ...

    # Rankings
    def get_rankings_dir(self) -> Path:
        """Return rankings storage directory."""
        ...
```

#### File: `src/egregora/adapters/mkdocs.py`

```python
class MkDocsOutputAdapter:
    """Output adapter for MkDocs static site structure.

    Structure:
        site_root/
        ├── posts/              # Blog posts
        ├── profiles/           # Author profiles
        ├── docs/
        │   └── media/
        │       ├── urls/       # URL enrichments
        │       └── <files>     # Media enrichments
        ├── journal/            # Agent journals
        ├── .egregora/
        │   ├── prompts/        # Custom prompts (optional)
        │   ├── rag/            # Vector store
        │   └── annotations/    # Annotations
        └── rankings/           # Elo rankings
    """

    def __init__(self, site_root: Path):
        self.site_root = site_root
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        for dir_path in [
            self.get_posts_dir(),
            self.get_profiles_dir(),
            self.get_media_urls_dir(),
            self.get_journal_dir(),
            self.get_rag_dir(),
            self.get_annotations_dir(),
            self.get_rankings_dir(),
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

    # Posts
    def write_post(self, slug: str, metadata: dict, content: str) -> Path:
        path = self.get_posts_dir() / f"{slug}.md"
        # Write with frontmatter + content
        full_content = f"---\n{yaml.dump(metadata)}---\n\n{content}"
        path.write_text(full_content, encoding="utf-8")
        return path

    def get_posts_dir(self) -> Path:
        return self.site_root / "posts"

    # Profiles
    def write_profile(self, uuid: str, content: str) -> Path:
        path = self.get_profiles_dir() / f"{uuid}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def read_profile(self, uuid: str) -> str | None:
        path = self.get_profiles_dir() / f"{uuid}.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def get_profiles_dir(self) -> Path:
        return self.site_root / "profiles"

    # Enrichment
    def write_url_enrichment(self, url: str, content: str) -> Path:
        enrichment_id = uuid.uuid5(uuid.NAMESPACE_URL, url)
        path = self.get_media_urls_dir() / f"{enrichment_id}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def write_media_enrichment(self, filename: str, content: str) -> Path:
        # Media enrichment goes next to the media file with .md extension
        media_path = self.site_root / "docs" / filename
        enrichment_path = media_path.with_suffix(media_path.suffix + ".md")
        enrichment_path.write_text(content, encoding="utf-8")
        return enrichment_path

    def get_media_urls_dir(self) -> Path:
        return self.site_root / "docs" / "media" / "urls"

    # Journal
    def write_journal(self, window_label: str, content: str) -> Path:
        # Convert window label to filename-safe format
        safe_label = window_label.replace(" ", "_").replace(":", "-")
        path = self.get_journal_dir() / f"journal_{safe_label}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def get_journal_dir(self) -> Path:
        return self.site_root / "journal"

    # Prompts
    def get_prompts_dir(self) -> Path | None:
        prompts_dir = self.site_root / ".egregora" / "prompts"
        return prompts_dir if prompts_dir.is_dir() else None

    # RAG
    def get_rag_dir(self) -> Path:
        return self.site_root / ".egregora" / "rag"

    # Annotations
    def get_annotations_dir(self) -> Path:
        return self.site_root / ".egregora" / "annotations"

    # Rankings
    def get_rankings_dir(self) -> Path:
        return self.site_root / "rankings"
```

#### File: `src/egregora/adapters/whatsapp.py`

```python
class WhatsAppSourceAdapter:
    """Source adapter for WhatsApp chat exports."""

    def __init__(self, export_path: Path, media_mapping: dict[str, Path]):
        self.export_path = export_path
        self.media_mapping = media_mapping
        self._messages: Table | None = None

    def get_messages(self, start: datetime, end: datetime) -> Table:
        """Retrieve messages within time window."""
        if self._messages is None:
            # Parse WhatsApp export
            from egregora.sources.whatsapp.parser import parse_source
            self._messages = parse_source(self.export_path)

        # Filter by time window
        return self._messages.filter(
            (self._messages.timestamp >= start) &
            (self._messages.timestamp < end)
        )

    def get_media_path(self, filename: str) -> Path:
        """Resolve media file path from filename."""
        return self.media_mapping.get(filename) or Path(filename)

    def get_source_metadata(self) -> dict[str, Any]:
        return {
            "source_type": "whatsapp",
            "export_path": str(self.export_path),
            "media_files": len(self.media_mapping),
        }
```

---

### Phase 2: Update Runtime Contexts

**Goal**: Replace path fields with adapter references

#### Before (example from `WriterRuntimeContext`):

```python
@dataclass(frozen=True, slots=True)
class WriterRuntimeContext:
    start_time: datetime
    end_time: datetime
    output_dir: Path          # ❌ Agent constructs paths from this
    profiles_dir: Path        # ❌ Agent constructs paths from this
    rag_dir: Path            # ❌ Agent constructs paths from this
    site_root: Path | None   # ❌ Agent constructs .egregora/prompts
    client: Any
    annotations_store: AnnotationStore | None = None
```

#### After:

```python
@dataclass(frozen=True, slots=True)
class WriterRuntimeContext:
    start_time: datetime
    end_time: datetime
    output: OutputAdapter     # ✅ Adapter provides all paths
    client: Any
    annotations_store: AnnotationStore | None = None
```

#### Files to Update:

- `src/egregora/agents/writer/writer_agent.py` → `WriterRuntimeContext`
- `src/egregora/agents/editor/editor_agent.py` → `EditorAgentState`
- `src/egregora/enrichment/core.py` → `EnrichmentRuntimeContext`
- `src/egregora/agents/ranking/ranking_agent.py` → `ComparisonConfig`

---

### Phase 3: Update Agents to Use Adapters

**Goal**: Replace all path construction with adapter calls

#### Example: Writer Agent

**Before:**

```python
# Writer agent constructs path
def write_post_tool(ctx: RunContext[WriterAgentState], metadata: PostMetadata, content: str):
    path = write_post(
        content=content,
        metadata=metadata.model_dump(exclude_none=True),
        output_dir=ctx.deps.output_dir  # ❌
    )
    return WritePostResult(status="success", path=path)
```

**After:**

```python
# Adapter handles path resolution
def write_post_tool(ctx: RunContext[WriterAgentState], metadata: PostMetadata, content: str):
    path = ctx.deps.output.write_post(
        slug=metadata.slug,
        metadata=metadata.model_dump(exclude_none=True),
        content=content
    )
    return WritePostResult(status="success", path=path)
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
# Adapter handles everything
enrichment_path = context.output.write_url_enrichment(url, markdown)  # ✅
```

#### Files to Update:

1. **Writer Agent** (`agents/writer/`)
   - `writer_agent.py` → `write_post_tool`, `write_profile_tool`, journal saving
   - `tools.py` → All tool implementations

2. **Editor Agent** (`agents/editor/`)
   - `editor_agent.py` → State initialization, profile reading

3. **Enrichment** (`enrichment/`)
   - `simple_runner.py` → URL enrichment, media enrichment writes
   - `core.py` → Context creation

4. **Ranking Agent** (`agents/ranking/`)
   - `ranking_agent.py` → Config initialization, prompt template resolution

5. **Profiler** (`agents/tools/`)
   - `profiler.py` → `read_profile`, `write_profile`

6. **Utilities** (`utils/`)
   - `write_post.py` → Refactor to accept adapter or move logic to adapter

---

### Phase 4: Update Prompt Template System

**Goal**: Templates accept `prompts_dir` instead of `site_root`

#### Before:

```python
@dataclass(slots=True)
class UrlEnrichmentPromptTemplate(PromptTemplate):
    url: str
    site_root: Path | None = None  # ❌ Template constructs .egregora/prompts

    def render(self) -> str:
        return self._render(site_root=self.site_root, url=self.url)
```

#### After:

```python
@dataclass(slots=True)
class UrlEnrichmentPromptTemplate(PromptTemplate):
    url: str
    prompts_dir: Path | None = None  # ✅ Direct path from adapter

    def render(self) -> str:
        return self._render(prompts_dir=self.prompts_dir, url=self.url)
```

#### Files to Update:

- `src/egregora/prompt_templates.py` → All template classes
- Template rendering logic to use `prompts_dir` directly

---

### Phase 5: Update Pipeline Orchestration

**Goal**: Create adapters at entry points, pass through pipeline

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
# CLI creates adapter
output_adapter = MkDocsOutputAdapter(site_root=Path(output))  # ✅
source_adapter = WhatsAppSourceAdapter(export_path, media_mapping)  # ✅

context = WriterRuntimeContext(
    output=output_adapter,
    source=source_adapter,
    # ...
)
```

#### Files to Update:

- `src/egregora/cli.py` → All commands that run agents
- `src/egregora/pipeline.py` → Pipeline orchestration functions
- Test files → Use mock adapters

---

### Phase 6: Testing Strategy

**Goal**: Comprehensive tests with mock adapters

#### Mock Adapters for Testing:

```python
class MemoryOutputAdapter:
    """In-memory output adapter for testing."""

    def __init__(self):
        self.posts: dict[str, tuple[dict, str]] = {}
        self.profiles: dict[str, str] = {}
        self.enrichments: dict[str, str] = {}
        self.journals: dict[str, str] = {}

    def write_post(self, slug: str, metadata: dict, content: str) -> Path:
        self.posts[slug] = (metadata, content)
        return Path(f"/memory/posts/{slug}.md")

    def get_posts_dir(self) -> Path:
        return Path("/memory/posts")

    # ... other methods store in memory
```

#### Test Updates:

1. Replace all `tmp_path` fixtures with `MemoryOutputAdapter`
2. Verify adapter calls instead of filesystem checks
3. Test adapter implementations independently

---

## Files Affected

### New Files (Create)

- `src/egregora/adapters/__init__.py` → Protocols
- `src/egregora/adapters/mkdocs.py` → MkDocs adapter
- `src/egregora/adapters/whatsapp.py` → WhatsApp adapter
- `src/egregora/adapters/memory.py` → Test adapter
- `tests/adapters/test_mkdocs_adapter.py` → Adapter tests
- `tests/adapters/test_memory_adapter.py` → Test helper tests

### Modified Files (Update)

**Core:**
- `src/egregora/agents/writer/writer_agent.py`
- `src/egregora/agents/writer/tools.py`
- `src/egregora/agents/editor/editor_agent.py`
- `src/egregora/agents/ranking/ranking_agent.py`
- `src/egregora/enrichment/core.py`
- `src/egregora/enrichment/simple_runner.py`
- `src/egregora/enrichment/thin_agents.py`
- `src/egregora/enrichment/agents.py`
- `src/egregora/agents/tools/profiler.py`
- `src/egregora/utils/write_post.py`

**Prompts:**
- `src/egregora/prompt_templates.py`

**Pipeline:**
- `src/egregora/cli.py`
- `src/egregora/pipeline.py`

**Tests:**
- `tests/agents/test_writer_pydantic_agent.py`
- `tests/agents/test_editor_pydantic_agent.py`
- `tests/agents/test_ranking_pydantic_agent.py`
- `tests/integration/test_enrich_table_duckdb.py`
- `tests/e2e/test_with_golden_fixtures.py`
- `tests/conftest.py` → Add adapter fixtures

### Documentation Updates

- `CLAUDE.md` → Update architecture section
- `docs/guides/architecture.md` → Add adapter pattern docs
- `CONTRIBUTING.md` → Add adapter development guide

---

## Benefits

### 1. **Decoupling**
- Agents don't know about filesystem structure
- Easy to swap MkDocs → Database → S3

### 2. **Testability**
- In-memory adapters for fast tests
- Mock adapters for unit tests
- No filesystem operations needed

### 3. **Extensibility**
- Add new output formats without touching agents
- Add new source formats without touching pipeline
- Plugin architecture for custom adapters

### 4. **Maintainability**
- Single responsibility - adapters handle I/O, agents handle logic
- Clear interfaces via Protocols
- Easier to reason about code

### 5. **Flexibility**
- Different projects can use different adapters
- Hybrid approaches (MkDocs + Database)
- Cloud-native deployments (S3, GCS)

---

## Risks & Mitigation

### Risk 1: Breaking Changes

**Impact**: High - affects all agents
**Mitigation**:
- Phase implementation over multiple PRs
- Maintain backward compatibility temporarily
- Comprehensive test coverage before refactor
- Use feature flags for gradual rollout

### Risk 2: Performance

**Impact**: Medium - extra abstraction layer
**Mitigation**:
- Profile before/after with benchmarks
- Optimize hot paths (batch writes)
- Use caching where appropriate

### Risk 3: Test Complexity

**Impact**: Low - need to rewrite many tests
**Mitigation**:
- Create helper fixtures for common adapters
- Document testing patterns
- Provide examples in tests/

### Risk 4: Learning Curve

**Impact**: Medium - new architecture for contributors
**Mitigation**:
- Update CLAUDE.md with clear examples
- Add architecture diagrams
- Provide template adapters

---

## Migration Path

### Alpha Mindset

**This is an alpha project** - we can make breaking changes for better architecture.

### Compatibility Strategy

**Option A: Clean Break (Recommended)**
- Refactor everything in one go
- Update all tests
- Ship as v0.X with migration guide

**Option B: Gradual Migration**
- Add adapter layer alongside existing code
- Migrate one agent at a time
- Remove old code when all agents migrated

**Recommendation**: Option A (clean break)
- Faster development
- Cleaner codebase
- Alpha project expectations

---

## Success Criteria

### Must Have

- [ ] All agents use adapters (no path construction)
- [ ] MkDocsOutputAdapter maintains current behavior
- [ ] All existing tests pass (with adapter fixtures)
- [ ] Documentation updated

### Should Have

- [ ] MemoryOutputAdapter for testing
- [ ] Performance benchmarks show no regression
- [ ] Example custom adapter in docs

### Nice to Have

- [ ] Database adapter proof-of-concept
- [ ] S3 adapter proof-of-concept
- [ ] Migration script for custom deployments

---

## Timeline Estimate

| Phase | Estimated Time | Priority |
|-------|---------------|----------|
| Phase 1: Protocols | 2-3 hours | P0 |
| Phase 2: Contexts | 1-2 hours | P0 |
| Phase 3: Agents | 4-6 hours | P0 |
| Phase 4: Templates | 1-2 hours | P0 |
| Phase 5: Pipeline | 2-3 hours | P0 |
| Phase 6: Testing | 3-4 hours | P0 |
| Documentation | 2-3 hours | P1 |

**Total**: ~15-23 hours of focused development

---

## Next Steps

1. **Review this plan** with maintainer
2. **Get approval** for clean break approach
3. **Create implementation branch** `refactor/adapter-pattern`
4. **Implement Phase 1** (protocols + MkDocs adapter)
5. **Verify** MkDocs adapter preserves all current behavior
6. **Proceed** with remaining phases sequentially

---

## Notes

- This refactor aligns with Phase 2-6 "MODERN" principles (alpha mindset, clean breaks)
- Completes separation of concerns started in earlier phases
- Enables future features: cloud deployment, multiple sources, custom outputs
- Makes codebase more testable and maintainable

---

**Author**: Claude
**Review Status**: Pending
**Target Version**: v0.X (next breaking release)
