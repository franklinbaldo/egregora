# Codebase Duplication Reduction Plan

This document outlines strategies to reduce duplication across the Egregora codebase. Each section addresses a specific duplication pattern identified during analysis.

## Overview

| # | Duplication Area | Priority | Effort | Risk |
|---|-----------------|----------|--------|------|
| 1 | Triple Truth of Database Schemas | High | Medium | Low |
| 2 | Configuration Mirroring | Medium | Medium | Medium |
| 3 | Prompt Template Classes | Low | Low | Low |
| 4 | Enrichment Control Flow | Medium | High | Medium |
| 5 | Output Adapter Storage Logic | Low | Medium | Low |
| 6 | Message Schema Definitions | High | Low | Low |
| 7 | Tool Definitions Patterns | Low | Low | Low |

---

## 1. Triple Truth of Database Schemas

### Current State

The `runs` table schema exists in three places:
- `schema/runs_v1.sql` - SQL DDL with documentation
- `src/egregora/database/ir_schema.py:RUNS_TABLE_DDL` - Python string copy
- `src/egregora/database/ir_schema.py:RUNS_TABLE_SCHEMA` - Ibis schema

### Problem

Manual synchronization is error-prone. The SQL file even admits: "Single source of truth: src/egregora/database/ir_schema.py:RUNS_TABLE_DDL"

### Solution: Delete `schema/runs_v1.sql`

**Rationale**: Since Python is already the canonical source, the SQL file is pure documentation that can drift. The `RUNS_TABLE_DDL` string in Python serves the same purpose.

**Action Items**:
1. Delete `schema/runs_v1.sql`
2. Move important documentation comments into the Python module docstring
3. Keep `RUNS_TABLE_DDL` as the executable source
4. Keep `RUNS_TABLE_SCHEMA` for Ibis operations

**Alternative Considered**: Generate SQL from Ibis schema programmatically. However, this adds complexity and the current `_ibis_to_duckdb_type()` function already handles this for table creation.

---

## 2. Configuration Mirroring (Pydantic vs Dataclasses)

### Current State

`PipelineSettings` (Pydantic, persisted) and `ProcessConfig` (dataclass, runtime) duplicate many fields:
- `step_size`, `step_unit`, `overlap_ratio`
- `from_date`, `to_date`, `timezone`
- `max_prompt_tokens`, `use_full_context_window`
- `max_windows`, `checkpoint_enabled`

### Problem

When adding a new pipeline parameter, you must update both classes and the copying code in `write_pipeline.py`.

### Solution: Make `ProcessConfig` derive from `PipelineSettings`

**Strategy**: Create `ProcessConfig` as a composition that wraps `PipelineSettings` plus runtime-only fields.

```python
@dataclass
class ProcessConfig:
    """Runtime configuration for processing."""

    # Required runtime fields (not in PipelineSettings)
    output_dir: Path
    input_file: Path | None = None
    gemini_key: str | None = None
    debug: bool = False

    # Pipeline settings (from config file)
    pipeline: PipelineSettings = field(default_factory=PipelineSettings)

    # Convenience properties that delegate to pipeline
    @property
    def step_size(self) -> int:
        return self.pipeline.step_size

    @property
    def step_unit(self) -> WindowUnit:
        return self.pipeline.step_unit

    # ... etc
```

**Action Items**:
1. Refactor `ProcessConfig` to contain a `PipelineSettings` instance
2. Add `@property` delegates for commonly accessed fields
3. Update `write_pipeline.py` to pass through settings directly
4. Remove manual field copying

**Benefits**:
- Single definition of pipeline parameters
- Type safety preserved
- Runtime-only fields clearly separated

---

## 3. Prompt Template Classes

### Current State

Six nearly identical dataclass templates in `prompt_templates.py`:
- `UrlEnrichmentPromptTemplate`
- `MediaEnrichmentPromptTemplate`
- `DetailedUrlEnrichmentPromptTemplate`
- `DetailedMediaEnrichmentPromptTemplate`
- `AvatarEnrichmentPromptTemplate`
- `WriterPromptTemplate`

Each follows the pattern:
1. Inherit from `PromptTemplate`
2. Define `template_name`
3. Define dataclass fields
4. Implement `render()` that calls `self._render(**fields)`

### Problem

Adding a new template requires copying boilerplate. The only differences are template name and fields.

### Solution: Generic Template Factory

**Strategy**: Create a factory function that generates template classes dynamically.

```python
def create_prompt_template(
    template_name: str,
    fields: dict[str, tuple[type, Any]],  # field_name -> (type, default)
) -> type[PromptTemplate]:
    """Create a prompt template class dynamically."""

    @dataclass(slots=True)
    class GeneratedTemplate(PromptTemplate):
        template_name: ClassVar[str] = template_name
        prompts_dir: Path | None = None
        env: Environment | None = None

        def render(self) -> str:
            context = {k: getattr(self, k) for k in fields}
            return self._render(env=self.env, prompts_dir=self.prompts_dir, **context)

    # Add fields dynamically
    for name, (field_type, default) in fields.items():
        setattr(GeneratedTemplate, name, default)

    return GeneratedTemplate

# Usage
UrlEnrichmentPromptTemplate = create_prompt_template(
    "url_detailed.jinja",
    {"url": (str, ...)}
)
```

