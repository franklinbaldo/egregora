# Open PRs Reimplementation Plan

**Status**: Draft
**Created**: 2025-11-21
**Context**: PRs #842-847 based on pre-PR#844 codebase, need reimplementation on current main

## Executive Summary

Five open PRs (#842, #843, #845, #846, #847) were created before PR #844's enrichment refactor merged to main. PR #844 moved in the opposite architectural direction (deleted `enrichment/` package, created `agents/enricher.py`), making direct merges impossible.

**Already Merged** (2025-11-21):
- ✅ Binary content support in Document (PR #847)
- ✅ Config validation utilities (PR #843/#845)

**Remaining Work**: Reimplement 5 major features on current main.

---

## Phase 1: Reader Agent Package Structure (PR #845)

### Current State (main)
```
src/egregora/agents/
├── reader.py          # Monolithic reader agent
└── ...
```

### Target State (from PR #845)
```
src/egregora/agents/reader/
├── __init__.py
├── agent.py           # Pydantic-AI reader agent
├── elo.py             # Elo comparison logic
├── models.py          # Reader-specific Pydantic models
└── reader_runner.py   # High-level runner
```

### Implementation Steps

1. **Create reader package**
   ```bash
   mkdir -p src/egregora/agents/reader
   ```

2. **Split monolithic reader.py**
   - Extract Pydantic models → `models.py`
   - Extract Elo comparison → `elo.py` or `compare.py`
   - Extract agent definition → `agent.py`
   - Extract runner/orchestration → `reader_runner.py`
   - Create `__init__.py` with exports

3. **Update imports across codebase**
   ```python
   # Old
   from egregora.agents.reader import compare_posts

   # New
   from egregora.agents.reader import compare_posts
   ```

4. **Add tests**
   - `tests/unit/agents/test_reader_models.py`
   - `tests/integration/agents/test_reader_elo.py`
   - Update existing reader tests

### Dependencies
- None (can be done first)

### Risk Assessment
- **Low**: Structural refactor only, no logic changes
- Watch for: Circular import issues with agents/shared

### Success Criteria
- All reader tests pass
- No import errors
- `ruff check` passes
- Reader CLI commands work unchanged

---

## Phase 2: RAG Refactor (PR #845)

### Current State (main)
```
src/egregora/knowledge/
├── rag.py             # Monolithic RAG implementation
├── annotations.py
└── profiles.py
```

### Target State (from PR #845)
```
src/egregora/agents/shared/rag/
├── __init__.py
├── chunker.py         # Text chunking logic
├── embedder.py        # Embedding generation
├── indexing.py        # Vector index creation
├── retriever.py       # Similarity search
├── store.py           # Vector store (DuckDB VSS)
└── pydantic_helpers.py # PydanticAI integration
```

### Implementation Steps

1. **Create RAG package**
   ```bash
   mkdir -p src/egregora/agents/shared/rag
   ```

2. **Split knowledge/rag.py**
   - Extract chunking → `chunker.py`
   - Extract embedding → `embedder.py`
   - Extract indexing → `indexing.py`
   - Extract retrieval → `retriever.py`
   - Extract storage → `store.py`
   - Extract PydanticAI helpers → `pydantic_helpers.py`

3. **Move annotations**
   ```python
   # From: src/egregora/knowledge/annotations.py
   # To:   src/egregora/agents/shared/annotations/__init__.py
   ```

4. **Update all RAG imports**
   ```python
   # Old
   from egregora.knowledge.rag import retrieve_similar

   # New
   from egregora.agents.shared.rag import retrieve_similar
   ```

5. **Update writer agent tools**
   - Writer agent uses RAG for context retrieval
   - Update tool imports in `agents/writer/tools.py`

6. **Update tests**
   - Move `tests/knowledge/test_rag.py` → `tests/integration/test_rag_store.py`
   - Add unit tests for each new module

### Dependencies
- Phase 1 (reader package) should be done first
- Requires understanding of current writer agent RAG usage

### Risk Assessment
- **Medium**: RAG is used by writer agent, errors affect generation
- Watch for: Breaking changes in retrieval API, embedding compatibility

### Success Criteria
- Writer agent RAG tools work unchanged
- All RAG tests pass
- Vector store queries return same results
- No performance regression

---

## Phase 3: MkDocs Path Simplification (PR #842)

### Current State (main)
```python
# Complex path resolution
from egregora.output_adapters.mkdocs.paths import SitePaths, load_site_paths

site_paths = load_site_paths(site_root)
mkdocs_path = site_paths.mkdocs_path
docs_dir = site_paths.docs_dir
# ... 10+ path attributes
```

### Target State (from PR #842)
```python
# Simple derived paths
def derive_mkdocs_paths(site_root: Path) -> dict[str, Path]:
    """Derive MkDocs paths directly from site root."""
    resolved_root = site_root.expanduser().resolve()
    egregora_dir = resolved_root / ".egregora"
    mkdocs_path = egregora_dir / "mkdocs.yml"

    # Check legacy location
    if (resolved_root / "mkdocs.yml").exists():
        mkdocs_path = resolved_root / "mkdocs.yml"

    return {
        "site_root": resolved_root,
        "mkdocs_path": mkdocs_path,
        "docs_dir": resolved_root / "docs",
        "posts_dir": resolved_root / "posts",
        # ... etc
    }
```

### Implementation Steps

1. **Add derive_mkdocs_paths() function**
   - Add to `output_adapters/mkdocs/adapter.py`
   - Simple dictionary-based path resolution
   - No YAML parsing, no config overrides (simplify first)

2. **Update MkDocsAdapter.__init__()**
   ```python
   # Old
   self.paths = load_site_paths(site_root)

   # New
   self.paths = derive_mkdocs_paths(site_root)
   ```

3. **Update all path access**
   ```python
   # Old
   self.paths.mkdocs_path

   # New
   self.paths["mkdocs_path"]
   ```

4. **Remove paths.py** (after migration)
   ```bash
   git rm src/egregora/output_adapters/mkdocs/paths.py
   ```

5. **Update SiteConfiguration**
   - Remove complex path overrides
   - Keep simple site_root-based resolution

6. **Update tests**
   - Remove `test_load_site_paths.py`
   - Update MkDocs adapter tests
   - Ensure custom docs_dir still works (from mkdocs.yml)

### Dependencies
- Should be done AFTER Phase 1 & 2 (less risky first)

### Risk Assessment
- **High**: MkDocs adapter is critical, used by all output
- Watch for: Breaking user configs, custom path setups, edge cases

### Migration Strategy
1. Add new function alongside old (parallel)
2. Update adapter to use new function
3. Test extensively with different configs
4. Remove old function once stable

### Success Criteria
- All e2e tests pass
- Custom mkdocs.yml paths still work
- `.egregora/mkdocs.yml` works
- Legacy `mkdocs.yml` at root works
- No user-visible breaking changes

---

## Phase 4: WhatsApp DuckDB zipfs Adapter (PR #846)

### Current State (main)
```python
# WhatsApp adapter extracts ZIP to temp, parses files
with zipfile.ZipFile(zip_path) as zf:
    zf.extractall(temp_dir)
    chat_file = temp_dir / "chat.txt"
    # ... parse
```

### Target State (from PR #846)
```python
# WhatsApp adapter uses DuckDB zipfs for streaming
import duckdb

# DuckDB reads directly from ZIP (no extraction)
conn.execute("""
    SELECT * FROM read_csv('zipfs://path/to/export.zip/chat.txt')
    WHERE length(content) < 2GB  -- Zip bomb protection
""")
```

### Implementation Steps

1. **Add zipfs capability check**
   ```python
   # In diagnostics.py
   def check_duckdb_zipfs_support() -> bool:
       """Check if DuckDB supports zipfs:// URIs."""
       conn = duckdb.connect(":memory:")
       try:
           conn.execute("SELECT 1 FROM zipfs://dummy.zip/test.txt")
           return True
       except:
           return False
   ```

2. **Add zip bomb guard**
   ```python
   DEFAULT_CHAT_FILE_LIMIT_BYTES = 2 * 1024**3  # 2GB

   def validate_chat_file_size(zip_path: Path, chat_file: str,
                               limit: int = DEFAULT_CHAT_FILE_LIMIT_BYTES):
       """Ensure chat file isn't a zip bomb."""
       with zipfile.ZipFile(zip_path) as zf:
           info = zf.getinfo(chat_file)
           if info.file_size > limit:
               raise ValueError(f"Chat file {chat_file} exceeds {limit} bytes")
   ```

3. **Refactor WhatsApp parser**
   ```python
   # Old: parse_export(zip_path) -> extract -> parse
   # New: parse_source(zipfs_uri) -> stream parse

   def parse_source(zipfs_uri: str, **kwargs) -> Table:
       """Parse WhatsApp chat via DuckDB zipfs streaming."""
       conn = duckdb.connect(":memory:")

       # Read directly from ZIP
       table = conn.execute(f"""
           SELECT * FROM read_csv('{zipfs_uri}',
               delim='\n',
               all_varchar=true,
               header=false)
       """).fetch_arrow_table()

       # ... existing parsing logic
   ```

4. **Update doctor command**
   ```python
   # In cli/doctor.py
   def check_zipfs_support():
       if not check_duckdb_zipfs_support():
           logger.warning("DuckDB zipfs not available, falling back to extraction")
   ```

5. **Remove old zip utilities**
   ```bash
   git rm src/egregora/utils/zip.py  # If fully replaced
   ```

6. **Update tests**
   - Add zipfs streaming tests
   - Keep extraction fallback tests
   - Test zip bomb detection

### Dependencies
- None (independent of other phases)

### Risk Assessment
- **Medium**: WhatsApp adapter is main input, but has fallback
- Watch for: DuckDB version compatibility, zipfs availability

### Fallback Strategy
```python
def parse_whatsapp(zip_path: Path) -> Table:
    if check_duckdb_zipfs_support():
        return parse_via_zipfs(zip_path)
    else:
        logger.warning("Falling back to extraction-based parsing")
        return parse_via_extraction(zip_path)
```

### Success Criteria
- WhatsApp parsing still works
- Zip bomb protection works
- Performance improvement (no temp files)
- Tests pass with and without zipfs

---

## Phase 5: New Output Adapters (PR #843/#845)

### Eleventy Arrow Adapter

**Purpose**: Output windowed Parquet files for Eleventy static site generator

**Target Structure**:
```
output/
  data/
    window_0.parquet
    window_1.parquet
  eleventy/
    src/_data/documents.js  # Loads Parquet files
```

**Implementation**:

1. **Create adapter skeleton**
   ```bash
   mkdir -p src/egregora/output_adapters/eleventy_arrow
   touch src/egregora/output_adapters/eleventy_arrow/{__init__.py,adapter.py}
   ```

2. **Implement EleventyArrowAdapter**
   ```python
   class EleventyArrowAdapter(OutputAdapter):
       def __init__(self, site_root: Path, url_context: Any):
           self.site_root = site_root
           self.data_dir = site_root / "data"
           self._buffers: dict[str, list[Document]] = {}

       def serve(self, document: Document):
           """Buffer document for batch write."""
           window = document.source_window or "default"
           self._buffers.setdefault(window, []).append(document)

       def finalize_window(self, window_label: str, posts, profiles, metadata):
           """Write window to Parquet."""
           docs = self._buffers.get(window_label, [])
           df = self._documents_to_frame(docs)

           window_idx = metadata.get("window_index", 0)
           output_path = self.data_dir / f"window_{window_idx}.parquet"
           df.to_parquet(output_path)
   ```

3. **Register adapter**
   ```python
   # In output_adapters/__init__.py
   from egregora.output_adapters.eleventy_arrow import EleventyArrowAdapter

   ADAPTER_REGISTRY = {
       "mkdocs": MkDocsAdapter,
       "eleventy-arrow": EleventyArrowAdapter,
       "hugo": HugoAdapter,  # Phase 5b
   }
   ```

4. **Add tests**
   - `tests/output_adapters/test_eleventy_arrow.py`
   - Test window buffering
   - Test Parquet file creation
   - Test schema correctness

### Hugo Adapter

**Purpose**: Output markdown for Hugo static site generator

**Implementation**: Similar to MkDocs adapter but with Hugo conventions

1. **Create adapter**
   ```bash
   mkdir -p src/egregora/output_adapters/hugo
   ```

2. **Implement HugoAdapter**
   - Front matter format: YAML or TOML
   - Directory structure: `content/posts/`, `content/profiles/`
   - Taxonomies: tags, categories
   - Hugo-specific features: shortcodes, archetypes

3. **Register and test**

### Dependencies
- Independent (can be done in parallel)
- Low priority (MkDocs is primary)

### Risk Assessment
- **Low**: New adapters, no impact on existing functionality

### Success Criteria
- Adapters pass basic tests
- Can generate valid Eleventy/Hugo sites
- Documentation exists

---

## Implementation Roadmap

### Recommended Order

```
Phase 1: Reader Agent Package (1-2 days)
  ↓
Phase 2: RAG Refactor (2-3 days)
  ↓
Phase 4: WhatsApp zipfs (1-2 days)
  ↓
Phase 3: MkDocs Path Simplification (2-3 days) ← Risky, do last
  ↓
Phase 5: New Output Adapters (optional, 2-3 days)
```

### Rationale
1. **Reader** first: Low risk, structural only
2. **RAG** second: Medium risk, needed by writer
3. **WhatsApp** third: Medium risk, has fallback
4. **MkDocs** fourth: High risk, test extensively
5. **New adapters** last: Optional, low priority

### Total Estimate
- **Required phases (1-4)**: 6-10 days
- **Optional phase (5)**: +2-3 days
- **Testing & polish**: +2-3 days
- **Total**: 8-16 days

---

## Testing Strategy

### Per-Phase Testing

1. **Unit tests**: Test each new module in isolation
2. **Integration tests**: Test interactions with other components
3. **E2E tests**: Full pipeline with real fixtures
4. **Regression tests**: Ensure old behavior unchanged

### Pre-Merge Checklist

- [ ] All tests pass (`uv run pytest tests/`)
- [ ] Linting passes (`uv run ruff check src/`)
- [ ] Formatting passes (`uv run ruff format src/`)
- [ ] Pre-commit hooks pass
- [ ] No import errors
- [ ] Documentation updated
- [ ] CLAUDE.md updated if needed

### Critical Test Coverage

**Phase 1 (Reader)**:
- Reader agent still works
- Elo comparisons work
- CLI commands work

**Phase 2 (RAG)**:
- Writer agent RAG retrieval works
- Embeddings generate correctly
- Vector store queries work

**Phase 3 (MkDocs)**:
- All MkDocs adapter tests pass
- Custom paths work
- E2E pipeline generates valid sites

**Phase 4 (WhatsApp)**:
- WhatsApp parsing works
- Zip bomb detection works
- Fallback to extraction works

---

## Migration Notes

### Breaking Changes to Avoid

1. **Public APIs**: Keep CLI interfaces unchanged
2. **Config format**: Keep `.egregora/config.yml` compatible
3. **Output format**: Keep generated markdown unchanged
4. **Database schema**: Keep runs/RAG tables compatible

### Deprecation Strategy

If breaking changes needed:

1. Support old + new in parallel (1-2 releases)
2. Log deprecation warnings
3. Update docs with migration guide
4. Remove old in major version bump

### User Communication

Before merging:
- Update CHANGELOG.md
- Document any new features
- Note any behavior changes
- Add migration guide if needed

---

## Risk Mitigation

### High-Risk Areas

1. **MkDocs path resolution**: Many edge cases, user configs
   - Mitigation: Extensive testing, keep old code in parallel

2. **RAG refactor**: Critical for writer agent
   - Mitigation: Pin exact embedding model, verify outputs unchanged

3. **Import reorganization**: Easy to break imports
   - Mitigation: Automated import scanning, comprehensive grep

### Rollback Plan

Each phase should be mergeable independently:

```bash
# If Phase 3 breaks, revert just that phase
git revert <phase-3-commit-range>

# Other phases still work
```

### Monitoring

After merge:
- Watch for import errors in CI
- Check test pass rates
- Monitor for user-reported issues

---

## Success Metrics

### Code Quality
- [ ] Test coverage ≥ current (check with `pytest --cov`)
- [ ] Zero ruff violations
- [ ] Zero import errors
- [ ] All pre-commit hooks pass

### Functionality
- [ ] All existing features work unchanged
- [ ] New features work as designed
- [ ] Performance not degraded
- [ ] Memory usage not increased

### Documentation
- [ ] All new modules have docstrings
- [ ] README.md updated
- [ ] CLAUDE.md updated
- [ ] API reference updated

---

## Open Questions

1. **Reader package**: Should we also package writer/banner/editor?
   - Decision: Yes, follow same pattern for consistency

2. **RAG location**: `agents/shared/rag/` or `knowledge/rag/`?
   - Decision: `agents/shared/rag/` (PR #845 choice)

3. **MkDocs simplification**: Remove ALL custom path config?
   - Decision: Keep minimal config, remove SitePaths class

4. **WhatsApp zipfs**: Support fallback forever or require DuckDB ≥X?
   - Decision: Keep fallback, log warning if zipfs unavailable

5. **New adapters**: Implement in this PR or separate?
   - Decision: Separate PRs (Phase 5 optional)

---

## Related Documents

- Original PRs:
  - #847: Binary content support (✅ merged)
  - #846: WhatsApp zipfs refactor
  - #845: Reader/RAG/adapters
  - #843: Config validation/adapters (✅ partial merge)
  - #842: MkDocs path simplification

- Planning docs:
  - `docs/plans/pydantic-ai-mock-plan.md` (from PR #845)
  - `docs/plans/user-stories-output-fixes.md` (from PR #845)
  - `docs/plans/replace-cassettes-with-pydantic-ai-mocks.md` (from PR #845)

- Architecture docs:
  - `docs/architecture/three-layer-functional.md`
  - `docs/pipeline/view-registry.md`
  - `docs/database/storage-manager.md`

---

## Conclusion

The open PRs contain valuable refactoring work that improves code organization and adds useful features. However, they were built on a different codebase structure and cannot be merged directly.

This plan outlines a phased approach to reimplementing the valuable parts:
1. Low-risk structural refactors first (reader, RAG)
2. Medium-risk functional changes next (WhatsApp)
3. High-risk simplifications last (MkDocs paths)
4. Optional new features (adapters)

Each phase is independently testable and mergeable, reducing risk and allowing incremental progress.

**Next Steps**:
1. Review this plan
2. Get approval on approach
3. Start with Phase 1 (Reader package)
4. Proceed phase by phase
5. Test extensively before each merge
