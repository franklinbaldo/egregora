# Code Quality Refactoring: Fix Code Smells & Technical Debt

## Executive Summary

This PR addresses **9 validated code smells** across the core pipeline that create maintenance burden, reduce testability, and violate SOLID principles. The refactoring focuses on **writer.py**, **write_pipeline.py**, **mkdocs/adapter.py**, and **duckdb_manager.py**.

**Impact:** Improved testability, reduced coupling, eliminated duplication, better separation of concerns.

**Scope:** ~500 lines changed across 4 core files, with comprehensive test coverage.

---

## Problems Identified

### 🔴 Critical Issues (Must Fix)

#### 1. **Inner Function Abuse in Writer Agent** (`src/egregora/agents/writer.py`)

**Location:** Lines 206-352 (`register_writer_tools`)

**Problem:**
```python
def register_writer_tools(agent: Agent, ...):
    @agent.tool
    def write_post_tool(ctx, metadata, content):  # Cannot test in isolation!
        # 40 lines of logic

    @agent.tool
    def read_profile_tool(ctx, author_uuid):  # Cannot reuse in other agents!
        # ...

    @agent.tool
    def search_media_tool(ctx, query, top_k):  # Cannot mock for unit tests!
        # 50 lines of logic
```

**Why it's bad:**
- **Zero testability** - Cannot unit test tools without full agent setup
- **No reusability** - Other agents cannot share these tools
- **Tight coupling** - Tools know about `RunContext` internals
- **Hard to mock** - Integration tests must mock entire agent machinery

**Fix:** Extract tools as standalone functions that accept explicit dependencies

---

#### 2. **God Method in Pipeline Orchestration** (`src/egregora/orchestration/write_pipeline.py`)

**Location:** Lines 1364-1454 (`run` function - 90 lines)

**Problem:**
```python
def run(run_params: PipelineRunParams) -> dict[str, dict[str, list[str]]]:
    # Adapter instantiation (10 lines)
    # Run tracking setup (8 lines)
    # Database initialization (15 lines)
    # Data preparation (12 lines)
    # Window processing (20 lines)
    # Media indexing (10 lines)
    # Checkpoint saving (8 lines)
    # Statistics generation (7 lines)
    # Error handling (15 lines)
```

**Why it's bad:**
- **Cyclomatic complexity** - Too many responsibilities
- **Hard to test** - Must mock 8+ dependencies
- **Hard to understand** - Requires reading 90 lines to grasp flow
- **High coupling** - Changes to any stage require touching this function

**Fix:** Extract helper methods for each major step

---

#### 3. **Manual YAML Frontmatter Construction** (`src/egregora/output_adapters/mkdocs/adapter.py`)

**Location:** Lines 763+, 789+, 838+ (4 methods)

**Problem:**
```python
def _write_post_doc(self, document, path):
    import yaml as _yaml
    metadata = dict(document.metadata or {})
    metadata["date"] = _format_frontmatter_datetime(metadata["date"])  # Custom logic
    yaml_front = _yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
    full_content = f"---\n{yaml_front}---\n\n{document.content}"  # Brittle!
    path.write_text(full_content)
```

**Duplicated in:** `_write_journal_doc`, `_write_profile_doc`, `_write_enrichment_doc`

**Why it's bad:**
- **Code duplication** - Same pattern repeated 4 times
- **Brittle string construction** - Manual `"---\n{yaml}---\n\n{content}"`
- **Asymmetry** - Uses `parse_frontmatter` library for reading, manual code for writing
- **Parameter repetition** - `default_flow_style=False, allow_unicode=True, sort_keys=False` everywhere

**Fix:** Use `python-frontmatter` library consistently for both reading and writing

---

### 🟡 High Priority Issues

#### 4. **Deep Parameter Lists** (`src/egregora/agents/writer.py`)

**Location:** Line 674 (`_save_journal_to_file` - 8 parameters)

**Problem:**
```python
def _save_journal_to_file(
    intercalated_log: list[JournalEntry],
    window_label: str,
    output_format: OutputSink,
    posts_published: int,
    profiles_updated: int,
    window_start: datetime,
    window_end: datetime,
    total_tokens: int = 0,
) -> str | None:
```

