# Refactoring Plan: Configuration & Documentation Improvements

## Context

Based on codebase analysis during documentation update, these improvements address real pain points without adding unnecessary complexity. All recommendations aligned with "alpha mindset" - clean, simple solutions.

**Note on Async/Parallel Processing:** Parallel window processing is NOT in roadmap. Sequential processing is essential for correct content understanding, and API rate limits make parallelization impractical. Current async RAG integration with `asyncio.run()` wrappers is acceptable.

## Agreed Upon Improvements

### 1. Make Privacy Configuration Functional

**Current State:**
```python
class PrivacySettings(BaseModel):
    """Privacy and data protection settings (YAML configuration).

    .. note::
       Currently all privacy features (anonymization, PII detection) are always enabled.
       This config section is reserved for future configurable privacy controls.
```

**Problem:** Can't disable privacy features for public datasets (judicial records, public archives)

**Goal:** Make privacy behavior configurable while keeping secure defaults

**Implementation:**
1. Add real settings to `PrivacySettings` in `config/settings.py`:
   ```python
   class PrivacySettings(BaseModel):
       """Privacy and data protection settings."""

       enabled: bool = Field(
           default=True,
           description="Enable privacy features (anonymization, PII detection)"
       )

       pii_detection_enabled: bool = Field(
           default=True,
           description="Enable PII detection and warnings"
       )

       pii_action: Literal["warn", "redact", "skip"] = Field(
           default="warn",
           description=(
               "Action on PII detection: "
               "warn=log warning, redact=replace with [REDACTED], skip=skip message"
           )
       )

       anonymize_authors: bool = Field(
           default=True,
           description="Anonymize author names with UUIDs"
       )

       custom_pii_patterns: list[str] = Field(
           default_factory=list,
           description="Additional regex patterns for PII detection"
       )
   ```

2. Wire settings through `egregora.privacy` module:
   - Update `privacy/config.py` runtime dataclass to read from config
   - Update `privacy/anonymizer.py` to respect `anonymize_authors` setting
   - Update `privacy/detector.py` to respect `pii_detection_enabled` and `pii_action`

3. Add validation:
   - If `enabled=False`, require explicit user confirmation in config comments
   - Validate that disabling privacy is intentional

4. Update documentation:
   - Add section in `docs/features/privacy.md` on disabling privacy
   - Document use cases (public datasets, judicial records)
   - Add warning about implications

**Files Changed:**
- `src/egregora/config/settings.py` - Add PrivacySettings fields
- `src/egregora/privacy/config.py` - Wire settings
- `src/egregora/privacy/anonymizer.py` - Respect anonymize_authors
- `src/egregora/privacy/detector.py` - Respect pii_detection_enabled and pii_action
- `docs/features/privacy.md` - Document new settings
- `CLAUDE.md` - Update configuration reference
- `tests/unit/privacy/` - Add tests for all settings combinations

**Impact:** Unlocks public dataset use cases while maintaining secure defaults

---

### 2. Comprehensive API Documentation via mkdocstrings

**Current State:**
- mkdocstrings is configured in `mkdocs.yml`
- API reference pages exist in `docs/api/` but are mostly stubs
- Many functions lack docstrings

**Goal:** Generate full API reference from code with proper docstrings

**Implementation:**

**Phase 1: Add docstrings to public APIs (high-priority modules)**
1. `data_primitives/document.py` - Document, DocumentType, MediaAsset
2. `input_adapters/base.py` - InputAdapter protocol
3. `output_adapters/base.py` - OutputAdapter protocol
4. `config/settings.py` - All settings classes (partially done)
5. `rag/models.py` - RAGQueryRequest, RAGResponse
6. `agents/writer.py` - write_posts_for_window
7. `transformations/windowing.py` - create_windows

**Phase 2: Configure mkdocstrings properly**
Update `docs/api/*.md` to use mkdocstrings syntax:
```markdown
# Document API

::: egregora.data_primitives.document
    options:
      show_source: true
      show_root_heading: true
      show_category_heading: true
      members_order: source
      show_if_no_docstring: false  # Hide undocumented items
```