**Alternative (Simpler)**: Keep existing classes but use a mixin or decorator to reduce boilerplate.

**Action Items**:
1. Create `GenericPromptTemplate` class with dynamic field handling
2. Migrate simple templates (URL, Media) to use generic approach
3. Keep complex templates (Writer) as explicit classes
4. Update tests

**Decision**: Low priority - current duplication is manageable and explicit classes provide good IDE support.

---

## 4. Enrichment Control Flow

### Current State

`_enrich_urls()` and `_enrich_media()` in `runners.py` share ~80% identical algorithm:
1. Iterate over message batches
2. Extract references (URLs or media filenames)
3. Check enrichment limit
4. Check cache
5. Run agent if not cached
6. Create enrichment row

### Problem

Bug fixes or algorithm changes must be applied to both functions. The functions are 100+ lines each.

### Solution: Extract Common Pipeline Pattern

**Strategy**: Create a generic enrichment pipeline that accepts strategy objects.

```python
@dataclass
class EnrichmentStrategy:
    """Strategy for extracting and processing enrichments."""

    name: str  # "URL" or "Media"

    def extract_references(self, message: str) -> list[str]:
        """Extract references from message text."""
        raise NotImplementedError

    def get_cache_key(self, reference: str) -> str:
        """Generate cache key for a reference."""
        raise NotImplementedError

    def process(self, reference: str, agent: Any, cache: EnrichmentCache) -> tuple[str | None, str]:
        """Process a single reference, return (enrichment_id, content)."""
        raise NotImplementedError


def _enrich_generic(
    messages_table: Table,
    strategy: EnrichmentStrategy,
    agent: Any,
    cache: EnrichmentCache,
    context: EnrichmentRuntimeContext,
    prompts_dir: Path | None,
    max_enrichments: int,
    start_count: int = 0,
) -> list[dict[str, Any]]:
    """Generic enrichment pipeline."""
    new_rows: list[dict[str, Any]] = []
    metadata_lookup: dict[str, dict[str, Any]] = {}

    # Phase 1: Collect references and metadata
    for batch in _iter_table_record_batches(messages_table.select(...)):
        for row in batch:
            message = row.get("text")
            if not message:
                continue

            refs = strategy.extract_references(message)
            # ... store metadata for each ref

    # Phase 2: Process references
    for ref in sorted_refs[:max_enrichments - start_count]:
        enrichment_id, content = strategy.process(ref, agent, cache)
        if enrichment_id:
            row = _create_enrichment_row(metadata_lookup[ref], strategy.name, ref, enrichment_id)
            if row:
                new_rows.append(row)

    return new_rows
```

**Action Items**:
1. Define `EnrichmentStrategy` protocol/base class
2. Implement `UrlEnrichmentStrategy` and `MediaEnrichmentStrategy`
3. Create generic `_enrich_generic()` function
4. Refactor `_enrich_urls()` and `_enrich_media()` to use strategies
5. Update tests

**Benefits**:
- Single algorithm to maintain
- Easy to add new enrichment types (e.g., code blocks, mentions)
- Better testability (mock strategies)

---

## 5. Output Adapter Storage Logic

### Current State

`MkDocsAdapter.list_documents()` and `HugoOutputAdapter.list_documents()` have nearly identical filesystem scanning logic:
- Iterate directories (posts, profiles, media)
- Get relative paths and mtimes
- Build Ibis table

### Problem

Adding a new output adapter requires copying 50+ lines of filesystem scanning code.

### Solution: Base Class with Template Method

**Strategy**: Extract common logic to `OutputAdapter` base class.

```python
class OutputAdapter(ABC):
    """Base output adapter with common filesystem operations."""

    def list_documents(self) -> Table:
        """List all documents as Ibis table."""
        if self._site_root is None:
            return self._empty_document_table()

        documents = []
        for dir_config in self._get_document_directories():
            documents.extend(self._scan_directory(**dir_config))

        return ibis.memtable(documents, schema=self._document_schema())

    @abstractmethod
    def _get_document_directories(self) -> list[dict]:
        """Return list of directories to scan with patterns.

        Example return:
        [
            {"path": self.posts_dir, "pattern": "*.md"},
            {"path": self.profiles_dir, "pattern": "*.md"},
        ]
        """
        pass

    def _scan_directory(self, path: Path, pattern: str) -> list[dict]:
        """Scan a directory for documents."""
        if not path.exists():
            return []

        results = []
        for file_path in path.glob(pattern):
            if file_path.is_file():
                try:
                    relative = str(file_path.relative_to(self._site_root))
                    mtime_ns = file_path.stat().st_mtime_ns
                    results.append({"storage_identifier": relative, "mtime_ns": mtime_ns})
                except (OSError, ValueError):
                    continue
        return results
```