**Why it's bad:**
- **Data clump smell** - These parameters travel together
- **Cognitive load** - Hard to remember parameter order
- **Error-prone** - Easy to swap parameters of same type

**Fix:** Introduce `JournalContext` dataclass

---

#### 5. **Control Flag Antipattern** (`src/egregora/orchestration/write_pipeline.py`)

**Location:** Line 1179 (`_apply_filters` with `checkpoint_enabled: bool`)

**Problem:**
```python
def _apply_filters(
    messages_table,
    ctx,
    from_date,
    to_date,
    checkpoint_path,
    checkpoint_enabled: bool = False,  # Control flag!
):
    # ... filtering logic ...

    if checkpoint_enabled:  # Branch 1 - resume logic (30 lines)
        checkpoint = load_checkpoint(checkpoint_path)
        # ...
    else:  # Branch 2 - full rebuild (10 lines)
        logger.info("Full rebuild")
```

**Why it's bad:**
- **Function does two things** - Resume logic vs. full rebuild
- **Violates SRP** - Single Responsibility Principle
- **Hard to test** - Must test both branches

**Fix:** Split into `_apply_base_filters` and `_apply_resume_filter`

---

#### 6. **Feature Envy** (`src/egregora/orchestration/write_pipeline.py`)

**Location:** Lines 111-141 in `process_whatsapp_export`

**Problem:**
```python
models_update = {
    "writer": opts.model,      # Reaching into opts
    "enricher": opts.model,    # Reaching into opts
    "enricher_vision": opts.model,  # Reaching into opts
    "ranking": opts.model,
    "editor": opts.model,
}

egregora_config = base_config.model_copy(
    deep=True,
    update={
        "pipeline": base_config.pipeline.model_copy(  # Deep reach
            update={
                "step_size": opts.step_size,  # Reaching into opts
                "step_unit": opts.step_unit,  # Reaching into opts
                "overlap_ratio": opts.overlap_ratio,  # Reaching into opts
                # ... 10 more fields
            }
        ),
        # ... 3 more nested sections
    },
)
```

**Why it's bad:**
- **Tight coupling** - Function knows internal structure of config
- **Fragile** - Breaks if config structure changes
- **Violation of LoD** - Law of Demeter violation

**Fix:** Add `WhatsAppProcessOptions.to_config_overrides()` method

---

### 🟢 Medium Priority Issues

#### 7. **Tight Coupling to Formatting** (`src/egregora/agents/writer.py`)

**Location:** Lines 38-39

**Problem:**
```python
from egregora.agents.formatting import (
    _build_conversation_xml,  # Writer shouldn't know about XML formatting
    _load_journal_memory,     # Writer shouldn't know about journal storage
)
```

**Why it's bad:**
- **Violates SRP** - Writer agent knows about data formatting
- **Hard to change formats** - XML format hardcoded
- **Tight coupling** - Cannot swap formatters

**Fix:** Inject formatter as dependency via `WriterResources`

---

#### 8. **Magic Strings in Return Types** (`src/egregora/agents/writer.py`)

**Location:** Lines 84-86, 1144

**Problem:**
```python
RESULT_KEY_POSTS = "posts"       # Constants defined
RESULT_KEY_PROFILES = "profiles"

# But used in untyped dict:
return {
    RESULT_KEY_POSTS: saved_posts,      # No type safety!
    RESULT_KEY_PROFILES: saved_profiles,
}  # Type: dict[str, list[str]]
```

**Why it's bad:**
- **No type safety** - Easy to typo keys
- **No IDE support** - No autocomplete
- **Runtime errors** - Typos discovered at runtime

**Fix:** Use Pydantic model `WriterResult(posts=[...], profiles=[...])`

---

#### 9. **Mixed Abstraction Levels** (`src/egregora/database/duckdb_manager.py`)

**Location:** Entire class (647 lines)

**Problem:** Single class handles:
- Connection management (lines 112-120)
- SQL execution (lines 184-217)
- Table I/O (lines 241-313)
- Atomic persistence (lines 315-347)
- Sequence management (lines 376-458)
- Vector search (lines 542-593)
- Cache management (lines 349-372)

