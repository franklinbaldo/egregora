"""Centralized configuration module using the facade pattern.

This module serves as the single entry point for all configuration-related imports in Egregora.
Instead of navigating deep module paths, consumers can import everything configuration-related
from this facade:

    from egregora.config import EgregoraConfig, WriterAgentSettings

**Facade Pattern Benefits:**

- **Simplified imports**: `from egregora.config import X` instead of `from egregora.config.settings import X`
- **Stable API**: Internal module restructuring doesn't break consumer code
- **Discoverability**: All config exports visible in one place via `__all__`
- **IDE support**: Better autocomplete and type hints

**Phase 2 Modernization: Configuration Objects Pattern**

This module is part of the Phase 2 refactoring to replace parameter soup (12-16 params) with
configuration objects (3-6 params). The pattern includes:

- **Pydantic V2 models** (.schema): Validated, typed config loaded from `.egregora/config.yml`
- **Runtime contexts** (.settings): Dataclasses and helpers for runtime parameters
- **Model utilities** (.model): LLM model configuration and defaults
- **Site paths** (.site): MkDocs site structure and path resolution

**Primary Exports:**

- `EgregoraConfig`: Root Pydantic V2 config model (loads from `.egregora/config.yml`)
- `load_egregora_config()`: Config loader with validation
- `EnrichmentSettings`: Enrichment configuration
- `ModelConfig`: LLM model configuration (backend-agnostic)

**Architecture:**

```
config/
├── __init__.py          # This facade (re-exports everything)
├── schema.py            # CONSOLIDATED: All config code (Pydantic models, dataclasses, loading)
└── config_validation.py # CLI-specific validation utilities
```

**Migration Status:**

- ✅ New system: Pydantic V2 configs in `.egregora/config.yml` (PRIMARY)
- 🔄 Transitional: Runtime context dataclasses for function signatures
- ⚠️ Legacy: Older contexts will be migrated to use EgregoraConfig internally

See Also:
    - `egregora.config.schema`: Pydantic V2 models and validation
    - `egregora.config.settings`: Runtime context dataclasses and helpers
    - CLAUDE.md: Configuration section for environment variables and MkDocs config

"""

# ==============================================================================
# All Configuration (from .schema)
# ==============================================================================
# CONSOLIDATED: Everything is now in schema.py - Pydantic models, dataclasses,
# loading functions, and model utilities all in one place.
from egregora.config.settings import (
    EMBEDDING_DIM,
    # Pydantic V2 config models (persisted in .egregora/config.yml)
    EgregoraConfig,
    EnrichmentSettings,
    FeaturesSettings,
    MediaEnrichmentContext,
    ModelSettings,
    # Model configuration utilities
    ModelType,
    PipelineEnrichmentConfig,
    PipelineSettings,
    PrivacySettings,
    # Runtime dataclasses (for function parameters, not persisted)
    RAGSettings,
    RuntimeContext,  # Minimal runtime-only context
    WriterAgentSettings,
    # Config loading/saving functions
    create_default_config,
    find_egregora_config,
    get_google_api_key,
    google_api_key_status,
    load_egregora_config,
    save_egregora_config,
)

__all__ = [
    "EMBEDDING_DIM",
    "EgregoraConfig",
    "EnrichmentSettings",
    "FeaturesSettings",
    "MediaEnrichmentContext",
    "ModelSettings",
    "ModelType",
    "PipelineEnrichmentConfig",
    "PipelineSettings",
    "PrivacySettings",
    "RAGSettings",
    "RuntimeContext",
    "WriterAgentSettings",
    "create_default_config",
    "find_egregora_config",
    "get_google_api_key",
    "google_api_key_status",
    "load_egregora_config",
    "save_egregora_config",
]
