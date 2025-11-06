# Complexity Reduction Plan

## Executive Summary

This document outlines a comprehensive plan to address the remaining 62 complexity-related linting errors in the Egregora codebase. The goal is to reduce cyclomatic complexity, function argument counts, statement counts, and branching logic through strategic architectural improvements and refactoring.

**Current State**: 62 complexity errors remaining after Phase 3C
**Target State**: All complexity errors resolved through systematic refactoring

## Error Breakdown

| Rule | Count | Description | Priority |
|------|-------|-------------|----------|
| **C901** | 20 | Functions too complex (> 10 cyclomatic complexity) | HIGH |
| **PLR0913** | 18 | Too many arguments (> 5 parameters) | MEDIUM |
| **PLR0915** | 14 | Too many statements (> 50 statements) | MEDIUM |
| **PLR0912** | 7 | Too many branches (> 12 branches) | HIGH |
| **PLR0911** | 3 | Too many return statements (> 6 returns) | LOW |

**Total**: 62 errors

---

## Strategic Approaches

### Approach 1: Configuration Objects Pattern
**Addresses**: PLR0913 (too many arguments)

**Problem**: Functions with 6-16 parameters become unwieldy and error-prone.

**Solution**: Group related parameters into configuration dataclasses.

**Benefits**:
- Single source of truth for related config
- Easy to add new parameters without signature changes
- Improved testability and mocking
- Better IDE autocomplete

**Example**:
```python
# Before: 14 parameters
def write_posts_with_pydantic_agent(
    prompt: str,
    model_name: str,
    period_date: str,
    output_dir: Path,
    profiles_dir: Path,
    rag_dir: Path,
    client: genai.Client,
    embedding_model: str,
    retrieval_mode: str,
    retrieval_nprobe: int | None,
    retrieval_overfetch: int | None,
    annotations_store,
    agent_model,
    register_tools: bool,
):
    ...

# After: 3 parameters
@dataclass
class WriterAgentConfig:
    """Configuration for writer agent execution."""
    model_name: str
    embedding_model: str
    retrieval_mode: str = "ann"
    retrieval_nprobe: int | None = None
    retrieval_overfetch: int | None = None
    register_tools: bool = True

@dataclass
class WriterAgentPaths:
    """File paths for writer agent I/O."""
    output_dir: Path
    profiles_dir: Path
    rag_dir: Path

def write_posts_with_pydantic_agent(
    config: WriterAgentConfig,
    paths: WriterAgentPaths,
    context: WriterAgentContext,
):
    ...
```

**Files to refactor**:
- `agents/writer/writer_agent.py` (14 params → 3 params)
- `agents/writer/core.py` (_process_tool_calls: 12 params)
- `pipeline/runner.py` (run_source_pipeline: 16 params)
- `agents/ranking/ranking_agent.py` (9 params, 7 params)
- `agents/tools/profiler.py` (7 params)
- `agents/writer/context.py` (9 params, 7 params)

---

### Approach 2: Strategy Pattern for Tool Registration
**Addresses**: C901, PLR0912 (high complexity and branching)

**Problem**: `_register_writer_tools` and `_register_editor_tools` have complex nested conditionals for tool configuration.

**Solution**: Use Strategy pattern with tool registry.

**Example**:
```python
# Before: Complex nested if/else
def _register_writer_tools(agent, enable_banner=False, enable_rag=False):
    @agent.tool
    def write_post_tool(...):
        ...

    if enable_banner:
        @agent.tool
        def generate_banner(...):
            ...

    if enable_rag:
        @agent.tool
        def search_posts(...):
            ...

        @agent.tool
        def search_media(...):
            ...

# After: Strategy-based registration
class ToolSet(Protocol):
    """Protocol for tool collections."""
    def register(self, agent: Agent) -> None:
        """Register tools with the agent."""
        ...

@dataclass
class CoreWriterTools(ToolSet):
    """Essential writer tools (always enabled)."""
    state: WriterAgentState

    def register(self, agent: Agent) -> None:
        @agent.tool
        def write_post_tool(ctx: RunContext[WriterAgentState], ...):
            ...

@dataclass
class BannerTools(ToolSet):
    """Banner generation tools (optional)."""
    generator: BannerGenerator

    def register(self, agent: Agent) -> None:
        @agent.tool
        def generate_banner(ctx: RunContext[WriterAgentState], ...):
            ...

@dataclass
class RAGTools(ToolSet):
    """RAG search tools (optional)."""
    store: VectorStore
    embedding_model: str

    def register(self, agent: Agent) -> None:
        @agent.tool
        def search_posts(...):
            ...

        @agent.tool
        def search_media(...):
            ...

def _register_writer_tools(agent: Agent, tool_sets: list[ToolSet]) -> None:
    """Register all provided tool sets."""
    for tool_set in tool_sets:
        tool_set.register(agent)
```