**Why it's bad:**
- **God class** - Too many responsibilities
- **Violates SRP** - 7 distinct concerns
- **Hard to test** - Complex setup for each test
- **High coupling** - Every change risks breaking 7 features

**Fix:** Extract specialized managers (VectorManager, SequenceManager)

---

## Refactoring Strategy

### Phase 1: Writer Agent Testability (Priority: CRITICAL)

**Goal:** Extract agent tools to standalone, testable functions

#### 1.1 Extract Tool Functions to New Module

**Create:** `src/egregora/agents/writer_tools.py`

```python
"""Standalone tool functions for the writer agent.

These can be tested independently and reused by other agents.
"""

from dataclasses import dataclass
from pathlib import Path
from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import OutputSink


@dataclass(frozen=True)
class PostToolContext:
    """Context for post writing tool."""
    output_sink: OutputSink
    window_label: str


def write_post(
    ctx: PostToolContext,
    metadata: dict,
    content: str,
) -> dict:
    """Write a blog post document.

    Pure function - easy to test, mock, and reuse.

    Args:
        ctx: Tool context with dependencies
        metadata: Post metadata (title, slug, date, etc.)
        content: Post markdown content

    Returns:
        Result dict with status and path
    """
    doc = Document(
        content=content,
        type=DocumentType.POST,
        metadata=metadata,
        source_window=ctx.window_label,
    )
    ctx.output_sink.persist(doc)
    return {"status": "success", "path": doc.document_id}


def read_profile(ctx: PostToolContext, author_uuid: str) -> dict:
    """Read an author profile.

    Pure function - easy to test with mock output_sink.
    """
    doc = ctx.output_sink.read_document(DocumentType.PROFILE, author_uuid)
    content = doc.content if doc else "No profile exists yet."
    return {"content": content}


# ... similar for search_media, write_profile, etc.
```

**Then update `writer.py`:**

```python
from egregora.agents.writer_tools import (
    PostToolContext,
    write_post,
    read_profile,
    write_profile,
    search_media,
)


def register_writer_tools(agent: Agent, ...):
    """Register tools as thin wrappers around pure functions."""

    @agent.tool
    def write_post_tool(ctx: RunContext[WriterDeps], metadata: dict, content: str):
        tool_ctx = PostToolContext(
            output_sink=ctx.deps.resources.output,
            window_label=ctx.deps.window_label,
        )
        return write_post(tool_ctx, metadata, content)

    @agent.tool
    def read_profile_tool(ctx: RunContext[WriterDeps], author_uuid: str):
        tool_ctx = PostToolContext(
            output_sink=ctx.deps.resources.output,
            window_label=ctx.deps.window_label,
        )
        return read_profile(tool_ctx, author_uuid)

    # ... similar for other tools (now just 3 lines each)
```

**Benefits:**
- ✅ Pure functions are easily unit tested
- ✅ Can reuse tools in other agents
- ✅ Can mock dependencies without Pydantic-AI machinery
- ✅ Clear separation between tool logic and agent registration

**Files Changed:**
- `src/egregora/agents/writer_tools.py` (+150 lines, new file)
- `src/egregora/agents/writer.py` (-140 lines, +40 lines = -100 net)
- `tests/unit/agents/test_writer_tools.py` (+200 lines, new file)

---

#### 1.2 Introduce JournalContext Dataclass

**Before:**
```python
def _save_journal_to_file(
    intercalated_log: list[JournalEntry],
    window_label: str,
    output_format: OutputSink,
    posts_published: int,
    profiles_updated: int,
    window_start: datetime,
    window_end: datetime,
    total_tokens: int = 0,
) -> str | None:
```

**After:**
```python
@dataclass(frozen=True)
class JournalContext:
    """Encapsulates all data needed to save a journal entry."""

    intercalated_log: list[JournalEntry]
    window_label: str
    window_start: datetime
    window_end: datetime
    posts_published: int
    profiles_updated: int
    total_tokens: int
    output_format: OutputSink


def _save_journal_to_file(ctx: JournalContext) -> str | None:
    """Save journal entry to markdown file."""
    # ... implementation uses ctx.intercalated_log, ctx.window_label, etc.
```

