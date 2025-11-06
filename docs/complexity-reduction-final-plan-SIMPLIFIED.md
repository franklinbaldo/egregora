# Complexity Reduction & Modernization - SIMPLIFIED (Alpha Version)

## 🚀 Alpha Mindset: Break Everything, Make It Better

**Critical simplification**: No backward compatibility! We're in alpha, no clients, ephemeral DB.

**Removed**:
- ❌ mkdocs.yml fallback logic
- ❌ Legacy config transformation
- ❌ Migration guides
- ❌ Deprecation warnings
- ❌ Dual-support code paths

**Result**: 30% less code, 50% faster implementation, 100% cleaner

---

## Phase 0: Config Migration (Week 1-2) - SIMPLIFIED

### Week 1: Config Infrastructure

**1. Create Pydantic schemas** (schema.py)
```python
# Simple, clean, no legacy support
class EgregoraConfig(BaseModel):
    models: ModelsConfig
    rag: RAGConfig
    writer: WriterConfig
    privacy: PrivacyConfig
    enrichment: EnrichmentConfig
    pipeline: PipelineConfig
    features: FeaturesConfig
```

**2. Create config loader** (loader.py)
```python
# SIMPLE - just load .egregora/config.yml, that's it!
def load_egregora_config(site_root: Path) -> EgregoraConfig:
    """Load config from .egregora/config.yml ONLY."""
    config_path = site_root / ".egregora" / "config.yml"

    if not config_path.exists():
        # Create default config on the fly
        return create_default_config(site_root)

    data = yaml.safe_load(config_path.read_text())
    return EgregoraConfig(**data)

def create_default_config(site_root: Path) -> EgregoraConfig:
    """Create .egregora/config.yml with defaults."""
    config = EgregoraConfig()  # All defaults from Pydantic
    save_egregora_config(config, site_root)
    return config
```

**3. Update SitePaths** - SIMPLIFIED
```python
@dataclass(frozen=True)
class SitePaths:
    """All paths relative to .egregora/"""
    site_root: Path
    egregora_dir: Path  # .egregora/
    config_path: Path   # .egregora/config.yml
    prompts_dir: Path   # .egregora/prompts/
    rag_dir: Path       # .egregora/rag/
    cache_dir: Path     # .egregora/.cache/

    # Content dirs (still in docs/)
    docs_dir: Path
    posts_dir: Path
    profiles_dir: Path
    media_dir: Path

    @classmethod
    def from_site_root(cls, site_root: Path) -> "SitePaths":
        egregora = site_root / ".egregora"
        docs = site_root / "docs"

        return cls(
            site_root=site_root,
            egregora_dir=egregora,
            config_path=egregora / "config.yml",
            prompts_dir=egregora / "prompts",
            rag_dir=egregora / "rag",
            cache_dir=egregora / ".cache",
            docs_dir=docs,
            posts_dir=docs / "posts",
            profiles_dir=docs / "profiles",
            media_dir=docs / "media",
        )
```

**4. Remove mkdocs.yml dependency**
- Delete all `load_mkdocs_config()` calls for egregora config
- mkdocs.yml ONLY for MkDocs rendering (theme, nav, etc.)
- Egregora config is ONLY in .egregora/config.yml

### Week 2: Scaffolding & Integration

**5. Update site scaffolding**
```python
def create_site_structure(site_root: Path) -> SitePaths:
    """Create .egregora/ structure - ALWAYS, every time."""
    paths = SitePaths.from_site_root(site_root)

    # Create all directories
    paths.egregora_dir.mkdir(exist_ok=True)
    paths.prompts_dir.mkdir(exist_ok=True)
    paths.rag_dir.mkdir(exist_ok=True)
    paths.cache_dir.mkdir(exist_ok=True)
    paths.docs_dir.mkdir(exist_ok=True)
    paths.posts_dir.mkdir(exist_ok=True)
    paths.profiles_dir.mkdir(exist_ok=True)
    paths.media_dir.mkdir(exist_ok=True)

    # Create config if missing
    if not paths.config_path.exists():
        config = EgregoraConfig()
        save_egregora_config(config, site_root)

    # Create prompts README
    (paths.prompts_dir / "README.md").write_text(
        "# Custom Prompts\n\n"
        "Place custom prompt overrides here.\n"
        "Use same filenames as package defaults.\n"
    )

    # Create .gitignore
    (paths.egregora_dir / ".gitignore").write_text(
        "# Ephemeral data\n"
        ".cache/\n"
        "rag/*.duckdb\n"
        "rag/*.parquet\n"
    )

    return paths
```