**Benefits**:
- Linear complexity (O(n) instead of nested conditionals)
- Each tool set is independently testable
- Easy to add new tool sets without modifying registration logic
- Clear separation of concerns

**Files to refactor**:
- `agents/writer/writer_agent.py` (_register_writer_tools: C901 14, PLR0915 77 statements)
- `agents/editor/editor_agent.py` (_register_editor_tools: C901 11)

---

### Approach 3: Pipeline Stage Decomposition
**Addresses**: C901, PLR0915, PLR0912 (high complexity, statements, branches)

**Problem**: `enrich_table`, `run_source_pipeline`, and CLI validation functions do too many things.

**Solution**: Extract sub-functions for each logical stage.

**Example - enrich_table decomposition**:
```python
# Before: 40 complexity, massive function
def enrich_table(messages_table, media_mapping, client, ...):
    # 100+ lines of:
    # - URL extraction
    # - Media extraction
    # - Batch API calls
    # - Result merging
    # - Error handling
    # - Logging
    ...

# After: Composed from focused functions
def enrich_table(messages_table, media_mapping, client, ...):
    """Orchestrate enrichment pipeline."""
    urls_to_enrich = _extract_urls_for_enrichment(messages_table)
    media_to_enrich = _extract_media_for_enrichment(messages_table, media_mapping)

    url_results = _enrich_urls_batch(urls_to_enrich, client, ...)
    media_results = _enrich_media_batch(media_to_enrich, client, ...)

    enriched_table = _merge_enrichment_results(
        messages_table,
        url_results,
        media_results
    )
    return enriched_table

def _extract_urls_for_enrichment(table: Table) -> list[URLToEnrich]:
    """Extract and deduplicate URLs needing enrichment."""
    ...

def _extract_media_for_enrichment(
    table: Table,
    media_mapping: dict[str, Path]
) -> list[MediaToEnrich]:
    """Extract media references needing enrichment."""
    ...

def _enrich_urls_batch(
    urls: list[URLToEnrich],
    client: genai.Client,
    config: EnrichmentConfig,
) -> list[URLEnrichment]:
    """Batch process URL enrichments."""
    ...

def _enrich_media_batch(
    media: list[MediaToEnrich],
    client: genai.Client,
    config: EnrichmentConfig,
) -> list[MediaEnrichment]:
    """Batch process media enrichments."""
    ...

def _merge_enrichment_results(
    original_table: Table,
    url_results: list[URLEnrichment],
    media_results: list[MediaEnrichment],
) -> Table:
    """Merge enrichment results back into table."""
    ...
```

**Benefits**:
- Each function has single responsibility
- Functions can be tested in isolation
- Easier to understand control flow
- Reusable building blocks

**Files to refactor**:
- `enrichment/core.py` (enrich_table: C901 40 **HIGHEST PRIORITY**)
- `pipeline/runner.py` (run_source_pipeline: C901 37, PLR0912 41 branches)
- `cli.py` (_validate_and_run_process: C901 14, PLR0912 13, PLR0915 57)

---

### Approach 4: Early Return Pattern
**Addresses**: PLR0911 (too many return statements)

**Problem**: Functions with 7+ return statements have complex control flow.

**Solution**: Restructure with guard clauses and early returns.