**Usage:**
```python
# Caller constructs context once
journal_ctx = JournalContext(
    intercalated_log=intercalated_log,
    window_label=deps.window_label,
    window_start=deps.window_start,
    window_end=deps.window_end,
    posts_published=len(saved_posts),
    profiles_updated=len(saved_profiles),
    total_tokens=result.usage().total_tokens,
    output_format=deps.resources.output,
)

# Clean call
_save_journal_to_file(journal_ctx)
```

**Benefits:**
- ✅ Single parameter instead of 8
- ✅ Immutable context (frozen dataclass)
- ✅ Named fields (no positional argument confusion)
- ✅ Easy to extend (add field without changing signature)

**Files Changed:**
- `src/egregora/agents/writer.py:609` (add JournalContext dataclass)
- `src/egregora/agents/writer.py:674` (update function signature)
- `src/egregora/agents/writer.py:912` (update call site)

---

#### 1.3 Use Pydantic Model for Return Values

**Before:**
```python
RESULT_KEY_POSTS = "posts"
RESULT_KEY_PROFILES = "profiles"

return {RESULT_KEY_POSTS: saved_posts, RESULT_KEY_PROFILES: saved_profiles}
# Type: dict[str, list[str]]  # No type safety!
```

**After:**
```python
from pydantic import BaseModel

class WriterResult(BaseModel):
    """Type-safe result from writer agent."""

    posts: list[str] = Field(default_factory=list, description="Post document IDs")
    profiles: list[str] = Field(default_factory=list, description="Profile document IDs")


def write_posts_for_window(...) -> WriterResult:
    # ...
    return WriterResult(posts=saved_posts, profiles=saved_profiles)
```

**Benefits:**
- ✅ Type safety (IDE autocomplete)
- ✅ Validation (Pydantic ensures lists)
- ✅ Documentation (Field descriptions)
- ✅ Serialization (automatic JSON/dict conversion)

**Files Changed:**
- `src/egregora/agents/writer.py:149` (add WriterResult model)
- `src/egregora/agents/writer.py:1150` (update return type)
- `src/egregora/agents/writer.py:1144` (return WriterResult instance)
- `src/egregora/orchestration/write_pipeline.py:257` (update usage)

---

### Phase 2: Pipeline Orchestration Simplification (Priority: CRITICAL)

**Goal:** Break down God method into testable, focused functions

#### 2.1 Extract Pipeline Steps

**Before:**
```python
def run(run_params: PipelineRunParams) -> dict:
    # 90 lines of mixed responsibilities
```

**After:**
```python
def run(run_params: PipelineRunParams) -> WriterResult:
    """Orchestrate pipeline workflow - delegates to specialized functions."""

    adapter = _create_adapter(run_params)
    run_id, started_at = run_params.run_id, run_params.start_time

    with _pipeline_environment(run_params) as (ctx, runs_backend):
        run_store = _create_run_store(runs_backend)
        _record_run_start(run_store, run_id, started_at)

        try:
            results = _execute_pipeline_stages(adapter, run_params, ctx)
            _record_run_completion(run_store, run_id, started_at, results)
            logger.info("[green]Pipeline completed successfully![/]")
            return results
        except Exception as exc:
            _record_run_failure(run_store, run_id, started_at, exc)
            raise


def _execute_pipeline_stages(
    adapter: InputAdapter,
    run_params: PipelineRunParams,
    ctx: PipelineContext,
) -> WriterResult:
    """Execute all pipeline stages in sequence."""

    dataset = _prepare_pipeline_data(adapter, run_params, ctx)
    results, max_timestamp = _process_all_windows(dataset.windows_iterator, dataset.context)
    _index_media_into_rag(dataset, results)
    _save_checkpoint(results, max_timestamp, dataset.checkpoint_path)
    _generate_statistics_page(dataset.messages_table, dataset.context)

    return results
```

**Benefits:**
- ✅ Main function is 15 lines (was 90)
- ✅ Each helper has single responsibility
- ✅ Easy to test helpers independently
- ✅ Clear pipeline flow

