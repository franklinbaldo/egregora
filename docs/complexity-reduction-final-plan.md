# Complexity Reduction & Modernization - FINAL UNIFIED PLAN

## Executive Summary

This document unifies three separate initiatives:

1. **Original complexity reduction** (PR #618) - Tactical fixes for 62 linting errors
2. **Config migration** - Move settings from mkdocs.yml to .egregora/
3. **Architectural improvements** - Parser modernization, RAG refactor, domain objects

**Critical correction**: My initial "v2.0" plan misrepresented Pydantic-AI patterns. This final plan uses **only documented, verified approaches**.

---

## 🚨 Corrections to v2.0 Plan

Based on thorough review, I need to correct these misrepresentations:

### ❌ What I Got WRONG

1. **Tool Registration Pattern**
   - **I claimed**: Current pattern is wrong, should use `WriterToolSet` class
   - **REALITY**: Current `@agent.tool` decorator pattern is CORRECT per pydantic-ai docs
   - **Action**: **Keep current tool registration as-is**

2. **Result Types for Tools**
   - **I claimed**: Tools should return `Result[T, str]` from `returns` library
   - **REALITY**: Pydantic-AI tools should return BaseModel instances
   - **Action**: **Keep current BaseModel returns**, do NOT use Result types in tools

3. **Immutable State with `with_*` Methods**
   - **I claimed**: Use `with_post()` methods for immutable updates
   - **REALITY**: Pattern not documented in pydantic-ai, invented by me
   - **Action**: **Don't implement this**, use simpler approaches

### ✅ What I Got RIGHT

1. **Config Dataclasses for Deps** ✅
   - Using `@dataclass` for `deps_type` IS standard practice
   - Reduces 14 params → 3 params

2. **Deps Should Not Mutate** ✅
   - Current code improperly does `ctx.deps.saved_posts.append(path)`
   - This violates immutability
   - Fix: Don't mutate deps, track results elsewhere

3. **Parser Modernization (pyparsing)** ✅
   - Industry-standard approach
   - Unrelated to Pydantic-AI, but valuable

4. **RAG Strategy Pattern** ✅
   - Good architectural improvement
   - Unrelated to Pydantic-AI, but valuable

5. **Domain Value Objects** ✅
   - Type safety improvement
   - Unrelated to Pydantic-AI, but valuable

---

## 📊 Categorization of Work

### Category A: Pydantic-AI Compliance (1 week)
**Only 2 actual violations** to fix:
1. Deps mutation in tool functions
2. Too many function parameters

### Category B: Config Migration (2 weeks)
Foundation for all other work:
- Extract settings from mkdocs.yml → .egregora/
- Pydantic validation schemas
- Custom prompt overrides

### Category C: Complexity Reduction (4 weeks)
Tactical fixes from original plan:
- Configuration objects
- Pipeline decomposition
- Function extraction

### Category D: Architectural Improvements (4-6 weeks, optional)
Strategic modernization:
- Parser rewrite with pyparsing
- RAG strategy pattern
- Domain value objects

**Total**: 7-9 weeks (core) + 4-6 weeks (optional improvements)

---

## 🎯 Unified Roadmap

### Phase 0: Config Migration (Week 1-2)

**Goal**: Extract configuration from mkdocs.yml to .egregora/

**Why first**: Provides infrastructure for all subsequent work

#### Week 1: Config Infrastructure

1. **Create Pydantic schemas**:
   ```python
   # src/egregora/config/schema.py
   class ModelConfig(BaseModel):
       writer: str = "models/gemini-2.0-flash-exp"
       enricher: str = "models/gemini-1.5-flash"
       embedding: str = "models/text-embedding-004"
       ranking: str | None = None
       editor: str | None = None

   class RAGConfig(BaseModel):
       enabled: bool = True
       top_k: int = Field(5, ge=1, le=20)
       min_similarity: float = Field(0.7, ge=0.0, le=1.0)
       mode: Literal["ann", "exact"] = "ann"
       nprobe: int | None = Field(None, ge=1, le=100)

   class WriterConfig(BaseModel):
       custom_instructions: str | None = None
       enable_meme_generation: bool = False
       enable_banners: bool = True

   class PrivacyConfig(BaseModel):
       anonymization_enabled: bool = True
       pii_detection_enabled: bool = True
       opt_out_keywords: list[str] = Field(default_factory=lambda: ["/egregora opt-out"])

   class EgregoraConfig(BaseModel):
       """Root configuration model."""
       models: ModelConfig = Field(default_factory=ModelConfig)
       rag: RAGConfig = Field(default_factory=RAGConfig)
       writer: WriterConfig = Field(default_factory=WriterConfig)
       privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
       features: dict[str, bool] = Field(default_factory=dict)
   ```

2. **Create config loader**:
   ```python
   # src/egregora/config/loader.py
   def load_egregora_config(site_dir: Path) -> EgregoraConfig:
       """Load config from .egregora/config.yml with fallback to mkdocs.yml."""
       egregora_config = site_dir / ".egregora" / "config.yml"

       if egregora_config.exists():
           data = yaml.safe_load(egregora_config.read_text())
           return EgregoraConfig(**data)

       # Fallback to mkdocs.yml for backward compatibility
       mkdocs_config = site_dir / "mkdocs.yml"
       if mkdocs_config.exists():
           data = yaml.safe_load(mkdocs_config.read_text())
           extra_egregora = data.get("extra", {}).get("egregora", {})
           return EgregoraConfig(**extra_egregora)

       # Return defaults
       return EgregoraConfig()
   ```

3. **Update SitePaths**:
   ```python
   # src/egregora/init/paths.py
   @dataclass
   class SitePaths:
       site_dir: Path
       docs_dir: Path
       posts_dir: Path
       profiles_dir: Path
       rag_dir: Path
       config_dir: Path  # New: .egregora/
       prompts_dir: Path  # New: .egregora/prompts/

       @classmethod
       def from_site_dir(cls, site_dir: Path) -> "SitePaths":
           return cls(
               site_dir=site_dir,
               docs_dir=site_dir / "docs",
               posts_dir=site_dir / "docs" / "posts",
               profiles_dir=site_dir / "docs" / "profiles",
               rag_dir=site_dir / ".egregora" / "rag",  # Move to .egregora/
               config_dir=site_dir / ".egregora",
               prompts_dir=site_dir / ".egregora" / "prompts",
           )
   ```

#### Week 2: Prompt Overrides & Scaffolding

4. **Implement prompt override loader**:
   ```python
   # src/egregora/config/prompts.py
   def load_prompt(name: str, site_dir: Path) -> str:
       """Load prompt with user override support.

       Checks:
       1. .egregora/prompts/{name}.md (user override)
       2. egregora/templates/prompts/{name}.md (package default)
       """
       user_prompt = site_dir / ".egregora" / "prompts" / f"{name}.md"
       if user_prompt.exists():
           logger.info("Using custom prompt: %s", name)
           return user_prompt.read_text()

       # Fallback to package default
       package_prompt = Path(__file__).parent.parent / "templates" / "prompts" / f"{name}.md"
       if package_prompt.exists():
           return package_prompt.read_text()

       raise FileNotFoundError(f"Prompt not found: {name}")
   ```

5. **Update site scaffolding**:
   ```python
   # src/egregora/init/scaffolding.py
   def create_site_structure(site_dir: Path) -> None:
       """Create .egregora/ directory structure for new sites."""
       config_dir = site_dir / ".egregora"
       config_dir.mkdir(exist_ok=True)

       # Create default config.yml
       default_config = EgregoraConfig()
       config_file = config_dir / "config.yml"
       config_file.write_text(
           yaml.dump(default_config.model_dump(), sort_keys=False)
       )

       # Create prompts/ directory with README
       prompts_dir = config_dir / "prompts"
       prompts_dir.mkdir(exist_ok=True)
       (prompts_dir / "README.md").write_text(
           "# Custom Prompts\n\n"
           "Place custom prompt overrides here with same names as package defaults.\n"
       )

       # Create .gitignore
       (config_dir / ".gitignore").write_text("*.pyc\n__pycache__/\nrag/\n")
   ```

**Deliverable**: Config migration PR
**Files changed**: 5 new, 11 modified
**Impact**: Foundation for all subsequent work

---

### Phase 1: Pydantic-AI Compliance (Week 3)

**Goal**: Fix ONLY the 2 actual Pydantic-AI violations

**Why separate**: Clear focus on framework compliance vs. general improvements

#### Issue 1: Fix Deps Mutation

**Current (WRONG)**:
```python
@agent.tool
def write_post_tool(ctx: RunContext[WriterAgentState], ...) -> WritePostResult:
    path = write_post(...)
    ctx.deps.record_post(path)  # ❌ Mutates deps!
    return WritePostResult(status="success", path=path)

class WriterAgentState(BaseModel):
    saved_posts: list[str] = Field(default_factory=list)  # ❌ Mutable!

    def record_post(self, path: str) -> None:
        self.saved_posts.append(path)  # ❌ Mutation!
```

**Fixed (CORRECT)**:
```python
# Option A: Return results in agent output
class WriterAgentReturn(BaseModel):
    summary: str | None = None
    notes: str | None = None
    saved_posts: list[Path] = Field(default_factory=list)  # Track here
    saved_profiles: list[Path] = Field(default_factory=list)

@agent.result_validator
async def collect_results(ctx: RunContext[WriterAgentState], result: WriterAgentReturn) -> WriterAgentReturn:
    """Collect all posts/profiles created during run."""
    # Extract from tool call history if needed
    return result

# Option B: Collect from tool call history (simpler)
def get_saved_posts(result: RunResult) -> list[Path]:
    """Extract saved posts from tool call history."""
    posts = []
    for msg in result.all_messages():
        if hasattr(msg, 'tool_calls'):
            for call in msg.tool_calls:
                if call.tool_name == 'write_post_tool':
                    posts.append(Path(call.result.path))
    return posts
```

**Recommended**: Option B (simpler, no deps mutation)

#### Issue 2: Reduce Function Parameters

**Current (WRONG)**:
```python
def write_posts_with_pydantic_agent(
    prompt: str,
    model_name: str,
    period_date: str,
    output_dir: Path,
    profiles_dir: Path,
    rag_dir: Path,
    client: object,
    embedding_model: str,
    retrieval_mode: str,
    retrieval_nprobe: int | None,
    retrieval_overfetch: int | None,
    annotations_store: AnnotationStore | None,
    agent_model: object | None = None,
    register_tools: bool = True,
) -> tuple[list[str], list[str]]:
```

**Fixed (CORRECT)**:
```python
@dataclass(frozen=True)
class WriterDeps:
    """Dependencies for writer agent (immutable)."""
    config: EgregoraConfig  # From Phase 0!
    paths: SitePaths
    client: genai.Client
    annotations_store: AnnotationStore | None

def write_posts_with_pydantic_agent(
    prompt: str,
    deps: WriterDeps,
    agent_model: object | None = None,
) -> RunResult:
    """Execute writer agent - 3 params instead of 14!"""
    agent = Agent[WriterDeps, WriterAgentReturn](
        model=agent_model or deps.config.models.writer,
        deps_type=WriterDeps
    )

    # Tool registration stays EXACTLY as-is (current is correct!)
    @agent.tool
    def write_post_tool(ctx: RunContext[WriterDeps], ...) -> WritePostResult:
        path = write_post(
            content=content,
            metadata=metadata.model_dump(),
            output_dir=ctx.deps.paths.output_dir
        )
        return WritePostResult(status="success", path=str(path))

    # Run agent
    result = agent.run_sync(prompt, deps=deps)
    return result
```

**Key points**:
- ✅ Use `@dataclass(frozen=True)` for deps (documented pattern)
- ✅ Keep `@agent.tool` decorator (current is correct!)
- ✅ Return BaseModel from tools (current is correct!)
- ✅ Don't mutate deps (fixed)
- ✅ Use EgregoraConfig from Phase 0

**Deliverable**: Pydantic-AI compliance PR
**Files changed**:
- `src/egregora/agents/writer/writer_agent.py`
- `src/egregora/agents/editor/editor_agent.py`
- `src/egregora/agents/ranking/ranking_agent.py`

**Impact**:
- PLR0913: -3 (writer, editor, ranking)
- Proper framework compliance
- Cleaner API

---

### Phase 2: Configuration Objects (Week 4)

**Goal**: Apply config objects pattern across codebase

**Builds on**: Phase 0 (EgregoraConfig) + Phase 1 (deps pattern)

1. **Create domain config objects**:
   ```python
   # src/egregora/config/pipeline.py
   @dataclass(frozen=True)
   class PipelineConfig:
       """Pipeline execution configuration."""
       config: EgregoraConfig
       enable_enrichment: bool = True
       enable_rag: bool = True
       max_enrichments: int = 50

   @dataclass(frozen=True)
   class EnrichmentConfig:
       """Enrichment service configuration."""
       models: ModelConfig
       max_enrichments: int = 50
       enable_url: bool = True
       enable_media: bool = True
   ```

2. **Refactor function signatures**:
   - `run_source_pipeline`: 16 params → 3 params
   - `enrich_table`: 14 params → 3 params
   - `_process_tool_calls`: 12 params → 3 params

**Deliverable**: Config objects PR
**Impact**: PLR0913: -15 (most "too many arguments" errors)

---

### Phase 3: Pipeline Decomposition (Week 5-6)

**Goal**: Extract focused sub-functions to reduce complexity

**From original plan** - Keep as-is:

1. **Enrichment decomposition**:
   ```python
   # src/egregora/enrichment/core.py
   def enrich_table(
       messages: Table,
       config: EnrichmentConfig,
       paths: SitePaths,
       clients: EnrichmentClients,
   ) -> Table:
       """Orchestrate enrichment - delegates to focused functions."""
       urls = _extract_urls(messages, config.max_enrichments)
       media = _extract_media(messages, config.max_enrichments, paths)

       url_results = _enrich_urls(urls, clients.text, config)
       media_results = _enrich_media(media, clients.vision, config)

       return _merge_enrichments(messages, url_results, media_results)

   def _extract_urls(table: Table, max_count: int) -> list[URLToEnrich]:
       """Extract URLs needing enrichment."""
       ...

   def _enrich_urls(urls: list[URLToEnrich], client: genai.Client, config: EnrichmentConfig) -> list[URLEnrichment]:
       """Batch enrich URLs."""
       ...
   ```

2. **CLI decomposition**:
   ```python
   # src/egregora/cli.py
   def _validate_and_run_process(...) -> None:
       """Orchestrate process command."""
       config = _validate_process_config(...)
       components = _setup_pipeline_components(config, paths)
       _run_pipeline(components)
   ```

3. **Pipeline runner decomposition**:
   ```python
   # src/egregora/pipeline/runner.py
   def run_source_pipeline(config: PipelineConfig, paths: SitePaths, ...) -> Table:
       """Orchestrate pipeline stages."""
       _validate_inputs(paths)
       messages = _run_ingestion(paths, config)
       if config.enable_enrichment:
           messages = _run_enrichment(messages, paths, config)
       if config.enable_rag:
           _build_rag_index(messages, paths, config)
       return messages
   ```

**Deliverable**: Pipeline decomposition PR
**Impact**:
- C901: -3 (enrich_table, _validate_and_run_process, run_source_pipeline)
- PLR0915: -3 (same functions)

---

### Phase 4: Remaining Complexity (Week 7)

**Goal**: Fix remaining tactical errors

**From original plan** - Keep as-is:

1. **Avatar state machine**:
   - Extract state handlers
   - Reduces C901: -3

2. **Profiler refactor**:
   - Extract command handlers
   - Reduces C901: -1

3. **Adapter early returns**:
   - Simplify deliver_media
   - Reduces PLR0911: -1

4. **Misc cleanup**:
   - Apply config objects to remaining functions
   - Fix remaining PLR0913

**Deliverable**: Final complexity PR
**Impact**: Remaining ~10 errors resolved

---

### Phase 5: Testing & Integration (Week 8)

**Goal**: Validate entire refactor

1. **Integration testing**:
   - Run full pipeline with golden fixtures
   - Compare outputs
   - Performance benchmarks

2. **Migration guide**:
   - Document .egregora/ migration for existing sites
   - Update CLAUDE.md
   - Update user documentation

3. **Cleanup**:
   - Remove deprecated code
   - Final ruff pass

**Deliverable**: Integration & docs PR

---

## 🎨 Optional: Architectural Improvements (Week 9-14)

**These are SEPARATE from complexity reduction and Pydantic-AI compliance**

Can be done later as independent initiatives:

### Week 9-10: Parser Modernization (OPTIONAL)

**Goal**: Replace regex parser with pyparsing

**Why optional**: Current parser works, this is for maintainability

```python
# src/egregora/ingestion/grammar.py
from pyparsing import *

# Declarative grammar
date_part = Word(nums, max=2) + "/" + Word(nums, max=2) + "/" + Word(nums, min=2, max=4)
time_part = Word(nums, max=2) + ":" + Word(nums, exact=2)
ampm = Optional(Regex(r"[APap][Mm]"))
separator = Suppress(Regex(r"[—\-]"))
author = Regex(r"[^:]+")
message = rest_of_line

whatsapp_message = Group(
    Optional(date_part)("date") +
    Optional(Suppress(",") | Suppress(" ")) +
    time_part("time") +
    ampm("ampm") +
    separator +
    author("author") +
    Suppress(":") +
    message("message")
)

class WhatsAppParser:
    def parse_line(self, line: str) -> Message | None:
        try:
            result = whatsapp_message.parse_string(line)
            return Message.from_parse_result(result)
        except ParseException:
            return None
```

**Dependencies**: Add `pyparsing>=3.1.0`

**Deliverable**: Parser refactor PR
**Impact**:
- Code: 500 → 200 lines
- C901: -1 (parse_multiple)
- PLR0912: -1 (parse_multiple)
- Maintainability: High improvement

### Week 11-12: RAG Strategy Pattern (OPTIONAL)

**Goal**: Refactor RAG search with strategy pattern

**Why optional**: Current RAG works, this improves extensibility

```python
# src/egregora/agents/tools/rag/strategies.py
class RetrievalStrategy(Protocol):
    def search(self, embedding: list[float], k: int) -> Table: ...

class ANNRetriever:
    def __init__(self, store: VectorStore, nprobe: int = 10):
        self.store = store
        self.nprobe = nprobe

    def search(self, embedding: list[float], k: int) -> Table:
        return self.store._ann_search(embedding, k, self.nprobe)

class ExactRetriever:
    def __init__(self, store: VectorStore):
        self.store = store

    def search(self, embedding: list[float], k: int) -> Table:
        return self.store._exact_search(embedding, k)

# src/egregora/agents/tools/rag/pipeline.py
class RAGSearchPipeline:
    def search(self, query: RAGQuery) -> Table:
        """Simplified pipeline replaces 77-statement function."""
        embedding = self._embed(query.query_text)
        strategy = self._get_strategy(query.mode)
        candidates = strategy.search(embedding, query.top_k * 5)
        filtered = self._apply_filters(candidates, query.filters)
        return filtered.order_by("similarity").limit(query.top_k)
```

**Deliverable**: RAG refactor PR
**Impact**:
- C901: -1 (VectorStore.search)
- PLR0913: -1 (VectorStore.search)
- PLR0915: -1 (VectorStore.search)
- PLR0911: -1 (VectorStore.search)

### Week 13-14: Domain Value Objects (OPTIONAL)

**Goal**: Type-safe domain primitives

**Why optional**: Current code works, this improves type safety

```python
# src/egregora/domain/value_objects.py
class PostSlug(BaseModel):
    """Validated post slug."""
    value: str = Field(pattern=r"^[a-z0-9-]+$")

    def __str__(self) -> str:
        return self.value

class AuthorUUID(BaseModel):
    """Validated author UUID."""
    value: str = Field(pattern=r"^[a-f0-9-]+$")

    def __str__(self) -> str:
        return self.value

# Gradually migrate codebase
class PostMetadata(BaseModel):
    title: str
    slug: PostSlug  # Type-safe!
    date: date
    authors: frozenset[AuthorUUID]  # Type-safe!
```

**Deliverable**: Domain objects PR
**Impact**: Eliminates validation complexity throughout codebase

---

## 📊 Impact Summary

### Core Work (Week 1-8)

| Phase | Weeks | Errors Fixed | Risk |
|-------|-------|--------------|------|
| Config migration | 2 | 0 (foundation) | Low |
| Pydantic-AI compliance | 1 | ~5 | Low |
| Config objects | 1 | ~15 | Low |
| Pipeline decomposition | 2 | ~25 | Low |
| Remaining complexity | 1 | ~17 | Low |
| Testing & docs | 1 | 0 (validation) | Low |
| **TOTAL** | **8** | **62** | **Low** |

### Optional Improvements (Week 9-14)

| Phase | Weeks | Benefit | Risk |
|-------|-------|---------|------|
| Parser modernization | 2 | High maintainability | Medium |
| RAG strategy pattern | 2 | High extensibility | Low |
| Domain value objects | 2 | High type safety | Low |
| **TOTAL** | **6** | **Strategic** | **Low-Med** |

---

## 🎯 Recommended Approach

### Option 1: CORE ONLY (8 weeks)
- Config migration
- Pydantic-AI compliance
- Complexity reduction
- **Result**: All errors fixed, solid foundation

### Option 2: CORE + PARSER (10 weeks)
- Everything from Option 1
- Parser modernization
- **Result**: All errors fixed + modern parser

### Option 3: CORE + PARSER + RAG (12 weeks)
- Everything from Option 2
- RAG strategy pattern
- **Result**: All errors fixed + modern parser + extensible RAG

### Option 4: FULL MODERNIZATION (14 weeks)
- Everything from Option 3
- Domain value objects
- **Result**: Complete architectural overhaul

**My recommendation**: **Option 2 (CORE + PARSER, 10 weeks)**
- Fixes all complexity errors
- Modernizes the most fragile component (parser)
- Manageable timeline
- Sets up for future improvements

---

## 🔄 Integration with Existing Work

### Config Migration (Already Planned)
- ✅ Use as Phase 0 (foundation)
- ✅ Provides EgregoraConfig for all subsequent work
- ✅ Enables custom prompts
- ✅ 6 phases already detailed

### Pydantic-AI Compliance (Per Review)
- ✅ Focus ONLY on 2 violations (deps, params)
- ✅ Don't change tool registration (current is correct!)
- ✅ Don't use Result types (BaseModel is correct!)
- ✅ 1 week, low risk

### Original Complexity Plan (PR #618)
- ✅ Keep Phases 1-6 as-is (solid tactical fixes)
- ✅ Apply AFTER config migration and Pydantic-AI compliance
- ✅ Proven approach, low risk

### Architectural Improvements (Optional)
- ✅ Separate from complexity reduction
- ✅ Can be done incrementally
- ✅ Each phase is independently valuable
- ✅ Not required for "done" state

---

## 🚀 Next Steps

1. **Choose option** (1-4 based on timeline/budget)

2. **Get approvals**:
   - Timeline (8-14 weeks depending on option)
   - Dependencies (pyparsing for parser modernization)
   - Resource allocation

3. **Start with Phase 0** (Config migration):
   - Already detailed in separate doc
   - 2 weeks, low risk
   - Foundation for everything else

4. **Review after Phase 1** (Pydantic-AI compliance):
   - Validate approach
   - Decide on optional phases
   - Adjust timeline if needed

---

## 📝 Success Criteria

### Must Have (All Options)
- ✅ All 62 complexity errors resolved
- ✅ Test coverage maintained (≥85%)
- ✅ Pydantic-AI compliance verified
- ✅ Config migration complete (.egregora/)
- ✅ No functionality regression
- ✅ Integration tests pass

### Should Have (Option 2+)
- ✅ Parser modernized with pyparsing
- ✅ Code reduced: 500 → 200 lines
- ✅ Grammar is declarative and maintainable

### Nice to Have (Option 3+)
- ✅ RAG uses strategy pattern
- ✅ Search pipeline is composable
- ✅ Easy to add new retrieval strategies

### Aspirational (Option 4)
- ✅ Domain value objects throughout
- ✅ Type coverage >90%
- ✅ Impossible states impossible

---

## 🙏 Acknowledgments

This plan combines:
- **Original complexity reduction** (PR #618) - Solid tactical foundation
- **Config migration** - Essential infrastructure work
- **Pydantic-AI review** - Critical corrections to my misrepresentations
- **Architectural improvements** - Strategic long-term value

**Thank you** to the reviewers who caught my mistakes and ensured this plan is accurate and achievable.

---

## ⚠️ Important Notes

1. **Tool registration is CORRECT** - Don't change it
2. **BaseModel returns are CORRECT** - Don't use Result types
3. **Config migration is FOUNDATION** - Do it first
4. **Optional phases are truly optional** - Core work stands alone
5. **Each phase is independently deliverable** - Can pause anywhere

---

## 📚 References

- Original plan: `docs/complexity-reduction-plan.md`
- Config migration: `docs/development/egregora-config-migration.md`
- Review: `docs/pydantic-ai-patterns-review.md`
- My analysis: `docs/complexity-reduction-plan-v2.md` (contains errors, see corrections above)
- Pydantic-AI docs: https://ai.pydantic.dev/
- pyparsing docs: https://pyparsing-docs.readthedocs.io/

---

**Final recommendation**: **Option 2 (CORE + PARSER, 10 weeks)** provides the best balance of:
- ✅ All errors fixed (62/62)
- ✅ Framework compliance (Pydantic-AI)
- ✅ Modern infrastructure (config migration)
- ✅ Maintainable parser (pyparsing)
- ✅ Manageable timeline (10 weeks)
- ✅ Low-medium risk

Ready to begin!