**Phase 3: Add examples to docstrings**
Use Google-style docstrings with examples:
```python
def create_windows(
    messages: Table,
    step_size: int,
    step_unit: str,
) -> Iterator[Table]:
    """Create sliding windows over message table.

    Args:
        messages: Ibis table with IR_MESSAGE_SCHEMA
        step_size: Window size in step_unit units
        step_unit: One of "messages", "hours", "days"

    Yields:
        Ibis table for each window

    Example:
        >>> windows = create_windows(messages, step_size=100, step_unit="messages")
        >>> for window in windows:
        ...     print(len(window))
        100
        100
        ...
    """
```

**Files Changed:**
- `src/egregora/data_primitives/document.py` - Add docstrings
- `src/egregora/input_adapters/base.py` - Add docstrings
- `src/egregora/output_adapters/base.py` - Add docstrings
- `src/egregora/rag/models.py` - Add docstrings
- `src/egregora/agents/writer.py` - Add docstrings
- `src/egregora/transformations/windowing.py` - Add docstrings
- `docs/api/data-primitives.md` - Use mkdocstrings syntax
- `docs/api/input-adapters.md` - Use mkdocstrings syntax
- `docs/api/output-adapters.md` - Use mkdocstrings syntax
- `docs/api/rag.md` - Enhance with more modules
- `mkdocs.yml` - Verify mkdocstrings config (already done)

**Impact:** Better developer experience, easier onboarding, fewer support questions

---

### 3. Better Configuration Validation & Error Messages

**Current State:**
- Pydantic validation exists but errors are cryptic
- No way to validate config without running full pipeline
- No friendly "did you mean?" suggestions

**Goal:** User-friendly config validation with helpful error messages

**Implementation:**

**1. Add `egregora config validate` command**
```python
# cli/config.py (NEW)
import typer
from egregora.config.settings import load_egregora_config
from pydantic import ValidationError

config_app = typer.Typer(help="Configuration management commands")

@config_app.command()
def validate(
    config_path: Path = typer.Option(
        Path(".egregora/config.yml"),
        help="Path to config file"
    ),
) -> None:
    """Validate configuration file and show friendly errors."""
    try:
        config = load_egregora_config(config_path.parent)
        typer.secho("✅ Configuration is valid!", fg=typer.colors.GREEN)
        typer.echo(f"Loaded from: {config_path}")
    except ValidationError as e:
        typer.secho("❌ Configuration errors found:", fg=typer.colors.RED)
        for error in e.errors():
            loc = " → ".join(str(l) for l in error["loc"])
            msg = error["msg"]
            typer.echo(f"  {loc}: {msg}")
        raise typer.Exit(1)
    except Exception as e:
        typer.secho(f"❌ Error loading config: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
```

**2. Add custom validators with better messages**
```python
# config/settings.py
from pydantic import field_validator, model_validator

class ModelSettings(BaseModel):
    writer: PydanticModelName = ...

    @field_validator("writer", "enricher", "reader")
    @classmethod
    def validate_model_format(cls, v: str) -> str:
        """Validate model name format."""
        if not v.startswith(("google-gla:", "models/")):
            msg = (
                f"Invalid model format: {v}\n"
                f"Expected format:\n"
                f"  - Pydantic-AI: 'google-gla:gemini-flash-latest'\n"
                f"  - Google SDK: 'models/gemini-flash-latest'"
            )
            raise ValueError(msg)
        return v

class RAGSettings(BaseModel):
    top_k: int = Field(default=5, ge=1, le=100)

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, v: int) -> int:
        """Validate top_k is reasonable."""
        if v > 50:
            logger.warning(
                f"top_k={v} is unusually high. "
                f"Consider values between 5-20 for better performance."
            )
        return v

class EgregoraConfig(BaseModel):
    ...

    @model_validator(mode="after")
    def validate_cross_field(self) -> EgregoraConfig:
        """Validate cross-field dependencies."""
        # If RAG is enabled, ensure lancedb_dir is set
        if self.rag.enabled and not self.paths.lancedb_dir:
            msg = "RAG is enabled but paths.lancedb_dir is not set"
            raise ValueError(msg)

        # Warn if privacy is disabled
        if not self.privacy.enabled:
            logger.warning(
                "⚠️  Privacy features are DISABLED. "
                "Only use for public datasets!"
            )

        return self
```