**Files Changed:**
- `src/egregora/orchestration/write_pipeline.py:1364-1454` (split into 4 functions)

---

#### 2.2 Eliminate Control Flag

**Before:**
```python
def _apply_filters(
    messages_table,
    ctx,
    from_date,
    to_date,
    checkpoint_path,
    checkpoint_enabled: bool = False,  # Flag!
):
    # ... base filtering (30 lines)

    if checkpoint_enabled:  # Resume branch (30 lines)
        # ...
    else:  # Full rebuild branch (5 lines)
        # ...
```

**After:**
```python
def _apply_base_filters(
    messages_table: Table,
    ctx: PipelineContext,
    from_date: date | None,
    to_date: date | None,
) -> Table:
    """Apply base filters: egregora messages, opted-out users, date range."""

    # Filter egregora messages
    messages_table, egregora_removed = filter_egregora_messages(messages_table)
    if egregora_removed:
        logger.info("Removed %s /egregora messages", egregora_removed)

    # Filter opted-out authors
    messages_table, removed_count = filter_opted_out_authors(messages_table, ctx.profiles_dir)
    if removed_count > 0:
        logger.warning("%s messages removed from opted-out users", removed_count)

    # Date range filtering
    if from_date or to_date:
        messages_table = _apply_date_range_filter(messages_table, from_date, to_date)

    return messages_table


def _apply_resume_filter(
    messages_table: Table,
    checkpoint_path: Path,
) -> Table:
    """Apply checkpoint-based resume filter (incremental processing)."""

    checkpoint = load_checkpoint(checkpoint_path)
    if not checkpoint or "last_processed_timestamp" not in checkpoint:
        logger.info("Starting fresh (checkpoint enabled, but no checkpoint found)")
        return messages_table

    last_timestamp = datetime.fromisoformat(checkpoint["last_processed_timestamp"])
    # ... resume logic (30 lines)
    return messages_table


# Caller decides which filters to apply
def _prepare_pipeline_data(...):
    # ...
    messages_table = _apply_base_filters(messages_table, ctx, from_date, to_date)

    if config.pipeline.checkpoint_enabled:
        messages_table = _apply_resume_filter(messages_table, checkpoint_path)
    else:
        logger.info("Full rebuild (checkpoint disabled)")
    # ...
```

**Benefits:**
- ✅ Each function has single responsibility
- ✅ No control flags
- ✅ Easy to test base filters without resume logic
- ✅ Easy to test resume logic in isolation

**Files Changed:**
- `src/egregora/orchestration/write_pipeline.py:1179` (split into 2 functions)
- `src/egregora/orchestration/write_pipeline.py:974` (update caller)

---

#### 2.3 Fix Feature Envy with Options Method

**Before:**
```python
# In process_whatsapp_export function
models_update = {
    "writer": opts.model,
    "enricher": opts.model,
    # ... reaching into opts repeatedly
}

egregora_config = base_config.model_copy(
    deep=True,
    update={
        "pipeline": base_config.pipeline.model_copy(
            update={
                "step_size": opts.step_size,
                "step_unit": opts.step_unit,
                # ... 10 more fields from opts
            }
        ),
        # ... 3 more nested sections
    },
)
```

**After:**
```python
# In WhatsAppProcessOptions dataclass
def to_config_overrides(self) -> dict[str, Any]:
    """Convert options to config overrides dict.

    Encapsulates knowledge of config structure.
    """
    overrides = {}

    # Model overrides (if provided)
    if self.model:
        overrides["models"] = {
            "writer": self.model,
            "enricher": self.model,
            "enricher_vision": self.model,
            "ranking": self.model,
            "editor": self.model,
        }

    # Pipeline overrides
    overrides["pipeline"] = {
        "step_size": self.step_size,
        "step_unit": self.step_unit,
        "overlap_ratio": self.overlap_ratio,
        "timezone": str(self.timezone) if self.timezone else None,
        "from_date": self.from_date.isoformat() if self.from_date else None,
        "to_date": self.to_date.isoformat() if self.to_date else None,
        "batch_threshold": self.batch_threshold,
        "max_prompt_tokens": self.max_prompt_tokens,
        "use_full_context_window": self.use_full_context_window,
    }

    # Enrichment overrides
    overrides["enrichment"] = {"enabled": self.enable_enrichment}

    return overrides


# In process_whatsapp_export function
def process_whatsapp_export(...):
    opts = options or WhatsAppProcessOptions()
    base_config = load_egregora_config(opts.output_dir)

    # Clean, single responsibility
    egregora_config = base_config.model_copy(deep=True, update=opts.to_config_overrides())
    # ...
```

