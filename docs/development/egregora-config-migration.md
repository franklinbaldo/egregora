# Egregora Configuration Migration: `.egregora/` Folder Structure

**Status**: In Progress (Phases 1-5 Complete)
**Date**: 2025-11-08 (Updated)
**Goal**: Extract Egregora configuration from `mkdocs.yml` into dedicated `.egregora/` directory

---

## Overview

This document describes the migration from embedding Egregora configuration in `mkdocs.yml` to a dedicated `.egregora/` folder structure. This change enables:

1. **Backend independence** - Egregora config separate from MkDocs (support Hugo, Astro, etc.)
2. **User customization** - Override prompts without modifying package code
3. **Type safety** - Pydantic V2 validation for configuration
4. **Cleaner separation** - Clear boundary between rendering and pipeline concerns
5. **Window-based processing** - Replaces period-based grouping with flexible windowing

### Update (2025-11-07): Windowing PR Compatibility Check

**PR #623** (`claude/replace-periods-with-windowing-011CUsvZWfA3SEo5nM6193ck`) implements Phase 1 of this plan **PLUS** windowing:

- ✅ Pydantic V2 schema (`config/schema.py`) with `EgregoraConfig` - **CONFIRMED in commit 4754862**
  - 8 config classes: `ModelSettings`, `RAGSettings`, `WriterConfig`, `PrivacySettings`, `EnrichmentSettings`, `PipelineSettings`, `FeaturesSettings`, `EgregoraConfig`
- ✅ Config loader (`config/loader.py`) - **CONFIRMED**
  - 4 functions: `find_egregora_config()`, `load_egregora_config()`, `create_default_config()`, `save_egregora_config()`
- ✅ Config facade pattern (`config/__init__.py`) - **CONFIRMED**
- ✅ Window-based processing (replaces period-based grouping) - **PRIMARY FOCUS OF PR #623**

**Compatibility**: ✅ This plan is fully compatible with PR #623. Phase 1 is complete, windowing is integrated.

**Remaining work**: Phases 2-6 (prompt overrides, scaffolding, consumer updates, docs, tests)

---

## Current State

### Configuration Location

**Current**: Configuration lives in `mkdocs.yml` under `extra.egregora`:

```yaml
extra:
  egregora:
    models:
      writer: models/gemini-2.0-flash-exp
      enricher: models/gemini-1.5-flash
      enricher_vision: models/gemini-1.5-flash
      embedding: models/text-embedding-004
      ranking: models/gemini-2.0-flash-exp
      editor: models/gemini-2.0-flash-exp
    writer_prompt: "Custom instructions..."
    rag:
      enabled: true
      top_k: 5
      min_similarity_threshold: 0.7
    profiles:
      top_authors_count: 20
      include_in_context: true
```

### Code Access Points

Configuration is accessed in 8+ files:

- `config/model.py` - `ModelConfig` class, `load_site_config()`
- `config/site.py` - YAML loader `load_mkdocs_config()`
- `agents/writer/core.py` - Writer prompt, meme settings, markdown extensions
- `cli.py` - All CLI commands (process, edit, rank, enrich, etc.)
- `pipeline/runner.py` - Pipeline initialization
- `enrichment/core.py` - Enrichment models
- `init/scaffolding.py` - Site creation

### Prompts Location

**Current**: Package-level in `src/egregora/prompts/` (not user-customizable):

```python
PROMPTS_DIR = Path(__file__).parent / "prompts"
DEFAULT_ENVIRONMENT = Environment(loader=FileSystemLoader(PROMPTS_DIR), ...)
```

Users cannot override prompts without modifying package code.

---

## Proposed Structure

### Directory Layout

```
site-root/
├── mkdocs.yml              # MkDocs-only config (theme, plugins, nav)
├── .egregora/              # Egregora configuration directory
│   ├── config.yml          # 🆕 Main configuration file
│   ├── prompts/            # 🆕 Optional custom prompt overrides (flat directory)
│   │   ├── README.md
│   │   ├── writer.jinja
│   │   ├── url_detailed.jinja
│   │   └── media_detailed.jinja
│   ├── agents/             # ✅ Agent configs (already exists)
│   │   ├── writer.jinja
│   │   ├── editor.jinja
│   │   └── ranking.jinja
│   ├── skills/             # ✅ Reusable prompt components
│   ├── tools/              # ✅ Tool profiles and quotas
│   └── global/             # ✅ Global settings (seeds, signing keys)
└── .egregora-cache/        # ✅ Cache directory (unchanged)
```

### Configuration File Format