**3. Add config file location to error messages**
Update `load_egregora_config()` to show where it's looking:
```python
def load_egregora_config(output_dir: Path) -> EgregoraConfig:
    """Load configuration from .egregora/config.yml."""
    config_path = output_dir / ".egregora" / "config.yml"

    try:
        if not config_path.exists():
            logger.info(f"No config found at {config_path}, using defaults")
            return EgregoraConfig()

        with config_path.open() as f:
            raw = yaml.safe_load(f)

        logger.debug(f"Loading config from {config_path}")
        return EgregoraConfig(**raw)

    except ValidationError as e:
        logger.error(f"Configuration errors in {config_path}:")
        raise
```

**Files Changed:**
- `src/egregora/cli/config.py` - NEW: Config management commands
- `src/egregora/cli/main.py` - Register config_app
- `src/egregora/config/settings.py` - Add validators with better messages
- `docs/configuration.md` - Document `config validate` command
- `CLAUDE.md` - Add to CLI commands reference

**Impact:** Much better UX, easier troubleshooting, catches errors early

---

## Implementation Order

1. **Config Validation** (2 hours)
   - Immediate user value
   - Catches errors early
   - Low risk, high impact
   - Foundation for privacy settings validation

2. **Privacy Configuration** (3 hours)
   - More complex - needs testing
   - Security-sensitive - needs careful review
   - Medium risk, unlocks new use cases
   - Benefits from config validation work

3. **API Documentation** (4 hours)
   - Add docstrings to priority modules
   - Update API reference pages
   - Medium effort, high long-term value
   - Can be done in parallel with other work

**Total estimated time: ~9 hours**

## Testing Strategy

### Config Validation
- Test with valid config → should succeed
- Test with invalid model names → friendly error
- Test with missing required fields → helpful message
- Test with cross-field errors → clear guidance

### Privacy Configuration
- Test with `privacy.enabled=false` → no anonymization
- Test with `pii_action=redact` → PII replaced
- Test with `pii_action=skip` → messages skipped
- Test with public dataset (judicial records)
- Verify default behavior unchanged (enabled=true)

### API Documentation
- Run `mkdocs build` - should succeed
- Check generated API docs have proper formatting
- Verify examples render correctly
- Test with `show_if_no_docstring: false` to find gaps

## Documentation Updates

- [ ] `CLAUDE.md` - Update configuration reference
- [ ] `docs/configuration.md` - Document new settings
- [ ] `docs/features/privacy.md` - Privacy configuration guide
- [ ] `docs/api/*.md` - Enhanced API reference
- [ ] `docs/cli-reference.md` - Add `config validate` command
- [ ] `docs/architecture/pipeline.md` - Add "Why Sequential Processing?" section

## Success Criteria

- ✅ Privacy can be disabled for public datasets
- ✅ Config validation catches errors with helpful messages
- ✅ API docs auto-generated from docstrings
- ✅ All tests pass
- ✅ Documentation updated

## Non-Goals

- ❌ Async/parallel pipeline (not in roadmap, sequential processing is essential)
- ❌ Migration tooling (not needed yet, alpha mindset)
- ❌ Docker support (can add later)
- ❌ Move constants from settings.py (configuration defaults belong with configuration)
- ❌ Remove legacy RAG (already removed)
- ❌ Extract embedding router (premature)

---

## Sequential Processing Rationale

Add section to `docs/architecture/pipeline.md` explaining why parallel window processing is not planned:

**Why Sequential Processing?**
- **API Rate Limits:** Google Gemini API has strict rate limits (1 req/sec). Parallel processing would quickly exhaust quotas without significant throughput gains.
- **Context Understanding:** Each window builds on previous windows' context. Sequential processing ensures the LLM has temporal continuity for coherent narrative.
- **Deterministic Output:** Sequential execution produces consistent results across runs. Parallel execution could introduce non-determinism in post ordering and content.
- **Sufficient Performance:** Current async RAG integration provides I/O overlap where it matters (embeddings, vector search). Window generation is CPU-bound (LLM calls), not I/O-bound.
- **Simpler Architecture:** Sequential execution is easier to reason about, debug, and test. No need for complex concurrency primitives or distributed coordination.

**Current Async Usage:**
- RAG operations (indexing, search) are fully async
- Wrapped in `asyncio.run()` from sync pipeline orchestration
- This is optimal - keeps complexity localized to I/O operations
