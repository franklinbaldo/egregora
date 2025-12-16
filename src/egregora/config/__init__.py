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

**Architecture:**

```
config/
├── __init__.py          # This facade (re-exports everything)
├── settings.py          # CONSOLIDATED: All config code (Pydantic models, dataclasses, loading)
```

"""

# ==============================================================================
# All Configuration
# ==============================================================================
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
    # Runtime dataclasses (for function parameters, not persisted)
    RAGSettings,
    RuntimeContext,  # Minimal runtime-only context
    WriterAgentSettings,
    # Config loading/saving functions
    create_default_config,
    find_egregora_config,
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
    "RAGSettings",
    "RuntimeContext",
    "WriterAgentSettings",
    "create_default_config",
    "find_egregora_config",
    "load_egregora_config",
    "save_egregora_config",
]
