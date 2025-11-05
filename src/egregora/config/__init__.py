"""Configuration management for Egregora."""

from egregora.config.model import (
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
    "DEFAULT_BLOG_DIR",
    "DEFAULT_DOCS_DIR",
    "DEFAULT_EDITOR_MODEL",
    "DEFAULT_EMBEDDING_DIMENSIONALITY",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_ENRICHER_MODEL",
    "DEFAULT_ENRICHER_VISION_MODEL",
    "DEFAULT_RANKING_MODEL",
    "DEFAULT_WRITER_MODEL",
    "KNOWN_EMBEDDING_DIMENSIONS",
    "MEDIA_DIR_NAME",
    "PROFILES_DIR_NAME",
    "ComparisonConfig",
    "ComparisonData",
    "EditorContext",
    "EnrichmentConfig",
    "MediaEnrichmentContext",
    # Model configuration
    "ModelConfig",
    "ModelType",
    "PostGenerationContext",
    # Configuration types
    "ProcessConfig",
    "RankingCliConfig",
    # Site configuration
    "SitePaths",
    "URLEnrichmentContext",
    "WriterConfig",
    "WriterPromptContext",
    "find_mkdocs_file",
    "load_mkdocs_config",
    "load_site_config",
    "resolve_site_paths",
]
