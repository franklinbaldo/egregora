# Ruff Compliance Refactoring Plan

**Goal:** Eliminate all 28 remaining ruff complexity violations to achieve 100% clean ruff check.

**Current Status:** 28 violations (13 PLR0913, 8 PLR0912, 5 PLR0915, 2 PLW0603)

---

## Priority 1: Monster Functions (CRITICAL)

### 1. `writer.py:write_posts_for_period()` - Line 246
**Severity:** 🔴 CRITICAL
**Issues:** 99 statements, 26 branches, 8 arguments
**Current Signature:**
```python
async def write_posts_for_period(
    df: pl.DataFrame,
    date: str,
    group_slug: GroupSlug,
    posts_dir: Path,
    profiles_dir: Path,
    client: genai.Client,
    rag_dir: Path,
    model_config: ModelConfig | None = None,
    enable_rag: bool = True,
) -> dict:
```

**Refactoring Strategy:**
1. **Extract Config Object** - Create `WriterConfig` dataclass:
   ```python
   @dataclass
   class WriterConfig:
       posts_dir: Path
       profiles_dir: Path
       rag_dir: Path
       model_config: ModelConfig | None = None
       enable_rag: bool = True
   ```

2. **Break into smaller functions:**
   - `_prepare_writing_context(df, date, group_slug, config)` - Handle RAG setup, model config
   - `_generate_post_with_llm(client, prompt, tools, model)` - LLM interaction loop
   - `_handle_tool_calls(response, snapshot, editor, rag_dir, client, config)` - Process tool calls
   - `_save_post_and_profile(snapshot, metadata, config, group_slug, date)` - Persistence
   - `_update_rag_index(post_path, rag_dir, client, config)` - RAG indexing

3. **Reduce branches:**
   - Use early returns for validation
   - Extract nested if/else into guard clauses
   - Use strategy pattern for tool call handlers

**Expected Improvement:**
99 statements → ~20-30 per function
26 branches → ~5-8 per function
8 arguments → 3-4 per function

---

### 2. `ranking/agent.py:run_comparison()` - Line 190
**Severity:** 🔴 CRITICAL
**Issues:** 64 statements, 16 branches, 6 arguments
**Current Signature:**
```python
def run_comparison(
    site_dir: Path,
    post_a_id: str,
    post_b_id: str,
    profile_id: str,
    api_key: str,
    model: str,
) -> dict:
```

**Refactoring Strategy:**
1. **Extract Config Object** - Create `ComparisonConfig`:
   ```python
   @dataclass
   class ComparisonConfig:
       site_dir: Path
       api_key: str
       model: str
       profile_id: str
   ```

2. **Break into functions:**
   - `_load_comparison_data(site_dir, post_a_id, post_b_id)` - Load posts and profiles
   - `_run_turn1_choose_winner(client, post_a_content, post_b_content, model)` - Turn 1
   - `_run_turn2_comment_a(client, winner, post_a_content, profile_a, model)` - Turn 2
   - `_run_turn3_comment_b(client, winner, post_b_content, profile_b, model)` - Turn 3
   - `_extract_tool_response(response, tool_name)` - Parse tool calls
   - `_update_elo_and_save(store, comparison_data)` - Persist results

3. **Reduce branches:**
   - Extract winner logic into separate function
   - Use dictionary dispatch for turn handlers
   - Early returns for validation

**Expected Improvement:**
64 statements → ~15-20 per function
16 branches → ~4-6 per function
6 arguments → 2-3 per function

---

### 3. `cli.py:rank()` - Line 338
**Severity:** 🟠 HIGH
**Issues:** 58 statements, 15 branches, 6 arguments
**Current Signature:**
```python
def rank(
    self,
    site_dir: str,
    comparisons: int = 1,
    strategy: str = "fewest_games",
    export_parquet: bool = False,
    gemini_key: str | None = None,
    model: str | None = None,
    debug: bool = False,
) -> None:
```

**Refactoring Strategy:**
1. **Extract Config Object** - Create `RankingCliConfig`:
   ```python
   @dataclass
   class RankingCliConfig:
       site_dir: Path
       comparisons: int = 1
       strategy: str = "fewest_games"
       export_parquet: bool = False
       model: str | None = None
       debug: bool = False
   ```

2. **Break into methods:**
   - `_setup_ranking_environment(config)` - Setup logging, paths, API key
   - `_initialize_ranking_system(site_path, posts_dir, rankings_dir)` - Init store
   - `_run_single_comparison(config, site_path, rankings_dir, ranking_model)` - One comparison
   - `_export_rankings_if_requested(config, rankings_dir)` - Conditional export
   - `_display_ranking_summary(store)` - Stats display

3. **Reduce branches:**
   - Use early returns for validation
   - Extract API key resolution into helper
   - Consolidate error handling

**Expected Improvement:**
58 statements → ~10-15 per function
15 branches → ~3-5 per function
6 arguments → 1-2 per function (using config)

---

## Priority 2: Large Functions

### 4. `editor_agent.py:run_editor_session()` - Line 228
**Issues:** 57 statements, 17 branches
**Strategy:**
- Extract `_setup_editor_context()` - RAG, snapshot, prompt
- Extract `_editor_conversation_loop()` - Main LLM interaction
- Extract `_process_editor_tools()` - Tool call handling
- Extract `_finalize_editor_session()` - Save and return

### 5. `pipeline.py:process_whatsapp_export()` - Line 100
**Issues:** 13 branches
**Strategy:**
- Extract `_validate_export_inputs()` - Validation logic
- Extract `_process_export_stage()` - Pipeline stages
- Use strategy pattern for different processing modes