**Example**:
```python
# Before: 7 return statements scattered throughout
def deliver_media(self, media_reference, temp_dir, **kwargs):
    if not media_reference:
        return None

    zip_path = kwargs.get("zip_path")
    if not zip_path:
        return None

    if not zipfile.is_zipfile(zip_path):
        logger.error(...)
        return None

    try:
        with zipfile.ZipFile(zip_path) as zf:
            if media_reference not in zf.namelist():
                logger.warning(...)
                return None

            try:
                extracted_path = zf.extract(media_reference, temp_dir)
                return Path(extracted_path)
            except Exception as e:
                logger.error(...)
                return None
    except zipfile.BadZipFile:
        logger.error(...)
        return None

# After: Clearer flow with Result type or exceptions
@dataclass
class MediaDeliveryResult:
    """Result of media delivery attempt."""
    success: bool
    path: Path | None
    error: str | None

def deliver_media(
    self,
    media_reference: str,
    temp_dir: Path,
    **kwargs
) -> MediaDeliveryResult:
    """Deliver media file from archive."""
    # Validate inputs
    validation_error = self._validate_media_request(media_reference, kwargs)
    if validation_error:
        return MediaDeliveryResult(False, None, validation_error)

    # Extract from archive
    try:
        path = self._extract_from_archive(
            kwargs["zip_path"],
            media_reference,
            temp_dir
        )
        return MediaDeliveryResult(True, path, None)
    except MediaExtractionError as e:
        return MediaDeliveryResult(False, None, str(e))

def _validate_media_request(
    self,
    media_reference: str,
    kwargs: dict
) -> str | None:
    """Validate media delivery request. Returns error message or None."""
    if not media_reference:
        return "Empty media reference"

    if "zip_path" not in kwargs:
        return "Missing zip_path in kwargs"

    if not zipfile.is_zipfile(kwargs["zip_path"]):
        return f"Invalid ZIP file: {kwargs['zip_path']}"

    return None

def _extract_from_archive(
    self,
    zip_path: Path,
    media_reference: str,
    temp_dir: Path,
) -> Path:
    """Extract media file. Raises MediaExtractionError on failure."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            if media_reference not in zf.namelist():
                raise MediaExtractionError(
                    f"Media not found in archive: {media_reference}"
                )

            extracted_path = zf.extract(media_reference, temp_dir)
            return Path(extracted_path)
    except zipfile.BadZipFile as e:
        raise MediaExtractionError(f"Corrupt ZIP file: {e}") from e
    except OSError as e:
        raise MediaExtractionError(f"Extraction failed: {e}") from e
```

**Benefits**:
- Single return point with clear result type
- Validation logic separated from extraction logic
- Easier to understand success vs failure paths
- Better error messages

**Files to refactor**:
- `adapters/whatsapp.py` (deliver_media: PLR0911 7 returns)
- `agents/tools/rag/store.py` (search: PLR0911 7 returns)
- `ingestion/parser.py` (_resolve_message_date: PLR0911 7 returns)

---

### Approach 5: State Machine for Complex Workflows
**Addresses**: C901, PLR0912, PLR0915 (complexity, branches, statements)

**Problem**: Avatar pipeline and RAG search have complex state management.

**Solution**: Explicit state machine with clear transitions.

**Example**:
```python
from enum import Enum, auto

class AvatarProcessingState(Enum):
    """States in avatar processing workflow."""
    VALIDATING = auto()
    DOWNLOADING = auto()
    CHECKING_CONTENT = auto()
    MODERATING = auto()
    RESIZING = auto()
    SAVING = auto()
    COMPLETED = auto()
    FAILED = auto()

@dataclass
class AvatarProcessingContext:
    """Shared context for avatar processing."""
    url: str
    author_uuid: str
    output_dir: Path
    current_state: AvatarProcessingState = AvatarProcessingState.VALIDATING
    image_data: bytes | None = None
    image: Image.Image | None = None
    error: str | None = None

class AvatarStateMachine:
    """State machine for avatar processing workflow."""

    def process(self, ctx: AvatarProcessingContext) -> AvatarProcessingContext:
        """Execute state machine until terminal state."""
        while ctx.current_state not in {
            AvatarProcessingState.COMPLETED,
            AvatarProcessingState.FAILED
        }:
            handler = self._get_state_handler(ctx.current_state)
            ctx = handler(ctx)

        return ctx

    def _get_state_handler(self, state: AvatarProcessingState):
        """Get handler function for current state."""
        handlers = {
            AvatarProcessingState.VALIDATING: self._validate_url,
            AvatarProcessingState.DOWNLOADING: self._download_image,
            AvatarProcessingState.CHECKING_CONTENT: self._check_content,
            AvatarProcessingState.MODERATING: self._moderate_content,
            AvatarProcessingState.RESIZING: self._resize_image,
            AvatarProcessingState.SAVING: self._save_avatar,
        }
        return handlers[state]

    def _validate_url(self, ctx: AvatarProcessingContext) -> AvatarProcessingContext:
        """Validate URL and transition to DOWNLOADING or FAILED."""
        try:
            _validate_url_for_ssrf(ctx.url)
            ctx.current_state = AvatarProcessingState.DOWNLOADING
        except AvatarProcessingError as e:
            ctx.error = str(e)
            ctx.current_state = AvatarProcessingState.FAILED
        return ctx

    # Similar for other states...
```

