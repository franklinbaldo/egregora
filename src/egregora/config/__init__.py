"""Centralized configuration module using the facade pattern.

This module serves as the single entry point for all configuration-related imports in Egregora.
Instead of navigating deep module paths, consumers can import everything configuration-related
from this facade:

    from egregora.config import EgregoraConfig, WriterRuntimeContext, SitePaths

**Facade Pattern Benefits:**

- **Simplified imports**: `from egregora.config import X` instead of `from egregora.config.schema import X`
- **Stable API**: Internal module restructuring doesn't break consumer code
- **Discoverability**: All config exports visible in one place via `__all__`
- **IDE support**: Better autocomplete and type hints

**Phase 2 Modernization: Configuration Objects Pattern**

This module is part of the Phase 2 refactoring to replace parameter soup (12-16 params) with
configuration objects (3-6 params). The pattern includes:

- **Pydantic V2 models** (.schema): Validated, typed config loaded from `.egregora/config.yml`
- **Runtime contexts** (.types): Dataclasses for function parameters (ProcessConfig, WriterConfig)
- **Model utilities** (.model): LLM model configuration and defaults
- **Site paths** (.site): MkDocs site structure and path resolution

**Primary Exports:**

- `EgregoraConfig`: Root Pydantic V2 config model (loads from `.egregora/config.yml`)
- `load_egregora_config()`: Config loader with validation
- `SitePaths`: Site structure paths (blog, profiles, media, .egregora/)
- `WriterConfig`, `EnrichmentConfig`: Runtime context dataclasses
- `ModelConfig`: LLM model configuration (backend-agnostic)

**Architecture:**

```
config/
├── __init__.py          # This facade (re-exports everything)
├── schema.py            # Pydantic V2 models (EgregoraConfig, ModelsConfig, RAGConfig)
├── types.py             # Runtime contexts (ProcessConfig, WriterConfig, EditorContext)
├── pipeline.py          # Pipeline-specific configs (PipelineEnrichmentConfig)
├── site.py              # Site paths and MkDocs utilities (SitePaths, resolve_site_paths)
├── model.py             # Model configuration (ModelConfig, get_model_config)
└── loader.py            # Config loading/saving (load_egregora_config, create_default_config)
```

**Migration Status:**

- ✅ New system: Pydantic V2 configs in `.egregora/config.yml` (PRIMARY)
- 🔄 Transitional: Runtime context dataclasses for function signatures
- ⚠️ Legacy: Old ProcessConfig/WriterConfig will be migrated to use EgregoraConfig internally

See Also:
    - `egregora.config.schema`: Pydantic V2 models and validation
    - `egregora.config.types`: Runtime context dataclasses
    - CLAUDE.md: Configuration section for environment variables and MkDocs config

"""

# ==============================================================================
# Config Loading & Persistence (.egregora/config.yml)
# ==============================================================================
# Functions for loading, creating, and saving the root EgregoraConfig from disk.
# This is the PRIMARY way to configure Egregora (replaces env vars + CLI flags).
from egregora.config.loader import (
    create_default_config,
    find_egregora_config,
    load_egregora_config,
    save_egregora_config,
)

# ==============================================================================
# Model Configuration Utilities (from .model)
# ==============================================================================
# Backend-agnostic model configuration (supports pydantic-ai, google-genai, openai).
# Provides model defaults, type enums, and conversion utilities.
#
# - ModelConfig: Dataclass with model_name, backend, temperature
# - ModelType: Enum of model roles (WRITER, ENRICHER, EMBEDDING, RANKING, EDITOR)
# - get_model_config(): Get config from EgregoraConfig or environment
# - ModelType: Type literal for model names
# - EMBEDDING_DIM: Embedding vector dimensions (768 for text-embedding-004)
# Note: Model defaults are centralized in schema.py ModelsConfig (no fallback constants)
from egregora.config.model import (
    EMBEDDING_DIM,
    ModelConfig,
    ModelType,
    get_model_config,
)

# ==============================================================================
# Pipeline-Specific Configs (from .pipeline)
# ==============================================================================
# Configuration classes specific to pipeline stages (e.g., enrichment batch processing).
from egregora.config.pipeline import PipelineEnrichmentConfig

# ==============================================================================
# Core Pydantic V2 Models (from .schema)
# ==============================================================================
# Validated, strongly-typed configuration models loaded from .egregora/config.yml.
# These are the PRIMARY config objects in the Phase 2 modernization.
#
# - EgregoraConfig: Root config (contains models, RAG, writer, privacy, pipeline, features)
# - ModelsConfig: LLM model names (writer, enricher, embedding, ranking, editor)
# - RAGConfig: Retrieval settings (mode, nprobe, embedding_dimensions)
# - EgregoraWriterConfig: Writer agent settings (max_posts_per_period, post_length_words)
# - PrivacyConfig: Anonymization settings (anonymize_authors)
# - EgregoraEnrichmentConfig: Enrichment settings (enrich_urls, enrich_media, use_batch_api)
# - EgregoraPipelineConfig: Pipeline settings (period)
# - FeaturesConfig: Feature flags (not yet implemented)
#
# Note: Aliased as Egregora* to avoid name collisions with legacy dataclasses.
from egregora.config.schema import (
    EgregoraConfig,
    FeaturesConfig,
    ModelsConfig,
    PrivacyConfig,
    RAGConfig,
)