### 6. `enricher.py:_enrich_with_llm()` - Line 405
**Issues:** 13 branches
**Strategy:**
- Extract `_select_enrichment_targets()` - URL/media selection
- Extract `_generate_enrichment()` - LLM call per item
- Use batch processing instead of nested loops

---

## Priority 3: Too Many Arguments (13 functions)

### General Strategy for All:
1. **Group related parameters into config objects**
2. **Use builder pattern for complex construction**
3. **Leverage dependency injection where appropriate**

### Specific Functions:

**cli.py:process() - 10 arguments**
```python
# BEFORE
def process(self, zip_file, output_dir, days, from_date, timezone,
            anonymize, gemini_key, model, config_file, debug)

# AFTER
@dataclass
class ProcessConfig:
    zip_file: Path
    output_dir: Path
    days: int | None = None
    from_date: date | None = None
    timezone: str | None = None
    anonymize: bool = True
    model: str | None = None
    config_file: Path | None = None
    debug: bool = False

def process(self, config: ProcessConfig, gemini_key: str | None = None)
```

**cli.py:_run_pipeline() - 9 arguments**
→ Use same `ProcessConfig` from parent

**ranking/agent.py:save_comparison() - 9 arguments**
```python
# Create ComparisonData dataclass
@dataclass
class ComparisonData:
    comparison_id: str
    timestamp: datetime
    profile_id: str
    post_a: str
    post_b: str
    winner: str
    comment_a: str
    stars_a: int
    comment_b: str
    stars_b: int

def save_comparison(store: RankingStore, data: ComparisonData)
```

**prompt_templates.py functions (7 params each)**
```python
# Create PromptContext dataclasses
@dataclass
class WriterPromptContext:
    date: str
    markdown_table: str
    active_authors: str
    group_name: str
    custom_instructions: str
    enable_rag: bool
    rag_context: str

@dataclass
class MediaEnrichmentContext:
    media_type: str
    media_filename: str
    author: str
    timestamp: str
    nearby_messages: str
    ocr_text: str
    detected_objects: str

def render_writer_prompt(ctx: WriterPromptContext) -> str
def render_media_enrichment_detailed_prompt(ctx: MediaEnrichmentContext) -> str
```

**writer.py:_generate_post() - 8 arguments**
→ Extract `PostGenerationContext` dataclass

**enricher.py functions (7-8 arguments)**
→ Extract `EnrichmentContext` dataclass

---

## Priority 4: Global Statement Warnings (2 functions)

### 1. `genai_utils.py:_last_call_monotonic` - Line ~90
**Current Issue:** Global variable for rate limiting

**Solution:** Use class-based rate limiter
```python
class RateLimiter:
    def __init__(self, min_interval: float = 1.0):
        self._last_call: float = 0.0
        self._min_interval = min_interval

    def wait_if_needed(self):
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

# Usage
_rate_limiter = RateLimiter(min_interval=1.0)

async def call_with_retries(...):
    _rate_limiter.wait_if_needed()
    # ... rest of function
```

### 2. `zip_utils.py:_DEFAULT_LIMITS` - Line 37
**Current Issue:** Global variable for validation limits

**Solution:** Use module-level constant + function parameter
```python
# Module level (immutable)
DEFAULT_LIMITS = ValidationLimits(
    max_file_size=100 * 1024 * 1024,
    max_total_size=500 * 1024 * 1024,
    max_files=10000
)

# Pass explicitly instead of global
def validate_zip_contents(
    zip_path: Path,
    limits: ValidationLimits = DEFAULT_LIMITS
) -> None:
    # Use limits parameter
```

---

## Implementation Order

1. **Phase 1: Config Objects** (1-2 hours)
   - Create all dataclass configs
   - Update function signatures to accept configs
   - Update all call sites

2. **Phase 2: Function Extraction** (3-4 hours)
   - Refactor `write_posts_for_period()` (biggest impact)
   - Refactor `run_comparison()`
   - Refactor `cli.py:rank()`
   - Refactor other complex functions

3. **Phase 3: Global Variable Cleanup** (30 mins)
   - Convert to class-based rate limiter
   - Remove global statement from zip_utils

4. **Phase 4: Verification** (30 mins)
   - Run `uv run ruff check src/` - expect 0 errors
   - Run existing tests
   - Manual smoke test of CLI commands

---

## Testing Strategy

**For Each Refactored Function:**
1. Write unit tests BEFORE refactoring (characterization tests)
2. Refactor while keeping tests green
3. Add new tests for extracted functions
4. Verify integration with smoke tests

**Critical Smoke Tests:**
```bash
# Test process pipeline
uv run egregora process test.zip output --days 2

# Test ranking
uv run egregora rank output --comparisons 1

# Test editor
uv run egregora edit output/posts/2024/01/01/some-post.md
```

---

## Risks & Mitigation

**Risk 1:** Breaking existing functionality
**Mitigation:** Comprehensive test coverage before refactoring

**Risk 2:** Config objects make code verbose
**Mitigation:** Use builder pattern, sensible defaults, type hints

**Risk 3:** Too many small functions hurt readability
**Mitigation:** Keep related logic together, clear function names

---

## Success Criteria

- ✅ `uv run ruff check src/` returns 0 errors
- ✅ All existing tests pass
- ✅ Smoke tests verify CLI functionality
- ✅ Code is more readable and maintainable
- ✅ Functions are single-responsibility
- ✅ No function >50 statements
- ✅ No function >12 branches
- ✅ No function >5 parameters
- ✅ No global variable mutations

---

## Estimated Time: 6-8 hours

**Breakdown:**
- Config objects: 1-2h
- writer.py refactor: 2h
- ranking/agent.py refactor: 1.5h
- cli.py refactor: 1h
- Other functions: 1h
- Global cleanup: 0.5h
- Testing & verification: 1h