**Benefits**:
- Explicit state representation
- Each state handler is focused
- Easy to add logging/metrics per state
- Testable state transitions
- Clear error handling

**Files to refactor**:
- `enrichment/avatar_pipeline.py` (_process_set_avatar_command: C901 18, PLR0912 21, PLR0915 61)
- `enrichment/avatar.py` (download_avatar_from_url: C901 18, PLR0912 19, PLR0915 75)
- `enrichment/avatar.py` (extract_avatar_from_zip: C901 14, PLR0912 14, PLR0915 52)

---

### Approach 6: Query Object Pattern for RAG Search
**Addresses**: C901, PLR0913, PLR0915 (complexity in search function)

**Problem**: `VectorStore.search()` has 21 cyclomatic complexity, 10 parameters, 77 statements.

**Solution**: Query builder pattern with fluent interface.

**Example**:
```python
@dataclass
class RAGQuery:
    """Fluent builder for RAG search queries."""
    query_text: str
    top_k: int = 10
    min_similarity: float = 0.7
    media_types: list[str] | None = None
    date_range: tuple[date, date] | None = None
    author_filter: list[str] | None = None
    content_filter: str | None = None

    # Search strategy config
    mode: Literal["ann", "exact"] = "ann"
    nprobe: int | None = None
    overfetch: int | None = None

    def with_media_types(self, types: list[str]) -> RAGQuery:
        """Filter by media types."""
        return replace(self, media_types=types)

    def with_date_range(self, start: date, end: date) -> RAGQuery:
        """Filter by date range."""
        return replace(self, date_range=(start, end))

    def with_author_filter(self, authors: list[str]) -> RAGQuery:
        """Filter by authors."""
        return replace(self, author_filter=authors)

    def exact_search(self) -> RAGQuery:
        """Use exact (brute-force) search instead of ANN."""
        return replace(self, mode="exact")

    def ann_search(self, nprobe: int | None = None) -> RAGQuery:
        """Use ANN search with optional nprobe tuning."""
        return replace(self, mode="ann", nprobe=nprobe)

class VectorStore:
    def search(self, query: RAGQuery) -> Table:
        """Execute RAG query and return results."""
        # Build query in stages
        results = self._embed_and_search(query)
        results = self._apply_filters(results, query)
        results = self._rank_and_limit(results, query)
        return results

    def _embed_and_search(self, query: RAGQuery) -> Table:
        """Get initial candidates via vector search."""
        embedding = self._embed_text(query.query_text)

        if query.mode == "exact":
            return self._exact_search(embedding, query.overfetch or query.top_k)
        else:
            return self._ann_search(
                embedding,
                query.overfetch or (query.top_k * DEFAULT_OVERFETCH),
                query.nprobe
            )

    def _apply_filters(self, results: Table, query: RAGQuery) -> Table:
        """Apply post-search filters."""
        if query.media_types:
            results = self._filter_media_types(results, query.media_types)

        if query.date_range:
            results = self._filter_date_range(results, *query.date_range)

        if query.author_filter:
            results = self._filter_authors(results, query.author_filter)

        return results

    def _rank_and_limit(self, results: Table, query: RAGQuery) -> Table:
        """Rank by similarity and limit to top_k."""
        results = results.filter(
            results.similarity >= query.min_similarity
        )
        results = results.order_by(results.similarity.desc())
        results = results.limit(query.top_k)
        return results

# Usage becomes much clearer
query = (
    RAGQuery("search for cat memes")
    .with_media_types(["image"])
    .with_date_range(date(2025, 1, 1), date(2025, 1, 31))
    .ann_search(nprobe=15)
)
results = store.search(query)
```

**Benefits**:
- Composable, fluent API
- Each method is simple
- Easy to test filters independently
- Query object is serializable
- Clear separation of query building vs execution

**Files to refactor**:
- `agents/tools/rag/store.py` (search: C901 21, PLR0913 10, PLR0915 77 **HIGH PRIORITY**)

---

### Approach 7: Visitor Pattern for Complex Parsing
**Addresses**: C901, PLR0912 (complexity in parser)

