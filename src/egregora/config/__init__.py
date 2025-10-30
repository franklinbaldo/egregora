"""Configuration management for Egregora."""

from .model import (
    ModelConfig,
    ModelType,
    load_site_config,
    DEFAULT_WRITER_MODEL,
    DEFAULT_ENRICHER_MODEL,
    DEFAULT_ENRICHER_VISION_MODEL,
    DEFAULT_RANKING_MODEL,
    DEFAULT_EDITOR_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_DIMENSIONALITY,
    KNOWN_EMBEDDING_DIMENSIONS,
)
from .site import (
    SitePaths,
    DEFAULT_BLOG_DIR,
    DEFAULT_DOCS_DIR,
    PROFILES_DIR_NAME,
    MEDIA_DIR_NAME,
    find_mkdocs_file,
    load_mkdocs_config,
    resolve_site_paths,
)
from .types import (
    ProcessConfig,
    RankingCliConfig,
    ComparisonConfig,
    ComparisonData,
    WriterConfig,
    WriterPromptContext,
    MediaEnrichmentContext,
    URLEnrichmentContext,
    EnrichmentConfig,
    EditorContext,
    PostGenerationContext,
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