**Benefits:**
- ✅ Options knows its own structure (LoD)
- ✅ Easy to change config structure (encapsulation)
- ✅ Cleaner orchestration code
- ✅ Testable conversion logic

**Files Changed:**
- `src/egregora/orchestration/write_pipeline.py:74` (add method to WhatsAppProcessOptions)
- `src/egregora/orchestration/write_pipeline.py:111-141` (simplify to 3 lines)

---

### Phase 3: Frontmatter Library Integration (Priority: HIGH)

**Goal:** Eliminate brittle YAML construction, use `python-frontmatter` consistently

#### 3.1 Install python-frontmatter Dependency

**Add to `pyproject.toml`:**
```toml
[project]
dependencies = [
    # ... existing deps ...
    "python-frontmatter>=1.1.0",
]
```

**Run:**
```bash
uv sync
```

---

#### 3.2 Replace Manual YAML Construction

**Before (`_write_post_doc`, `_write_journal_doc`, `_write_profile_doc`, `_write_enrichment_doc`):**
```python
def _write_post_doc(self, document: Document, path: Path) -> None:
    import yaml as _yaml
    metadata = dict(document.metadata or {})
    metadata["date"] = _format_frontmatter_datetime(metadata["date"])
    if "authors" in metadata:
        _ensure_author_entries(path.parent, metadata.get("authors"))

    yaml_front = _yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=False)
    full_content = f"---\n{yaml_front}---\n\n{document.content}"
    path.write_text(full_content, encoding="utf-8")
```

**After:**
```python
import frontmatter


def _write_post_doc(self, document: Document, path: Path) -> None:
    metadata = self._prepare_post_metadata(document.metadata)
    post = frontmatter.Post(document.content, **metadata)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")


def _prepare_post_metadata(self, metadata: dict) -> dict:
    """Prepare metadata for post documents (hook for customization)."""
    prepared = dict(metadata or {})

    # Format date
    if "date" in prepared:
        prepared["date"] = _format_frontmatter_datetime(prepared["date"])

    # Ensure authors exist in .authors.yml
    if "authors" in prepared:
        _ensure_author_entries(self.posts_dir.parent, prepared["authors"])

    return prepared
```

**Similar for journal, profile, enrichment:**
```python
def _write_journal_doc(self, document: Document, path: Path) -> None:
    metadata = self._ensure_hidden(document.metadata.copy())
    post = frontmatter.Post(document.content, **metadata)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")


def _write_profile_doc(self, document: Document, path: Path) -> None:
    metadata = self._prepare_profile_metadata(document.metadata)
    post = frontmatter.Post(document.content, **metadata)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")


def _write_enrichment_doc(self, document: Document, path: Path) -> None:
    metadata = self._prepare_enrichment_metadata(document.metadata, document)
    post = frontmatter.Post(document.content, **metadata)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
```

**Benefits:**
- ✅ Eliminates 4 instances of manual `f"---\n{yaml}---\n\n{content}"`
- ✅ Removes repeated YAML dump parameters
- ✅ Symmetry with parsing (same lib for read/write)
- ✅ Handles edge cases (multiline values, special chars)
- ✅ Reduces code by ~30 lines

**Files Changed:**
- `pyproject.toml` (+1 line)
- `src/egregora/output_adapters/mkdocs/adapter.py:763` (`_write_post_doc`)
- `src/egregora/output_adapters/mkdocs/adapter.py:789` (`_write_journal_doc`)
- `src/egregora/output_adapters/mkdocs/adapter.py:797` (`_write_profile_doc`)
- `src/egregora/output_adapters/mkdocs/adapter.py:838` (`_write_enrichment_doc`)