**Problem**: `parse_multiple` has 15 complexity and 16 branches due to error handling.

**Solution**: Visitor pattern for processing each export.

**Example**:
```python
class ExportProcessor(Protocol):
    """Protocol for processing individual exports."""
    def process(self, export: WhatsAppExport) -> Table | None:
        """Process export, return table or None on failure."""
        ...

class StandardExportProcessor:
    """Standard export processing with error handling."""

    def __init__(self, timezone: str | ZoneInfo | None = None):
        self.timezone = timezone
        self.errors: list[tuple[Path, Exception]] = []

    def process(self, export: WhatsAppExport) -> Table | None:
        """Process single export, tracking errors."""
        try:
            return self._parse_export(export)
        except ZipValidationError as e:
            logger.warning("Skipping %s: %s", export.zip_path.name, e)
            self.errors.append((export.zip_path, e))
            return None
        except Exception as e:
            logger.error("Failed to process %s: %s", export.zip_path.name, e)
            self.errors.append((export.zip_path, e))
            return None

    def _parse_export(self, export: WhatsAppExport) -> Table:
        """Parse export, may raise exceptions."""
        with zipfile.ZipFile(export.zip_path) as zf:
            validate_zip_contents(zf)
            ensure_safe_member_size(zf, export.chat_file)

            with zf.open(export.chat_file) as raw:
                text_stream = io.TextIOWrapper(raw, encoding="utf-8")
                rows = _parse_messages(text_stream, export, self.timezone)

        if not rows:
            return ibis.memtable([])

        messages = ibis.memtable(rows)
        messages = messages.order_by("timestamp")
        return messages

def parse_multiple(
    exports: Sequence[WhatsAppExport],
    timezone: str | ZoneInfo | None = None
) -> Table:
    """Parse and concatenate multiple exports."""
    processor = StandardExportProcessor(timezone)

    # Process all exports
    tables = [
        table
        for export in exports
        if (table := processor.process(export)) is not None
    ]

    if not tables:
        return ibis.memtable([], schema=MESSAGE_SCHEMA)

    # Combine and finalize
    combined = _combine_tables(tables)
    combined = _add_message_ids(combined)
    combined = ensure_message_schema(combined, timezone=timezone)
    return anonymize_table(combined)

def _combine_tables(tables: list[Table]) -> Table:
    """Combine tables with proper ordering."""
    combined = tables[0]
    for table in tables[1:]:
        combined = combined.union(table, distinct=False)
    return combined.order_by("timestamp")
```

**Benefits**:
- Separation of concerns (processing vs combining)
- Error collection for reporting
- Easier to add alternative processors (e.g., parallel processing)
- Testable in isolation

**Files to refactor**:
- `ingestion/parser.py` (parse_multiple: C901 15, PLR0912 16)

---

## Implementation Roadmap

### Phase 1: Configuration Objects (Week 1)
**Impact**: Reduces 18 PLR0913 errors

1. Create config dataclasses:
   - `WriterAgentConfig`, `WriterAgentPaths`, `WriterAgentContext`
   - `PipelineConfig`, `PipelinePaths`
   - `EnrichmentConfig`
   - `RAGConfig`

2. Refactor function signatures:
   - `write_posts_with_pydantic_agent` (14 params → 3)
   - `run_source_pipeline` (16 params → 4)
   - `_process_tool_calls` (12 params → 3)

3. Update all callers to use config objects

4. Run full test suite

**Deliverable**: Config objects PR with all PLR0913 errors resolved

---

### Phase 2: Tool Registration Refactor (Week 2)
**Impact**: Reduces 2 C901 errors (complexity 14, 11)

1. Define `ToolSet` protocol

2. Create tool set implementations:
   - `CoreWriterTools`
   - `BannerTools`
   - `RAGTools`
   - `AnnotationTools`
   - `ProfileTools`

3. Refactor `_register_writer_tools` and `_register_editor_tools`

4. Run agent tests

**Deliverable**: Tool registration PR

---

### Phase 3: Pipeline Decomposition (Week 3)
**Impact**: Reduces 3 C901 errors (complexity 40, 37, 14)

1. **Enrichment decomposition** (`enrich_table`):
   - Extract `_extract_urls_for_enrichment`
   - Extract `_extract_media_for_enrichment`
   - Extract `_enrich_urls_batch`
   - Extract `_enrich_media_batch`
   - Extract `_merge_enrichment_results`