**Action Items**:
1. Add `_scan_directory()` helper to `OutputAdapter` base
2. Add `_get_document_directories()` abstract method
3. Implement in `MkDocsAdapter` and `HugoOutputAdapter`
4. Remove duplicated scanning code

**Benefits**:
- DRY scanning logic
- New adapters only define directory configuration
- Consistent behavior across adapters

---

## 6. Message Schema Definitions

### Current State

Message schema defined twice:
- `ir_schema.py:IR_MESSAGE_SCHEMA` - Ibis schema (creation)
- `validation.py:IRMessageRow` - Pydantic model (validation)

### Problem

Adding a column requires updating both definitions. Type mismatches can cause subtle bugs.

### Solution: Generate Pydantic Model from Ibis Schema

**Strategy**: Create a utility to generate Pydantic models from Ibis schemas.

```python
def ibis_schema_to_pydantic(
    schema: ibis.Schema,
    model_name: str,
    validators: dict[str, Any] | None = None,
) -> type[BaseModel]:
    """Generate Pydantic model from Ibis schema."""

    type_mapping = {
        dt.String: str,
        dt.Int64: int,
        dt.Float64: float,
        dt.Boolean: bool,
        dt.Timestamp: datetime,
        dt.Date: date,
        dt.UUID: uuid.UUID,
        dt.JSON: dict[str, Any],
    }

    fields = {}
    for name, dtype in schema.items():
        python_type = type_mapping.get(type(dtype), Any)
        if dtype.nullable:
            python_type = python_type | None
        fields[name] = (python_type, ...)

    return create_model(model_name, **fields)

# Usage
IRMessageRow = ibis_schema_to_pydantic(
    IR_MESSAGE_SCHEMA,
    "IRMessageRow",
    validators={
        "source": Field(pattern=r"^[a-z][a-z0-9_-]*$"),
        "tenant_id": Field(min_length=1),
    }
)
```

**Action Items**:
1. Create `ibis_schema_to_pydantic()` utility in `validation.py`
2. Generate `IRMessageRow` from `IR_MESSAGE_SCHEMA`
3. Add field validators separately (can't be derived from Ibis)
4. Update tests to verify generation

**Benefits**:
- Single source of truth (Ibis schema)
- Automatic type synchronization
- Reduced maintenance burden

**Risk**: Custom Pydantic validators need manual definition. Acceptable since they're semantic (e.g., regex patterns) not structural.

---

## 7. Tool Definitions vs Pydantic Schemas

### Current State

In `agents/writer/tools.py`:
- `write_post_tool` signature mirrors `PostMetadata` fields
- `write_profile_tool` logic mirrors `write_post_tool` pattern
- Pattern: Action → Document Creation → Output Adapter Serve

### Problem

Minor duplication but manageable. Each tool has unique logic.

### Solution: Document a Common Pattern (No Code Change)

**Rationale**: The duplication here is acceptable because:
1. Tools have different validation requirements
2. Explicit code is easier to debug
3. The pattern is clear and intentional

**Action Items**:
1. Document the "Tool → Document → Serve" pattern in code comments
2. Consider a helper for common operations if more tools are added
3. No immediate code changes needed

**Future Enhancement**: If 5+ tools follow the same pattern, extract:
```python
def serve_document_tool(
    output_format: OutputAdapter,
    doc_type: DocumentType,
    content: str,
    metadata: dict[str, Any],
) -> str:
    """Common pattern for tools that create and serve documents."""
    doc = Document(content=content, type=doc_type, metadata=metadata)
    output_format.serve(doc)
    return doc.document_id
```

---

## Implementation Order

### Phase 1: Quick Wins (1-2 hours)
1. **#1 - Delete SQL file** - Immediate, no risk
2. **#6 - Schema generation** - High value, low effort

### Phase 2: Medium Effort (2-4 hours)
3. **#5 - Base adapter scanning** - Clean abstraction
4. **#2 - Config composition** - Reduces ongoing maintenance

### Phase 3: Larger Refactors (4-8 hours)
5. **#4 - Enrichment strategies** - Highest impact but needs careful testing

### Phase 4: Optional/Deferred
6. **#3 - Prompt factory** - Low priority, explicit classes are fine
7. **#7 - Tool patterns** - Document only, no code change

---

## Testing Strategy

For each change:
1. Run existing tests before changes
2. Make incremental changes
3. Run tests after each change
4. Add new tests for generated/factory code
5. Run full test suite: `uv run pytest tests/`
6. Run lint: `uv run pre-commit run --all-files`

---

## Success Metrics

- Lines of code reduced: Target 200-400 LOC
- Files deleted: 1 (runs_v1.sql)
- Duplicate field definitions eliminated: ~20
- Test coverage maintained: 100% of current coverage