---

### Phase 4: Decouple Writer from Formatting (Priority: MEDIUM)

**Goal:** Inject formatter instead of importing specific implementations

#### 4.1 Create Formatter Protocol

**Create:** `src/egregora/agents/formatting_protocol.py`

```python
from typing import Protocol, runtime_checkable
from ibis.expr.types import Table


@runtime_checkable
class ConversationFormatter(Protocol):
    """Protocol for formatting conversation data for LLMs."""

    def format_conversation(
        self,
        messages: Table,
        annotations_store: AnnotationStore | None = None,
    ) -> str:
        """Format messages table into prompt-ready string."""
        ...


@runtime_checkable
class JournalLoader(Protocol):
    """Protocol for loading journal history."""

    def load_journal_memory(self, output_sink: OutputSink) -> str:
        """Load recent journal entries as context."""
        ...
```

---

#### 4.2 Update WriterResources

**Before:**
```python
@dataclass(frozen=True)
class WriterResources:
    # ... existing fields ...
```

**After:**
```python
@dataclass(frozen=True)
class WriterResources:
    # ... existing fields ...

    # NEW: Formatters as dependencies
    conversation_formatter: ConversationFormatter
    journal_loader: JournalLoader
```

---

#### 4.3 Update Writer to Use Injected Formatters

**Before:**
```python
from egregora.agents.formatting import (
    _build_conversation_xml,
    _load_journal_memory,
)

def _build_writer_context(...):
    conversation_xml = _build_conversation_xml(messages_table, resources.annotations_store)
    journal_memory = _load_journal_memory(resources.output)
    # ...
```

**After:**
```python
def _build_writer_context(...):
    conversation_xml = resources.conversation_formatter.format_conversation(
        messages_table,
        resources.annotations_store,
    )
    journal_memory = resources.journal_loader.load_journal_memory(resources.output)
    # ...
```

**Benefits:**
- ✅ No import coupling to specific implementations
- ✅ Easy to swap formatters (XML → JSON → custom)
- ✅ Easy to mock formatters in tests
- ✅ Writer focused on writing, not formatting

**Files Changed:**
- `src/egregora/agents/formatting_protocol.py` (+30 lines, new file)
- `src/egregora/agents/writer.py:156` (add fields to WriterResources)
- `src/egregora/agents/writer.py:38-39` (remove imports)
- `src/egregora/agents/writer.py:534` (use injected formatter)
- `src/egregora/agents/writer.py:548` (use injected journal loader)
- `src/egregora/orchestration/factory.py` (inject default implementations)

---

### Phase 5: Split DuckDBStorageManager (Priority: LOW)

**Goal:** Extract specialized managers to reduce God class complexity

**Note:** This is a larger refactoring with lower priority. Recommend separate PR.

**Approach:**
1. Extract `SequenceManager` (lines 376-458)
2. Extract `VectorManager` (lines 542-593)
3. Keep `DuckDBStorageManager` focused on core table I/O

**Files Created:**
- `src/egregora/database/sequence_manager.py` (+100 lines)
- `src/egregora/database/vector_manager.py` (+80 lines)

**Files Changed:**
- `src/egregora/database/duckdb_manager.py` (-180 lines)

**Defer to separate PR** - Not blocking for this refactoring.

---

## Implementation Plan

### Week 1: Writer Agent Testability

- [x] Day 1: Extract tool functions to `writer_tools.py` (Phase 1.1)
- [x] Day 2: Write unit tests for extracted tools
- [x] Day 3: Introduce `JournalContext` dataclass (Phase 1.2)
- [x] Day 4: Introduce `WriterResult` Pydantic model (Phase 1.3)
- [x] Day 5: Test and verify writer changes

### Week 2: Pipeline Orchestration

- [ ] Day 1: Extract pipeline stages from `run()` (Phase 2.1)
- [ ] Day 2: Eliminate control flag in filters (Phase 2.2)
- [ ] Day 3: Add `to_config_overrides()` method (Phase 2.3)
- [ ] Day 4: Test orchestration changes
- [ ] Day 5: Buffer/catch-up

