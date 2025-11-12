"""Centralized configuration module using the facade pattern.

This module serves as the single entry point for all configuration-related imports in Egregora.
Instead of navigating deep module paths, consumers can import everything configuration-related
from this facade:

    from egregora.config import EgregoraConfig, WriterAgentContext, SitePaths

**Facade Pattern Benefits:**

- **Simplified imports**: `from egregora.config import X` instead of `from egregora.config.settings import X`
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
- `WriterConfig`, `EnrichmentSettings`: Runtime context dataclasses
- `ModelConfig`: LLM model configuration (backend-agnostic)

**Architecture:**

```
config/
├── __init__.py          # This facade (re-exports everything)
├── schema.py            # CONSOLIDATED: All config code (Pydantic models, dataclasses, loading)
├── validation.py        # CLI-specific validation utilities
└── site.py              # MkDocs site paths (DEPRECATED, should move to output_adapters/)
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
# All Configuration (from .schema)
# ==============================================================================
# CONSOLIDATED: Everything is now in schema.py - Pydantic models, dataclasses,
# loading functions, and model utilities all in one place.
from egregora.config.settings import (
    DEFAULT_BANNER_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    # Constants
    DEFAULT_MODEL,
    EMBEDDING_DIM,
    # Pydantic V2 config models (persisted in .egregora/config.yml)
    EgregoraConfig,
    EnrichmentRuntimeConfig,
    EnrichmentSettings,
    FeaturesSettings,
    MediaEnrichmentContext,
    ModelSettings,
    # Model configuration utilities
    ModelType,
    PipelineEnrichmentConfig,
    PrivacySettings,
    # Runtime dataclasses (for function parameters, not persisted)
    ProcessConfig,
    RAGSettings,
    WriterAgentSettings,
    WriterRuntimeConfig,
    # Config loading/saving functions
    create_default_config,
    find_egregora_config,
    get_model_for_task,
    load_egregora_config,
    save_egregora_config,
)

# ==============================================================================
# Site Paths & MkDocs Utilities (from output_adapters.mkdocs_site)
# ==============================================================================
# DEPRECATED: MkDocs-specific utilities moved to output_adapters.mkdocs_site module.
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
# New code should import from egregora.output_adapters.mkdocs_site directly.
from egregora.output_adapters.mkdocs_site import (
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
    # ==========================================================================
    # Core Pydantic V2 Config Models (PRIMARY - Phase 2 modernization)
    # ==========================================================================
    # Root config and sub-configs loaded from .egregora/config.yml
    "EgregoraConfig",  # Root config (contains all sub-configs)
    "EnrichmentSettings",  # Enrichment stage parameters
    "FeaturesSettings",  # Feature flags
    "MediaEnrichmentContext",  # Media enrichment runtime context
    # ==========================================================================
    # Model Configuration Utilities
    # ==========================================================================
    "ModelType",  # Type literal for model roles
    "ModelSettings",  # LLM model names
    "get_model_for_task",  # Get model name with CLI override support
    # ==========================================================================
    # Pipeline-Specific Configs
    # ==========================================================================
    "PipelineEnrichmentConfig",  # Enrichment batch processing config
    "PrivacySettings",  # Anonymization settings
    # ==========================================================================
    # Runtime Context Dataclasses (TRANSITIONAL - Phase 2 migration in progress)
    # ==========================================================================
    # These replace parameter soup (12-16 params → 3-6 params) in function signatures.
    # Will eventually use EgregoraConfig internally.
    "ProcessConfig",  # CLI process command parameters
    "RAGSettings",  # Retrieval settings
    # ==========================================================================
    # Site Paths & MkDocs Utilities
    # ==========================================================================
    "SitePaths",  # Dataclass with all site paths
    "WriterAgentSettings",  # Writer agent settings (Pydantic model)
    "WriterConfig",  # Writer agent runtime context (dataclass from writer_runner)
    "create_default_config",  # Create default config
    "find_egregora_config",  # Find config file in directory tree
    "find_mkdocs_file",  # Locate mkdocs.yml
    # ==========================================================================
    # Config Loading & Persistence
    # ==========================================================================
    "load_egregora_config",  # Load config from .egregora/config.yml
    "load_mkdocs_config",  # Load and parse mkdocs.yml
    "resolve_site_paths",  # Resolve paths from site_dir or mkdocs.yml
    "save_egregora_config",  # Save config to disk
]
