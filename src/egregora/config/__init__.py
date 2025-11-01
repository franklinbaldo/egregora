"""Configuration management for Egregora."""

from .model import (
    DEFAULT_EDITOR_MODEL,
    DEFAULT_EMBEDDING_DIMENSIONALITY,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_ENRICHER_MODEL,
    DEFAULT_ENRICHER_VISION_MODEL,
    DEFAULT_RANKING_MODEL,
    DEFAULT_WRITER_MODEL,
    KNOWN_EMBEDDING_DIMENSIONS,
    ModelConfig,
    ModelType,
    load_site_config,
)
from .site import (
    DEFAULT_BLOG_DIR,
    DEFAULT_DOCS_DIR,
    MEDIA_DIR_NAME,
    PROFILES_DIR_NAME,
    SitePaths,
    find_mkdocs_file,
    load_mkdocs_config,
    resolve_site_paths,
)
from .types import (
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
    # Model configuration
    "ModelConfig",
    "ModelType",
    "load_site_config",
    "DEFAULT_WRITER_MODEL",
    "DEFAULT_ENRICHER_MODEL",
    "DEFAULT_ENRICHER_VISION_MODEL",
    "DEFAULT_RANKING_MODEL",
    "DEFAULT_EDITOR_MODEL",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_EMBEDDING_DIMENSIONALITY",
    "KNOWN_EMBEDDING_DIMENSIONS",
    # Site configuration
    "SitePaths",
    "DEFAULT_BLOG_DIR",
    "DEFAULT_DOCS_DIR",
    "PROFILES_DIR_NAME",
    "MEDIA_DIR_NAME",
    "find_mkdocs_file",
    "load_mkdocs_config",
    "resolve_site_paths",
    # Configuration types
    "ProcessConfig",
    "RankingCliConfig",
    "ComparisonConfig",
    "ComparisonData",
    "WriterConfig",
    "WriterPromptContext",
    "MediaEnrichmentContext",
    "URLEnrichmentContext",
    "EnrichmentConfig",
    "EditorContext",
    "PostGenerationContext",
]