### Week 3: Frontmatter & Formatting

- [ ] Day 1: Install `python-frontmatter`, update adapter (Phase 3.1-3.2)
- [ ] Day 2: Test frontmatter changes
- [ ] Day 3: Create formatter protocols (Phase 4.1)
- [ ] Day 4: Inject formatters into writer (Phase 4.2-4.3)
- [ ] Day 5: Final testing and verification

---

## Success Criteria

1. **Writer Agent Testability:**
   - ✅ All tools extracted to standalone functions
   - ✅ 90%+ test coverage on `writer_tools.py`
   - ✅ No more than 8 parameters per function
   - ✅ Type-safe return values (Pydantic models)

2. **Pipeline Simplification:**
   - ✅ Main `run()` function < 20 lines
   - ✅ No control flags in function signatures
   - ✅ Each helper function tests independently
   - ✅ Config overrides encapsulated in options

3. **Frontmatter Consistency:**
   - ✅ `python-frontmatter` used for all YAML operations
   - ✅ No manual `f"---\n{yaml}---\n\n{content}"` construction
   - ✅ Symmetric read/write (same library)
   - ✅ Tests verify frontmatter parsing

4. **Decoupled Formatting:**
   - ✅ Writer uses protocol dependencies
   - ✅ No direct imports of formatting implementations
   - ✅ Easy to mock formatters in tests

5. **Test Coverage:**
   - ✅ All refactored code has unit tests
   - ✅ Integration tests updated
   - ✅ No regression in existing tests
   - ✅ Coverage maintained or improved

---

## Files Modified Summary

| File | Changes | Lines |
|------|---------|-------|
| `src/egregora/agents/writer_tools.py` | New file | +150 |
| `src/egregora/agents/writer.py` | Extract tools, add models | -100 |
| `src/egregora/agents/formatting_protocol.py` | New file | +30 |
| `src/egregora/orchestration/write_pipeline.py` | Split God method | -60, +40 |
| `src/egregora/output_adapters/mkdocs/adapter.py` | Use frontmatter lib | -30, +20 |
| `pyproject.toml` | Add dependency | +1 |
| `tests/unit/agents/test_writer_tools.py` | New file | +200 |
| `tests/unit/agents/test_writer.py` | Update for new structure | +50 |
| `tests/unit/orchestration/test_write_pipeline.py` | Test extracted helpers | +100 |
| **Total** | **9 files** | **~350 net lines** |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking writer tests | Low | High | Comprehensive test coverage before refactoring |
| Frontmatter library incompatibility | Low | Medium | Test with existing golden fixtures |
| Pipeline refactoring introduces bugs | Medium | High | Extract incrementally, test each stage |
| Performance regression | Low | Low | Benchmark before/after |

---

## Rollback Plan

1. **Immediate:** Git revert to previous commit
2. **Phase-by-phase:** Each phase is independent; can roll back partial changes
3. **Feature flags:** Keep old implementations temporarily behind config flags
4. **Parallel implementation:** Run old and new side-by-side during transition

---

## Additional Code Smells to Fix Opportunistically

While working on the primary issues, fix these if encountered:

1. **Async/Sync Mixing** - `enricher.py` (not fully analyzed yet)
2. **In-Memory Materialization** - Table iteration patterns
3. **Excessive Exception Catching** - Broad `except Exception` blocks
4. **Duplicate Code** - Similar patterns across modules

---

## References

- **Clean Code** by Robert C. Martin (Uncle Bob)
- **Refactoring** by Martin Fowler
- **SOLID Principles** - Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion
- **Design Patterns** - Gang of Four (Strategy, Factory)

---

## PR Checklist

- [ ] All extracted functions have docstrings with examples
- [ ] `python-frontmatter` dependency added and tested
- [ ] All direct tool functions have unit tests (90%+ coverage)
- [ ] Pipeline helpers tested independently
- [ ] No control flags in function signatures
- [ ] Type-safe return values (Pydantic models)
- [ ] Full test suite passes (`pytest tests/`)
- [ ] No new warnings or errors
- [ ] Pre-commit hooks pass
- [ ] Code review requested
- [ ] CI/CD pipeline passes