2. **Runner decomposition** (`run_source_pipeline`):
   - Extract `_validate_pipeline_inputs`
   - Extract `_setup_pipeline_directories`
   - Extract `_execute_pipeline_stages`
   - Extract `_handle_pipeline_errors`

3. **CLI decomposition** (`_validate_and_run_process`):
   - Extract `_validate_process_config`
   - Extract `_setup_pipeline_components`
   - Extract `_run_pipeline`

**Deliverable**: Pipeline decomposition PR

---

### Phase 4: Avatar State Machine (Week 4)
**Impact**: Reduces 3 C901 errors (complexity 18, 18, 14)

1. Define `AvatarProcessingState` enum

2. Create `AvatarStateMachine` class

3. Implement state handlers:
   - `_validate_url`
   - `_download_image`
   - `_check_content`
   - `_moderate_content`
   - `_resize_image`
   - `_save_avatar`

4. Refactor:
   - `download_avatar_from_url`
   - `extract_avatar_from_zip`
   - `_process_set_avatar_command`

**Deliverable**: Avatar refactor PR

---

### Phase 5: RAG Query Object (Week 5)
**Impact**: Reduces 1 C901 error (complexity 21)

1. Create `RAGQuery` builder class

2. Extract search components:
   - `_embed_and_search`
   - `_apply_filters`
   - `_rank_and_limit`
   - `_filter_media_types`
   - `_filter_date_range`
   - `_filter_authors`

3. Refactor `VectorStore.search()`

4. Update all RAG callers

**Deliverable**: RAG refactor PR

---

### Phase 6: Parser & Misc (Week 6)
**Impact**: Resolves remaining C901, PLR0911, PLR0915 errors

1. Visitor pattern for `parse_multiple`

2. Early return pattern for:
   - `deliver_media`
   - `_resolve_message_date`

3. Extract helper functions for remaining PLR0915 (too many statements)

**Deliverable**: Parser refactor PR

---

## Testing Strategy

For each refactoring phase:

1. **Before refactoring**:
   - Run full test suite (baseline)
   - Document current test coverage
   - Create additional tests for edge cases

2. **During refactoring**:
   - Run tests after each extraction
   - Use property-based testing for equivalence
   - Add unit tests for new functions

3. **After refactoring**:
   - Run full test suite (must pass)
   - Verify test coverage hasn't decreased
   - Add integration tests if needed

4. **Regression testing**:
   - Run against golden fixtures
   - Compare output with pre-refactor version
   - Check performance hasn't regressed

---

## Success Metrics

| Metric | Before | Target |
|--------|--------|--------|
| C901 violations | 20 | 0 |
| PLR0913 violations | 18 | 0 |
| PLR0915 violations | 14 | 0 |
| PLR0912 violations | 7 | 0 |
| PLR0911 violations | 3 | 0 |
| **Total complexity errors** | **62** | **0** |
| Test coverage | ~85% | ≥85% |
| Integration test pass rate | 100% | 100% |

---

## Risks & Mitigations

### Risk 1: Breaking Changes
**Mitigation**:
- Comprehensive test suite before starting
- Incremental refactoring with frequent test runs
- Golden fixture comparison for output validation

### Risk 2: Performance Regression
**Mitigation**:
- Benchmark critical paths before/after
- Profile for hotspots
- Use caching where appropriate

### Risk 3: Increased Boilerplate
**Mitigation**:
- Use dataclasses for config objects (minimal boilerplate)
- Protocols instead of ABCs where possible
- Type aliases for complex signatures

### Risk 4: Scope Creep
**Mitigation**:
- Strict adherence to 6-week roadmap
- Focus on linting errors only
- Defer non-critical refactoring

---

## Conclusion

This plan addresses all 62 remaining complexity errors through systematic, testable refactoring. The key strategies are:

1. **Configuration objects** → Reduce parameter counts
2. **Strategy pattern** → Simplify tool registration
3. **Function extraction** → Reduce complexity and statement counts
4. **State machines** → Clarify complex workflows
5. **Query objects** → Simplify search logic
6. **Visitor pattern** → Improve parser structure

Each phase is independently deliverable and testable. The entire refactoring can be completed in 6 weeks with minimal risk to existing functionality.

**Next Step**: Begin Phase 1 (Configuration Objects) after approval of this plan.