# ==============================================================================
# Runtime Context Dataclasses (from .types)
# ==============================================================================
# Dataclasses for function parameters in the Phase 2 Configuration Objects pattern.
# These replace parameter soup (12-16 params → 3-6 params) in function signatures.
#
# TRANSITIONAL: These will eventually be migrated to use EgregoraConfig internally,
# but currently exist as standalone dataclasses for gradual migration.
#
# - ProcessConfig: CLI process command parameters
# - WriterConfig: Writer agent runtime context
# - EnrichmentConfig: Enrichment stage parameters
# - RankingCliConfig: Ranking CLI parameters
# - ComparisonConfig: Elo ranking comparison parameters
# - ComparisonData: Comparison result data
# - MediaEnrichmentContext: Media enrichment runtime context
from egregora.config.types import (
    ComparisonConfig,
    ComparisonData,
    EnrichmentConfig,
    MediaEnrichmentContext,
    ProcessConfig,
    RankingCliConfig,
    WriterConfig,
)

# ==============================================================================
# Site Paths & MkDocs Utilities (from rendering.mkdocs_site)
# ==============================================================================
# DEPRECATED: MkDocs-specific utilities moved to rendering.mkdocs_site module.
# Re-exported here for backward compatibility only.
#
# Path resolution for MkDocs site structure (blog/, profiles/, media/, .egregora/).
# Handles both legacy flat structure and new .egregora/ structure.
#
# - SitePaths: Dataclass with all site paths (site_dir, blog_dir, profiles_dir, etc.)
# - resolve_site_paths(): Resolve paths from site_dir or mkdocs.yml
# - find_mkdocs_file(): Locate mkdocs.yml in directory tree
# - load_mkdocs_config(): Load and parse mkdocs.yml
# - DEFAULT_BLOG_DIR, DEFAULT_DOCS_DIR: Default directory names
# - MEDIA_DIR_NAME, PROFILES_DIR_NAME: Subdirectory names
#
# New code should import from egregora.rendering.mkdocs_site directly.
from egregora.rendering.mkdocs_site import (
    DEFAULT_BLOG_DIR,
    DEFAULT_DOCS_DIR,
    MEDIA_DIR_NAME,
    PROFILES_DIR_NAME,
    SitePaths,
    find_mkdocs_file,
    load_mkdocs_config,
    resolve_site_paths,
)

__all__ = [
    "DEFAULT_BLOG_DIR",  # Default blog directory name
    "DEFAULT_DOCS_DIR",  # Default docs directory name
    "EMBEDDING_DIM",  # Embedding vector dimensions
    "MEDIA_DIR_NAME",  # Media subdirectory name
    "PROFILES_DIR_NAME",  # Profiles subdirectory name
    "ComparisonConfig",  # Elo ranking comparison parameters
    "ComparisonData",  # Comparison result data
    # ==========================================================================
    # Core Pydantic V2 Config Models (PRIMARY - Phase 2 modernization)
    # ==========================================================================
    # Root config and sub-configs loaded from .egregora/config.yml
    "EgregoraConfig",  # Root config (contains all sub-configs)
    "EnrichmentConfig",  # Enrichment stage parameters
    "FeaturesConfig",  # Feature flags
    "MediaEnrichmentContext",  # Media enrichment runtime context
    # ==========================================================================
    # Model Configuration Utilities
    # ==========================================================================
    "ModelConfig",  # Backend-agnostic model config
    "ModelType",  # Type literal for model roles
    "ModelType",  # Enum of model roles
    "ModelsConfig",  # LLM model names
    # ==========================================================================
    # Pipeline-Specific Configs
    # ==========================================================================
    "PipelineEnrichmentConfig",  # Enrichment batch processing config
    "PrivacyConfig",  # Anonymization settings
    # ==========================================================================
    # Runtime Context Dataclasses (TRANSITIONAL - Phase 2 migration in progress)
    # ==========================================================================
    # These replace parameter soup (12-16 params → 3-6 params) in function signatures.
    # Will eventually use EgregoraConfig internally.
    "ProcessConfig",  # CLI process command parameters
    "RAGConfig",  # Retrieval settings
    "RankingCliConfig",  # Ranking CLI parameters
    # ==========================================================================
    # Site Paths & MkDocs Utilities
    # ==========================================================================
    "SitePaths",  # Dataclass with all site paths
    "WriterConfig",  # Writer agent runtime context
    "create_default_config",  # Create default config
    "find_egregora_config",  # Find config file in directory tree
    "find_mkdocs_file",  # Locate mkdocs.yml
    "get_model_config",  # Get config from EgregoraConfig or env
    # ==========================================================================
    # Config Loading & Persistence
    # ==========================================================================
    "load_egregora_config",  # Load config from .egregora/config.yml
    "load_mkdocs_config",  # Load and parse mkdocs.yml
    "resolve_site_paths",  # Resolve paths from site_dir or mkdocs.yml
    "save_egregora_config",  # Save config to disk
]
