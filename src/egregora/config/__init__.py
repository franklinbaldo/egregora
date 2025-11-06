"""Configuration management for Egregora.

SIMPLIFIED (Alpha): New config system based on .egregora/config.yml.

Main exports:
- EgregoraConfig: Root Pydantic config model
- load_egregora_config(): Load from .egregora/config.yml
- SitePaths: All paths (including .egregora/ structure)

Legacy exports (will be migrated):
- ModelConfig: Still used but will use EgregoraConfig internally
- ProcessConfig, WriterConfig, etc.: Dataclasses for function parameters
"""

# New config system (Pydantic + .egregora/)
from egregora.config.loader import (
    create_default_config,
    find_egregora_config,
    load_egregora_config,
    save_egregora_config,
)
from egregora.config.schema import (
    EgregoraConfig,
    EnrichmentConfig as EgregoraEnrichmentConfig,
    FeaturesConfig,
    ModelsConfig,
    PipelineConfig as EgregoraPipelineConfig,
    PrivacyConfig,
    RAGConfig,
    WriterConfig as EgregoraWriterConfig,
)

# Model configuration (will be updated to use EgregoraConfig)
from egregora.config.model import (
    DEFAULT_EDITOR_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_ENRICHER_MODEL,
    DEFAULT_ENRICHER_VISION_MODEL,
    DEFAULT_RANKING_MODEL,
    DEFAULT_WRITER_MODEL,
    EMBEDDING_DIM,
    ModelConfig,
    ModelType,
    from_pydantic_ai_model,
    load_site_config,
)

# Pipeline config
from egregora.config.pipeline import PipelineEnrichmentConfig

# Site paths and MkDocs utilities
from egregora.config.site import (
    DEFAULT_BLOG_DIR,
    DEFAULT_DOCS_DIR,
    MEDIA_DIR_NAME,
    PROFILES_DIR_NAME,
    SitePaths,
    find_mkdocs_file,
    load_mkdocs_config,
    resolve_site_paths,
)

# Dataclass configs for function parameters (transitional)
from egregora.config.types import (
    ComparisonConfig,
    ComparisonData,
    EditorContext,
    EnrichmentConfig,
    MediaEnrichmentContext,
    PostGenerationContext,
    ProcessConfig,
    RankingCliConfig,
    URLEnrichmentContext,
    WriterConfig,
    WriterPromptContext,
)

__all__ = [
    # New config system (PRIMARY - use these!)
    "EgregoraConfig",
    "ModelsConfig",
    "RAGConfig",
    "EgregoraWriterConfig",
    "PrivacyConfig",
    "EgregoraEnrichmentConfig",
    "EgregoraPipelineConfig",
    "FeaturesConfig",
    "load_egregora_config",
    "create_default_config",
    "find_egregora_config",
    "save_egregora_config",
    # Model utilities
    "ModelConfig",
    "ModelType",
    "from_pydantic_ai_model",
    "EMBEDDING_DIM",
    "DEFAULT_WRITER_MODEL",
    "DEFAULT_ENRICHER_MODEL",
    "DEFAULT_ENRICHER_VISION_MODEL",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_RANKING_MODEL",
    "DEFAULT_EDITOR_MODEL",
    # Site paths
    "SitePaths",
    "resolve_site_paths",
    "find_mkdocs_file",
    "load_mkdocs_config",
    "DEFAULT_BLOG_DIR",
    "DEFAULT_DOCS_DIR",
    "MEDIA_DIR_NAME",
    "PROFILES_DIR_NAME",
    # Pipeline
    "PipelineEnrichmentConfig",
    # Dataclass configs (transitional - will be replaced)
    "ProcessConfig",
    "WriterConfig",
    "EnrichmentConfig",
    "RankingCliConfig",
    "ComparisonConfig",
    "ComparisonData",
    "EditorContext",
    "PostGenerationContext",
    "MediaEnrichmentContext",
    "URLEnrichmentContext",
    "WriterPromptContext",
    # Legacy (will be removed)
    "load_site_config",
]