**6. Update ALL consumers**
```python
# OLD (14 parameters!)
def write_posts_with_pydantic_agent(
    prompt, model, period, output_dir, profiles_dir, rag_dir,
    client, embedding_model, retrieval_mode, retrieval_nprobe,
    retrieval_overfetch, annotations_store, agent_model, register_tools
):
    ...

# NEW (2 parameters!)
def write_posts_with_pydantic_agent(
    prompt: str,
    context: WriterContext,
) -> RunResult:
    """Run writer agent.

    Args:
        prompt: The conversation to write about
        context: All configuration and paths (frozen dataclass)
    """
    config = context.config  # EgregoraConfig from .egregora/
    paths = context.paths    # SitePaths

    agent = create_writer_agent(
        model=config.models.writer,
        deps=WriterDeps(config=config, paths=paths, ...),
    )

    return agent.run_sync(prompt, deps=deps)
```

---

## Phase 1: Pydantic-AI Compliance (Week 3) - SIMPLIFIED

**Only 2 real issues to fix:**

### Issue 1: Deps Mutation (SIMPLE FIX)

```python
# OLD (WRONG) - mutates deps
@agent.tool
def write_post_tool(ctx: RunContext[WriterDeps], ...) -> WritePostResult:
    path = write_post(...)
    ctx.deps.saved_posts.append(path)  # ❌ MUTATION!
    return WritePostResult(...)

# NEW (CORRECT) - track in result
@agent.tool
def write_post_tool(ctx: RunContext[WriterDeps], ...) -> WritePostResult:
    path = write_post(...)
    # Don't mutate deps - just return result
    return WritePostResult(status="success", path=str(path))

# Extract posts from tool call history
def get_saved_posts(result: RunResult) -> list[Path]:
    """Extract all write_post_tool calls."""
    posts = []
    for msg in result.all_messages():
        if hasattr(msg, 'tool_calls'):
            for call in msg.tool_calls:
                if call.tool_name == 'write_post_tool':
                    posts.append(Path(call.result.path))
    return posts
```

### Issue 2: Use Frozen Dataclasses

```python
# Simple frozen deps - no mutation possible
@dataclass(frozen=True)
class WriterDeps:
    config: EgregoraConfig
    paths: SitePaths
    client: genai.Client
    annotations_store: AnnotationStore | None

# That's it - can't mutate even if you try!
```

**No other changes needed** - current tool registration is CORRECT!

---

## Phase 2-5: Exactly As Planned (Week 4-8)

No changes - these were already clean. Just use the new config system.

---

## Phase 6: Parser Modernization (Week 9-10) - SIMPLIFIED

**No backward compat for old parser!**

```python
# Before: Keep old parser as fallback
# After: Just delete it and use pyparsing

# Delete these files:
# - OLD: Complex regex parser
# - NEW: pyparsing only

# Single parser, clean implementation
class WhatsAppParser:
    def __init__(self):
        self.grammar = build_whatsapp_grammar()  # pyparsing

    def parse_line(self, line: str) -> Message | None:
        try:
            result = self.grammar.parse_string(line)
            return Message.from_parse_result(result)
        except ParseException:
            return None  # Continuation line
```

**No dual parsers, no validation, just swap!**

---

## Timeline: 11 WEEKS (vs 14 in original)

| Phase | Weeks | What | Simplification Benefit |
|-------|-------|------|------------------------|
| Phase 0 | 1.5 | Config (no compat!) | -0.5 weeks |
| Phase 1 | 0.5 | Pydantic-AI (just 2 fixes) | -0.5 weeks |
| Phase 2 | 1 | Config objects | Same |
| Phase 3 | 2 | Pipeline decomp | Same |
| Phase 4 | 1 | Remaining | Same |
| Phase 5 | 1 | Testing | -0.5 weeks (no compat tests) |
| Phase 6 | 2 | Parser | Same |
| Phase 7 | 2 | RAG | Same |
| **TOTAL** | **11** | | **-3 weeks saved!** |

Domain value objects (old Phase 8) → Do incrementally later

---

## What We're Deleting

### 1. All Backward Compatibility Code
```python
# DELETE THIS ENTIRE PATTERN
def load_config(site_root: Path) -> Config:
    # Try new format
    if new_format_exists():
        return load_new()
    # Try old format  # ❌ DELETE
    if old_format_exists():  # ❌ DELETE
        return load_old()  # ❌ DELETE
    return defaults()

# REPLACE WITH
def load_config(site_root: Path) -> EgregoraConfig:
    config_path = site_root / ".egregora" / "config.yml"
    if not config_path.exists():
        return create_default_config(site_root)
    return EgregoraConfig(**yaml.safe_load(config_path.read_text()))
```

### 2. All Legacy Transformation
```python
# DELETE
def _transform_legacy_config(old: dict) -> dict:
    # 50 lines of transformation logic
    ...

# DON'T NEED IT - just use new format!
```