**File**: `.egregora/config.yml` (as implemented in PR #623)

```yaml
# Egregora Configuration
# Separate from mkdocs.yml to support multiple rendering backends

# Model configuration (uses pydantic-ai format: provider:model-name)
models:
  writer: google-gla:gemini-2.0-flash-exp
  enricher: google-gla:gemini-flash-latest
  enricher_vision: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001
  ranking: google-gla:gemini-2.0-flash-exp      # Optional
  editor: google-gla:gemini-2.0-flash-exp       # Optional

# Writer agent settings
writer:
  # Custom instructions appended to system prompt
  custom_instructions: |
    Write analytical posts in the style of Scott Alexander / LessWrong.
    Focus on capturing narrative threads and preserving complexity.

  # Enable banner image generation
  enable_banners: true

  # Maximum tokens per prompt
  max_prompt_tokens: 100000             # Default 100k cap
  use_full_context_window: false        # Override cap with full model context

# RAG (Retrieval-Augmented Generation) settings
rag:
  enabled: true
  top_k: 5                              # Number of results to retrieve
  min_similarity_threshold: 0.7                   # Minimum similarity threshold (0-1)
  mode: ann                             # 'ann' (approximate) or 'exact'
  nprobe: 10                            # ANN search quality (1-100, higher = better + slower)
  overfetch: 3                          # Overfetch multiplier for ANN candidate pool

# Privacy settings
privacy:
  anonymization_enabled: true           # Convert names to UUIDs
  pii_detection_enabled: true           # Scan for PII (phones, emails, addresses)

# Enrichment settings
enrichment:
  url_enabled: true                     # URL enrichment
  media_enabled: true                   # Media/image enrichment
  batch_size: 10                        # Batch API calls for efficiency

# Pipeline windowing settings (NEW in PR #623)
pipeline:
  # Window size and unit
  step_size: 100                        # Size of each processing window
  step_unit: messages                   # Unit: 'messages', 'hours', 'days', 'bytes'

  # Window boundaries
  min_window_size: 10                   # Minimum messages per window
  overlap_ratio: 0.2                    # Overlap fraction (0.0-0.5) for context continuity
  max_window_time: 168                  # Max hours per window (optional constraint)

  # Filtering
  from_date: "2024-01-01"               # Start date (ISO format, optional)
  to_date: "2024-12-31"                 # End date (ISO format, optional)
  timezone: "America/New_York"          # Timezone for timestamps

  # API batching
  batch_threshold: 10                   # Minimum items before batching API calls

  # Token limits
  max_prompt_tokens: 100000             # Max tokens per prompt (cost control)
  use_full_context_window: false        # Use full model context (overrides cap)

# Feature flags
features:
  ranking_enabled: false                # Elo-based post ranking
  annotations_enabled: true             # Conversation annotations/threading
```

**Note**: The `pipeline` section replaces the old `period` parameter with flexible windowing. Windows can be defined by message count, time spans, or byte size, with configurable overlap for context continuity.

### Prompt Override Mechanism

**Priority**:
1. `.egregora/prompts/writer.jinja` (user override)
2. `src/egregora/prompts/writer.jinja` (package default)

**Implementation**:
```python
def find_prompts_dir(site_root: Path) -> Path:
    """Find prompts directory with user override support."""
    user_prompts = site_root / ".egregora" / "prompts"
    if user_prompts.exists():
        return user_prompts
    # Fall back to package prompts
    return Path(__file__).parent / "prompts"
```

---

## Implementation Plan

### Phase 1: Config File Infrastructure ✅ COMPLETE (PR #623)

**Status**: ✅ Implemented in PR #623 (`claude/replace-periods-with-windowing-011CUsvZWfA3SEo5nM6193ck`)

This phase has been completed with the following implementations:

#### ✅ Step 1.1: Pydantic V2 config schema created

**Implemented**: `src/egregora/config/schema.py`

Complete Pydantic V2 models with validation:
- `EgregoraConfig` - Root config model
- `ModelSettings` - LLM model configuration
- `RAGSettings` - Retrieval settings (renamed fields: `mode`, `nprobe` instead of `retrieval_mode`, `retrieval_nprobe`)
- `WriterConfig` - Writer agent settings (includes `max_prompt_tokens`, `use_full_context_window`)
- `PrivacySettings` - Anonymization settings
- `EnrichmentSettings` - URL/media enrichment settings
- `PipelineSettings` - **NEW**: Windowing parameters (`step_size`, `step_unit`, `min_window_size`, `overlap_ratio`, `max_window_time`)
- `FeaturesSettings` - Feature flags (`ranking_enabled`, `annotations_enabled`)

**Key differences from original plan**:
- Uses Pydantic V2 with `ConfigDict` instead of V1
- `extra="forbid"` prevents unknown fields
- `PipelineSettings` replaces period-based grouping with windowing
- RAG fields renamed: `mode`/`nprobe`/`overfetch` (not `retrieval_mode`/`retrieval_nprobe`)
- Writer: `custom_instructions` (not `prompt`), `enable_banners` (not `enable_memes`)

#### ✅ Step 1.2: Config loader implemented

**Implemented**: `src/egregora/config/loader.py`

Functions:
- `find_egregora_config(start_dir: Path) -> Path | None` - Upward search for `.egregora/config.yml`
- `load_egregora_config(site_root: Path) -> EgregoraConfig` - Load and validate config
- `create_default_config(site_root: Path) -> EgregoraConfig` - Create default config if missing
- `save_egregora_config(config: EgregoraConfig, site_root: Path)` - Save config to YAML

**Strategy**: Clean break, no backward compatibility:
- ONLY loads from `.egregora/config.yml`
- Creates default config if missing
- No `mkdocs.yml` fallback
- No legacy transformation
- No deprecation warnings

#### ✅ Step 1.3: Config facade pattern implemented

**Implemented**: `src/egregora/config/__init__.py`

Facade pattern exports:
- All schema models (`EgregoraConfig`, `ModelSettings`, `RAGSettings`, etc.)
- Loader functions (`load_egregora_config`, `create_default_config`, `save_egregora_config`, `find_egregora_config`)
- Model utilities (`ModelConfig`, `ModelType`, `get_model_config`)
- Site paths (`SitePaths`, `resolve_site_paths`, `load_mkdocs_config`)
- Runtime contexts (`ProcessConfig`, `WriterConfig`, `EditorContext`, etc.)

Benefits:
- Simplified imports: `from egregora.config import EgregoraConfig`
- Stable API: Internal restructuring doesn't break consumers
- Better IDE autocomplete

#### ✅ Step 1.4: Window-based processing implemented

**Replaced**: Period-based grouping → Window-based processing

**New `ProcessConfig` fields**:
- `step_size: int` - Window size (default 100)
- `step_unit: str` - Unit: "messages", "hours", "days", "bytes"
- `min_window_size: int` - Minimum messages per window (default 10)
- `overlap_ratio: float` - Overlap fraction 0.0-0.5 (default 0.2)
- `max_window_time: timedelta | None` - Optional time constraint

**Removed**: `period: str` parameter

**Pipeline changes**:
- `create_windows()` function creates overlapping windows
- `Window` dataclass tracks `start_ts`, `end_ts`, `message_count`
- Resume logic uses timestamp-based identification (not window_id)
- Automatic window splitting for oversized prompts

---

### Phase 2: Custom Prompt Overrides ⏳ PENDING

**Status**: ⏳ Not yet implemented

This phase enables users to override system prompts without modifying package code.

#### Step 2.1: Update prompt template loader

**File**: `src/egregora/prompt_templates.py`

```python
def find_prompts_dir(site_root: Path | None = None) -> Path:
    """Find prompts directory with user override support.

    Priority:
    1. {site_root}/.egregora/prompts/ (user overrides)
    2. src/egregora/prompts/ (package defaults)

    Args:
        site_root: Site root directory to check for .egregora/

    Returns:
        Path to prompts directory
    """
    if site_root:
        user_prompts = site_root / ".egregora" / "prompts"
        if user_prompts.is_dir():
            logger.info("Using custom prompts from %s", user_prompts)
            return user_prompts

    # Fall back to package prompts
    package_prompts = Path(__file__).parent / "prompts"
    logger.debug("Using package prompts from %s", package_prompts)
    return package_prompts

def create_prompt_environment(site_root: Path | None = None) -> Environment:
    """Create Jinja2 environment with appropriate prompts directory.

    Args:
        site_root: Site root to check for custom prompts

    Returns:
        Configured Jinja2 Environment
    """
    prompts_dir = find_prompts_dir(site_root)
    return Environment(
        loader=FileSystemLoader(prompts_dir),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )
```

#### Step 2.2: Update PromptTemplate base class

```python
class PromptTemplate(ABC):
    """Base class for prompt templates backed by Jinja files."""

    template_name: ClassVar[str]

    def _render(
        self,
        env: Environment | None = None,
        site_root: Path | None = None,  # 🆕 Add site_root
        **context: Any
    ) -> str:
        # 🆕 Create environment with custom prompts support
        if env is None and site_root is not None:
            env = create_prompt_environment(site_root)
        template_env = env or DEFAULT_ENVIRONMENT
        template = template_env.get_template(self.template_name)
        return template.render(**context)

    @abstractmethod
    def render(self) -> str:
        """Render the template with the configured context."""
```

#### Step 2.3: Update WriterPromptTemplate

```python
@dataclass(slots=True)
class WriterPromptTemplate(PromptTemplate):
    """Prompt template for the writer agent."""

    date: str
    markdown_table: str
    active_authors: str
    custom_instructions: str = ""
    markdown_features: str = ""
    profiles_context: str = ""
    rag_context: str = ""
    freeform_memory: str = ""
    enable_memes: bool = False
    site_root: Path | None = None  # 🆕 Add site_root
    env: Environment | None = None
    template_name: ClassVar[str] = "writer.jinja"

    def render(self) -> str:
        return self._render(
            env=self.env,
            site_root=self.site_root,  # 🆕 Pass to _render
            date=self.date,
            markdown_table=self.markdown_table,
            active_authors=self.active_authors,
            custom_instructions=self.custom_instructions,
            markdown_features=self.markdown_features,
            profiles_context=self.profiles_context,
            rag_context=self.rag_context,
            freeform_memory=self.freeform_memory,
            enable_memes=self.enable_memes,
        )
```

---

### Phase 3: Site Scaffolding ⏳ PENDING

**Status**: ⏳ Not yet implemented

This phase updates site initialization to create `.egregora/` directory structure.

#### Step 3.1: Create config.yml template

**New file**: `src/egregora/rendering/templates/site/.egregora/config.yml.jinja`

```yaml
# Egregora Configuration
# This file configures Egregora's LLM-powered pipeline
# Separate from mkdocs.yml to support multiple rendering backends

# Model configuration (Google Gemini API)
# Uses pydantic-ai format: provider:model-name
models:
  writer: google-gla:gemini-2.0-flash-exp
  enricher: google-gla:gemini-flash-latest
  enricher_vision: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001
  ranking: google-gla:gemini-2.0-flash-exp
  editor: google-gla:gemini-2.0-flash-exp

# Writer agent settings
writer:
  # Custom instructions for the writer agent (optional)
  # Uncomment and customize as needed:
  # prompt: |
  #   Write analytical posts in the style of Scott Alexander / LessWrong.
  #   Focus on capturing narrative threads and preserving complexity.

  # Enable meme helper text in prompts
  enable_memes: false

# RAG (Retrieval-Augmented Generation) settings
rag:
  enabled: true
  top_k: 5                      # Number of results to retrieve
  min_similarity_threshold: 0.7           # Minimum similarity threshold (0-1)
  retrieval_mode: ann           # 'ann' (approximate) or 'exact'
  retrieval_nprobe: 10          # ANN search quality (1-100, higher = better + slower)
  embedding_dimensions: 768     # Vector dimensions (fixed for gemini-embedding-001)

# Author profile settings
profiles:
  top_authors_count: 20         # Number of top authors to profile
  include_in_context: true      # Include profiles in writer context

# Privacy settings
privacy:
  anonymize: true               # Convert names to UUIDs
  detect_pii: true              # Scan for PII (phones, emails, addresses)

# Feature flags
features:
  enrichment: true              # URL/media enrichment
  profiles: true                # Author profile generation
  ranking: false                # Elo-based post ranking
```

#### Step 3.2: Create prompts README

**New file**: `src/egregora/rendering/templates/site/.egregora/prompts/README.md.jinja`

```markdown
# Custom Prompt Overrides

This directory allows you to customize Egregora's LLM prompts without modifying package code.

## How It Works

1. Copy a template from the package: `src/egregora/prompts/`
2. Place it in this directory with the same path structure
3. Customize the template as needed
4. Egregora will use your version instead of the default

## Available Prompts

- `writer.jinja` – Main writer agent prompt
- `url_detailed.jinja` – URL enrichment prompt (used for linked articles)
- `media_detailed.jinja` – Media enrichment prompt (used for images, video, audio, docs)

## Example

To customize the writer prompt:

```bash
# Copy default template
cp /path/to/src/egregora/prompts/writer.jinja .egregora/prompts/writer.jinja

# Edit the template
vim .egregora/prompts/writer.jinja
```

Changes take effect immediately on the next run.
```

#### Step 3.3: Update scaffolding

**File**: `src/egregora/init/scaffolding.py`

```python
def _create_site_structure(site_paths: SitePaths, env: Environment, context: dict[str, Any]) -> None:
    """Create essential directories and files for the site."""
    # ... existing code for docs_dir, posts_dir, etc.

    # 🆕 Create .egregora/ directory structure
    egregora_dir = site_paths.site_root / ".egregora"
    egregora_dir.mkdir(parents=True, exist_ok=True)

    # 🆕 Render config.yml
    config_template = env.get_template(".egregora/config.yml.jinja")
    config_content = config_template.render(**context)
    (egregora_dir / "config.yml").write_text(config_content, encoding="utf-8")

    # 🆕 Create prompts/ directory with README
    prompts_dir = egregora_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    for subdir in ["system", "enrichment"]:
        (prompts_dir / subdir).mkdir(exist_ok=True)

    readme_template = env.get_template(".egregora/prompts/README.md.jinja")
    readme_content = readme_template.render(**context)
    (prompts_dir / "README.md").write_text(readme_content, encoding="utf-8")

    # ... rest of existing code
```

#### Step 3.4: Update mkdocs.yml template

**File**: `src/egregora/rendering/templates/site/mkdocs.yml.jinja`

Remove the `extra.egregora` section:

```yaml
# ... theme, plugins, markdown_extensions, nav ...

# 🆕 Add comment pointing to new location
# Egregora configuration has moved to .egregora/config.yml
# This file now contains only MkDocs-specific settings

extra:
  # Disable MkDocs generator notice
  generator: false
```

---

### Phase 4: Update Config Consumers ⏳ PENDING

**Status**: ⏳ Not yet implemented

This phase updates all code that reads configuration to use `EgregoraConfig` model.

#### Step 4.1: Update CLI commands

**File**: `src/egregora/cli.py`

Update all commands that use config:

```python
@app.command()
def process(
    export_path: Path,
    output: Path = Path("."),
    model: str | None = None,
    # ... other params
):
    """Process chat export into blog."""
    # 🆕 Load EgregoraConfig instead of dict
    site_config = load_site_config(output)  # Returns EgregoraConfig

    # 🆕 Use Pydantic attributes instead of dict access
    model_config = ModelConfig(cli_model=model, site_config=site_config)
    writer_model = model_config.get_model("writer")
    enricher_model = model_config.get_model("enricher")

    # 🆕 Access config attributes
    if site_config.features.enrichment:
        logger.info("Enrichment enabled")

    # ... rest of command
```

Similar updates for:
- `edit()` - Use `site_config.models.editor`
- `rank()` - Use `site_config.models.ranking`
- `enrich()` - Use `site_config.models.enricher`

#### Step 4.2: Update writer agent

**File**: `src/egregora/agents/writer/core.py`

```python
def generate_post_for_period(
    date: str,
    group_slug: GroupSlug,
    conversation: Table,
    config: WriterConfig,
    site_config: EgregoraConfig,  # 🆕 Changed type
    # ... other params
) -> dict[str, Any]:
    """Generate a blog post for a conversation period."""

    # 🆕 Use Pydantic attributes
    custom_writer_prompt = site_config.writer.prompt or ""
    enable_memes = site_config.writer.enable_memes

    # 🆕 Pass site_root for prompt overrides
    prompt_template = WriterPromptTemplate(
        date=date,
        markdown_table=markdown_table,
        active_authors=active_authors,
        custom_instructions=custom_writer_prompt,
        enable_memes=enable_memes,
        site_root=config.posts_dir.parent,  # Pass site root
    )

    # ... rest of function
```

#### Step 4.3: Update enrichment

**File**: `src/egregora/enrichment/core.py`

```python
def enrich_conversations(
    table: Table,
    site_config: EgregoraConfig,  # 🆕 Changed type
    # ... other params
) -> Table:
    """Enrich conversations with LLM-generated descriptions."""

    # 🆕 Use Pydantic attributes
    enricher_model = site_config.models.enricher
    enricher_vision_model = site_config.models.enricher_vision

    # ... rest of function
```

#### Step 4.4: Update pipeline runner

**File**: `src/egregora/pipeline/runner.py`

```python
def run_pipeline(config: ProcessConfig) -> None:
    """Execute the complete pipeline."""
    site_paths = resolve_site_paths(config.output_dir)

    # 🆕 Load EgregoraConfig
    if not site_paths.egregora_dir:
        msg = "No .egregora/ directory found. Run 'egregora init' first."
        raise FileNotFoundError(msg)

    site_config = load_egregora_config(site_paths.egregora_dir)

    # 🆕 Pass EgregoraConfig to pipeline stages
    model_config = ModelConfig(cli_model=config.model, site_config=site_config)

    # ... rest of pipeline
```

---

### Phase 5: Documentation ⏳ PENDING

**Status**: ⏳ Not yet implemented

This phase updates all documentation to reflect new configuration structure.

#### Step 5.1: Update CLAUDE.md

Replace mkdocs.yml config section with:

```markdown
## Configuration

### .egregora/config.yml

Generated sites store Egregora configuration in `.egregora/config.yml`:

\```yaml
models:
  writer: google-gla:gemini-2.0-flash-exp
  enricher: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001

rag:
  enabled: true
  top_k: 5
  min_similarity_threshold: 0.7
  retrieval_mode: ann
  retrieval_nprobe: 10

writer:
  prompt: |
    Custom instructions for the writer agent...
  enable_memes: false
\```

### Custom Prompts

Override prompts by placing templates in `.egregora/prompts/`:

\```bash
.egregora/
├── config.yml
└── prompts/
    └── system/
        └── writer.jinja  # Overrides package default
\```

See `.egregora/prompts/README.md` for available templates.
```

#### Step 5.2: Update configuration docs

**File**: `docs/getting-started/configuration.md`

Add new section:

```markdown
## Egregora Configuration File

Egregora stores its configuration in `.egregora/config.yml`, separate from MkDocs settings.

### Location

```bash
my-blog/
├── mkdocs.yml          # MkDocs rendering settings
└── .egregora/
    └── config.yml      # Egregora pipeline settings
```

### Full Configuration

\```yaml
# Model configuration
models:
  writer: google-gla:gemini-2.0-flash-exp
  enricher: google-gla:gemini-flash-latest
  enricher_vision: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001
  ranking: google-gla:gemini-2.0-flash-exp
  editor: google-gla:gemini-2.0-flash-exp

# Writer settings
writer:
  prompt: |
    Custom instructions for blog post generation...
  enable_memes: false

# RAG settings
rag:
  enabled: true
  top_k: 5
  min_similarity_threshold: 0.7
  retrieval_mode: ann
  retrieval_nprobe: 10
  embedding_dimensions: 768

# Profile settings
profiles:
  top_authors_count: 20
  include_in_context: true

# Privacy settings
privacy:
  anonymize: true
  detect_pii: true

# Feature flags
features:
  enrichment: true
  profiles: true
  ranking: false
\```

### Customizing Prompts

You can override any prompt template without modifying package code:

1. Copy the template from `src/egregora/prompts/`
2. Place it in `.egregora/prompts/` with the same path structure
3. Customize as needed

Example:

\```bash
# Copy writer prompt
cp src/egregora/prompts/writer.jinja .egregora/prompts/writer.jinja

# Edit
vim .egregora/prompts/writer.jinja
\```

Changes take effect immediately on the next run.
```

#### Step 5.3: Update README.md

Update quick start section:

```markdown
## Quick Start

1. Install Egregora:
   ```bash
   pip install egregora
   ```

2. Process a WhatsApp export:
   ```bash
   egregora process chat.zip --output=./my-blog
   ```

3. Configure your site:
   ```bash
   cd my-blog
   vim .egregora/config.yml  # Edit models, prompts, features
   ```

4. Serve the blog:
   ```bash
   mkdocs serve
   ```
```

---

### Phase 6: Testing ✅ COMPLETE

**Status**: ✅ Complete (2025-01-08)

This phase adds comprehensive tests for config loading and prompt overrides.

#### Step 6.1: Unit tests - Config loading

**New file**: `tests/unit/test_egregora_config.py`

```python
import pytest
from pathlib import Path
from pydantic import ValidationError

from egregora.config.settings import EgregoraConfig, RAGSettings, load_egregora_config

def test_egregora_config_defaults():
    """Test EgregoraConfig has sensible defaults."""
    config = EgregoraConfig()
    assert config.models.writer == "google-gla:gemini-2.0-flash-exp"
    assert config.rag.enabled is True
    assert config.rag.top_k == 5
    assert config.privacy.anonymize is True

def test_egregora_config_validation():
    """Test Pydantic validation catches invalid values."""
    # Invalid retrieval_mode
    with pytest.raises(ValidationError):
        EgregoraConfig(rag={"retrieval_mode": "invalid"})

    # Invalid top_k (out of range)
    with pytest.raises(ValidationError):
        EgregoraConfig(rag={"top_k": -1})

    # Invalid min_similarity_threshold (out of range)
    with pytest.raises(ValidationError):
        EgregoraConfig(rag={"min_similarity_threshold": 1.5})

def test_find_egregora_dir_upward_search(tmp_path):
    """Test upward search for .egregora directory."""
    # Create directory structure
    site_root = tmp_path / "site"
    egregora_dir = site_root / ".egregora"
    nested = site_root / "docs" / "posts" / "deep"

    egregora_dir.mkdir(parents=True)
    nested.mkdir(parents=True)

    # Should find .egregora from nested directory
    found = find_egregora_dir(nested)
    assert found == egregora_dir

def test_find_egregora_dir_not_found(tmp_path):
    """Test find_egregora_dir returns None when not found."""
    assert find_egregora_dir(tmp_path) is None

def test_load_egregora_config(tmp_path):
    """Test loading and parsing config.yml."""
    egregora_dir = tmp_path / ".egregora"
    egregora_dir.mkdir()

    config_content = """
models:
  writer: google-gla:gemini-2.0-flash-exp
rag:
  enabled: true
  top_k: 10
"""
    (egregora_dir / "config.yml").write_text(config_content)

    config = load_egregora_config(egregora_dir)
    assert config.models.writer == "google-gla:gemini-2.0-flash-exp"
    assert config.rag.top_k == 10

def test_load_egregora_config_env_substitution(tmp_path, monkeypatch):
    """Test !ENV tag support in config.yml."""
    egregora_dir = tmp_path / ".egregora"
    egregora_dir.mkdir()

    monkeypatch.setenv("TEST_MODEL", "google-gla:custom-model")

    config_content = """
models:
  writer: !ENV [TEST_MODEL, "google-gla:fallback"]
"""
    (egregora_dir / "config.yml").write_text(config_content)

    config = load_egregora_config(egregora_dir)
    assert config.models.writer == "google-gla:custom-model"
```

#### Step 6.2: Unit tests - Prompt overrides

**New file**: `tests/unit/test_prompt_overrides.py`

```python
from pathlib import Path
from egregora.prompt_templates import find_prompts_dir, create_prompt_environment

def test_find_prompts_dir_custom(tmp_path):
    """Test finding custom prompts directory."""
    custom_prompts = tmp_path / ".egregora" / "prompts"
    custom_prompts.mkdir(parents=True)

    found = find_prompts_dir(tmp_path)
    assert found == custom_prompts

def test_find_prompts_dir_fallback():
    """Test fallback to package prompts when custom not found."""
    from egregora import prompts
    package_prompts = Path(prompts.__file__).parent

    found = find_prompts_dir(Path("/nonexistent"))
    assert found == package_prompts

def test_custom_prompt_override(tmp_path):
    """Test that custom prompts override package prompts."""
    # Create custom prompt
    custom_prompts = tmp_path / ".egregora" / "prompts" / "system"
    custom_prompts.mkdir(parents=True)
    (custom_prompts / "writer.jinja").write_text("Custom prompt: {{ date }}")

    # Create environment with custom prompts
    env = create_prompt_environment(tmp_path)
    template = env.get_template("writer.jinja")

    # Should render custom template
    result = template.render(date="2025-01-01")
    assert result == "Custom prompt: 2025-01-01"
```

#### Step 6.3: Integration tests

**File**: `tests/e2e/test_init_template_structure.py`

```python
def test_egregora_directory_created(tmp_path):
    """Test that .egregora/ directory is created on init."""
    from egregora.init.scaffolding import ensure_mkdocs_project

    docs_dir, created = ensure_mkdocs_project(tmp_path)

    assert created
    assert (tmp_path / ".egregora").exists()
    assert (tmp_path / ".egregora" / "config.yml").exists()
    assert (tmp_path / ".egregora" / "prompts").exists()

def test_config_yml_structure(tmp_path):
    """Test that generated config.yml has correct structure."""
    from egregora.init.scaffolding import ensure_mkdocs_project
    from egregora.config.settings import load_egregora_config

    ensure_mkdocs_project(tmp_path)

    egregora_dir = tmp_path / ".egregora"
    config = load_egregora_config(egregora_dir)

    # Verify structure
    assert config.models.writer
    assert config.rag.enabled is True
    assert config.privacy.anonymize is True

def test_mkdocs_yml_no_extra_egregora(tmp_path):
    """Test that mkdocs.yml doesn't have extra.egregora."""
    from egregora.init.scaffolding import ensure_mkdocs_project
    import yaml

    ensure_mkdocs_project(tmp_path)

    mkdocs_content = (tmp_path / "mkdocs.yml").read_text()
    mkdocs_dict = yaml.safe_load(mkdocs_content)

    # Should NOT have extra.egregora
    assert "egregora" not in mkdocs_dict.get("extra", {})
```

#### Step 6.4: E2E tests

**File**: `tests/e2e/test_custom_prompts.py`

```python
def test_pipeline_with_custom_prompt(tmp_path, sample_whatsapp_export):
    """Test full pipeline with custom writer prompt."""
    # Initialize site
    from egregora.init.scaffolding import ensure_mkdocs_project
    ensure_mkdocs_project(tmp_path)

    # Create custom writer prompt
    custom_prompts = tmp_path / ".egregora" / "prompts" / "system"
    custom_prompts.mkdir(parents=True, exist_ok=True)
    (custom_prompts / "writer.jinja").write_text(
        "Test custom prompt: {{ markdown_table }}"
    )

    # Run pipeline
    from egregora.cli import process
    # ... run process command

    # Verify custom prompt was used
    # (check logs or output for evidence of custom prompt)
```

---

## Migration Strategy

### For Existing Sites (Manual Migration)

Since this is a **prototyping phase** with **no backward compatibility**, existing sites must be manually migrated:

```bash
# 1. Create .egregora/ directory
mkdir .egregora

# 2. Copy config from mkdocs.yml manually
# Extract extra.egregora section → .egregora/config.yml

# 3. Update mkdocs.yml
# Remove extra.egregora section

# 4. Test
egregora process chat.zip --output=.
```

### For New Sites

New sites automatically get `.egregora/` structure:

```bash
egregora process chat.zip --output=./my-blog
cd my-blog
ls -la .egregora/  # config.yml, prompts/, agents/, etc.
```

---

## Environment Variable Support

### `!ENV` Tag in config.yml

**Supported syntax**:

```yaml
# With fallback
models:
  writer: !ENV [EGREGORA_WRITER_MODEL, "google-gla:gemini-2.0-flash-exp"]

# Without fallback (empty string if not set)
models:
  writer: !ENV EGREGORA_WRITER_MODEL
```

**Implementation**: Reuse existing `_ConfigLoader` from `config/site.py`

---

## Files to Create/Modify

### New Files (5)

1. `src/egregora/config/schema.py` - Pydantic config schema
2. `src/egregora/rendering/templates/site/.egregora/config.yml.jinja` - Config template
3. `src/egregora/rendering/templates/site/.egregora/prompts/README.md.jinja` - Prompts README
4. `tests/unit/test_egregora_config.py` - Config tests
5. `tests/unit/test_prompt_overrides.py` - Prompt override tests

### Modified Files (11)

6. `src/egregora/config/site.py` - Add `.egregora/` finder/loader
7. `src/egregora/config/model.py` - Use `EgregoraConfig` model
8. `src/egregora/config/types.py` - Update type hints
9. `src/egregora/prompt_templates.py` - Add prompt override support
10. `src/egregora/init/scaffolding.py` - Create `.egregora/config.yml`
11. `src/egregora/cli.py` - Use `EgregoraConfig` types
12. `src/egregora/agents/writer/core.py` - Use config attributes
13. `src/egregora/enrichment/core.py` - Use config attributes
14. `src/egregora/pipeline/runner.py` - Load and pass config
15. `src/egregora/rendering/templates/site/mkdocs.yml.jinja` - Remove `extra.egregora`
16. `tests/e2e/test_init_template_structure.py` - Test `.egregora/` creation

### Documentation (3)

17. `CLAUDE.md` - Update config examples
18. `docs/getting-started/configuration.md` - Add `.egregora/` section
19. `README.md` - Update quick start

**Total**: 19 files (5 new, 11 modified, 3 docs)

---

## Benefits Summary

### 1. Backend Independence
- Egregora config separate from MkDocs
- Easy to support Hugo, Astro, Docusaurus, etc.
- Pipeline can run without any static site generator

### 2. User Customization
- Override prompts without forking repo
- Changes persist across updates
- Version control friendly

### 3. Type Safety
- Pydantic validation catches errors early
- IDE autocomplete for config
- Self-documenting with field constraints

### 4. Cleaner Architecture
- Clear separation: `.egregora/` (pipeline) vs `mkdocs.yml` (rendering)
- Single source of truth for Egregora settings
- Extensible structure for future features

### 5. Developer Experience
- Config schema in code (not scattered across docs)
- Easier to test and validate
- Better error messages from Pydantic

---

## Design Decisions

### 1. Hidden Directory (`.egregora/`)
**Rationale**: Configuration/infrastructure, not user content. Similar to `.git/`, `.github/`, etc.

### 2. Pydantic Validation
**Rationale**: Type safety, validation, IDE support, better error messages.

### 3. Prompt Overrides
**Rationale**: Power users need customization without forking. Falls back to package defaults gracefully.

### 4. No Backward Compatibility
**Rationale**: Prototyping phase, clean slate preferred over legacy support burden.

### 5. Separation of Concerns
**Rationale**: Different tools for different purposes. MkDocs for rendering, Egregora for pipeline.

---

## Open Questions

1. **Config versioning**: Should `config.yml` have a `version` field for future migrations?
2. **Config validation on load**: Should we validate config immediately or lazily?
3. **Prompt discovery**: Should we list available custom prompts in CLI?
4. **Multiple config files**: Should different stages have separate config files?
5. **Config inheritance**: Should we support multiple `.egregora/` directories (parent/child)?

---

## Progress Summary

### Completed ✅

| Phase | Status | Implemented In | Key Deliverables |
|-------|--------|----------------|------------------|
| **Phase 1: Config Infrastructure** | ✅ Complete | PR #623 | Pydantic V2 schema, config loader, facade pattern, windowing |
| **Phase 2: Custom Prompt Overrides** | ✅ Complete | Current branch | `find_prompts_dir()`, `create_prompt_environment()`, site_root param in all templates |
| **Phase 3: Site Scaffolding** | ✅ Complete | Current branch | `config.yml.jinja`, `prompts/README.md.jinja`, updated `scaffolding.py`, removed `extra.egregora` from mkdocs |
| **Phase 4: Update Config Consumers** | ✅ Complete | Current branch | site_root in all agent deps (WriterAgentContext, EditorAgentState, enrichment contexts), renderer-agnostic design |
| **Phase 5: Documentation** | ✅ Complete | Current branch | Updated CLAUDE.md, configuration.md with .egregora/ structure, custom prompts, EgregoraConfig references |
| **Phase 6: Testing** | ✅ Complete | Current branch | 32 comprehensive tests: config loading (16), prompt overrides (11), scaffolding (5) |

### In Progress / Pending ⏳

No phases remaining - migration complete!

### Key Changes from Original Plan

PR #623 introduced several improvements:

1. **Pydantic V2** instead of V1 (`ConfigDict`, `extra="forbid"`)
2. **Windowing** replaces period-based grouping (`step_size`, `step_unit`, `overlap_ratio`)
3. **Token limits** added (`max_prompt_tokens`, `use_full_context_window`)
4. **Field renames**:
   - `writer.prompt` → `writer.custom_instructions`
   - `writer.enable_memes` → `writer.enable_banners`
   - `rag.retrieval_mode` → `rag.mode`
   - `rag.retrieval_nprobe` → `rag.nprobe`
5. **No backward compatibility** (clean break, alpha phase)

---

## Next Steps

### Immediate (Phase 2-3)

1. **Implement prompt overrides** (Phase 2)
   - Update `prompt_templates.py` to search `.egregora/prompts/`
   - Add fallback to package prompts
   - Test custom prompt loading

2. **Update scaffolding** (Phase 3)
   - Create `config.yml.jinja` template
   - Update `init/scaffolding.py` to create `.egregora/`
   - Remove `extra.egregora` from mkdocs.yml template

### Medium-term (Phase 4-6)

3. **Update config consumers** (Phase 4)
   - CLI commands use `EgregoraConfig`
   - Writer/enrichment/pipeline use Pydantic models
   - Remove dict-based config access

4. **Documentation updates** (Phase 5)
   - CLAUDE.md with `.egregora/` examples
   - Configuration guide
   - Migration instructions

5. **Testing** (Phase 6)
   - Config loading tests
   - Prompt override tests
   - E2E integration tests

---

**Status**: Phases 1-5 complete, Phase 6 (testing) awaiting implementation