### 3. All Migration Documentation
```python
# DELETE migration guides
# DELETE "how to upgrade" docs
# DELETE compatibility warnings

# REPLACE WITH
# "Run egregora init to create .egregora/"
# That's it!
```

### 4. All Dual Code Paths
```python
# DELETE
if use_new_system:
    do_new_way()
else:  # ❌ DELETE
    do_old_way()  # ❌ DELETE

# REPLACE WITH
do_new_way()  # Just one way!
```

---

## Breaking Changes (Who Cares, We're Alpha!)

### Breaking Change 1: Config Location
- **Before**: mkdocs.yml extra.egregora
- **After**: .egregora/config.yml
- **Migration**: `egregora init` creates it
- **Impact**: None (alpha, no users)

### Breaking Change 2: No mkdocs.yml Config
- **Before**: Could configure via mkdocs.yml
- **After**: MUST use .egregora/config.yml
- **Migration**: Just create .egregora/
- **Impact**: None (alpha, no users)

### Breaking Change 3: Parser Replacement
- **Before**: Regex parser
- **After**: pyparsing
- **Migration**: Just works, parse format unchanged
- **Impact**: None (same inputs, better code)

### Breaking Change 4: RAG Architecture
- **Before**: Monolithic search
- **After**: Strategy pattern
- **Migration**: API stays same, internals change
- **Impact**: None (same behavior)

**Total breaking changes that matter**: 0 (we're in alpha!)

---

## Simplified Success Criteria

### Must Have
- ✅ All 62 complexity errors → 0
- ✅ Pydantic-AI compliant
- ✅ Config in .egregora/ ONLY
- ✅ No backward compat code
- ✅ Tests pass

### Should Have
- ✅ Parser: pyparsing (clean)
- ✅ RAG: Strategy pattern
- ✅ Code: 30% less than original plan

### Nice to Have
- ✅ Documentation: Simple "here's how it works"
- ✅ No migration guides (not needed!)

---

## What This Means for Implementation

### Before (With Compat)
```python
# config/loader.py - 250 lines
def load_config():
    # Try .egregora/
    # Try mkdocs.yml
    # Transform legacy
    # Handle both formats
    # Deprecation warnings
    ...

# site.py - Keep old SitePaths
# pipeline.py - Support both configs
# cli.py - Accept old + new params
```

### After (No Compat)
```python
# config/loader.py - 80 lines
def load_config(site_root: Path) -> EgregoraConfig:
    path = site_root / ".egregora" / "config.yml"
    if not path.exists():
        return create_default_config(site_root)
    return EgregoraConfig(**yaml.safe_load(path.read_text()))

# site.py - New SitePaths only
# pipeline.py - New config only
# cli.py - New params only
```

**70% less code, 0% complexity!**

---

## Execution Plan

### Week 1: Clean Break
1. Create schema.py (Pydantic models)
2. Create loader.py (simple, no compat)
3. Update SitePaths (new structure)
4. Update scaffolding (always create .egregora/)
5. **Delete all mkdocs.yml config loading for egregora**

### Week 2: Wire It Up
1. Update CLI to use new config
2. Update agents to use new config
3. Update pipeline to use new config
4. Run tests, fix breaks
5. Done with Phase 0!

### Week 3-11: As Planned
- Phase 1-7 proceed as documented
- Each phase cleaner without compat code
- Faster implementation
- Less testing surface

---

## Files to DELETE

1. All legacy transformation functions
2. All "try old, try new" logic
3. All migration utilities
4. All compat shims
5. All deprecation warnings

**Estimate**: Delete ~500 lines, add ~200 lines = Net -300 lines!

---

## Alpha Advantages

1. **Speed**: -3 weeks (11 vs 14)
2. **Simplicity**: -30% code
3. **Clarity**: One way to do things
4. **Maintainability**: No dual code paths
5. **Flexibility**: Can change .egregora/ format freely

---

## When We Hit Beta

If we need to support old sites later:
1. Write one-time migration script
2. Run on all known sites (0 sites in alpha!)
3. Delete script after migration
4. Still no compat code in codebase

**But we're not there yet - full speed ahead!** 🚀

---

## TL;DR

### Original Plan
- 14 weeks
- Backward compatible
- Legacy support
- Dual code paths
- Migration guides

### Simplified Plan (Alpha)
- **11 weeks** (-21%)
- **No backward compat** (YOLO!)
- **New format only** (.egregora/)
- **One code path** (clean!)
- **No migration** (just works!)

### Result
- Same outcomes (62 errors fixed)
- Faster delivery (3 weeks saved)
- Cleaner code (30% less)
- Simpler architecture (no compat)
- More flexibility (can change freely)

**RECOMMENDATION: THIS VERSION** - Alpha mindset FTW! 🎉
