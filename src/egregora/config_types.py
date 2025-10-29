"""Configuration dataclasses to reduce function parameter counts."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .model_config import ModelConfig
from .types import GroupSlug


@dataclass
class ProcessConfig:
    """Configuration for WhatsApp export processing."""

    zip_file: Path
    output_dir: Path
    period: str = "day"
    enable_enrichment: bool = True
    from_date: date | None = None
    to_date: date | None = None
    timezone: str | None = None
    gemini_key: str | None = None
    model: str | None = None
    debug: bool = False
    retrieval_mode: str = "ann"
    retrieval_nprobe: int | None = None
    retrieval_overfetch: int | None = None


@dataclass
class RankingCliConfig:
    """Configuration for ranking CLI command."""

    site_dir: Path
    comparisons: int = 1
    strategy: str = "fewest_games"
    export_parquet: bool = False
    model: str | None = None
    debug: bool = False


@dataclass
class ComparisonConfig:
    """Configuration for a single ranking comparison."""

    site_dir: Path
    api_key: str
    model: str
    profile_id: str


@dataclass
class ComparisonData:
    """Data from a completed comparison."""

    comparison_id: str
    timestamp: str  # Will be datetime but keeping as str for now
    profile_id: str
    post_a: str
    post_b: str
    winner: str
    comment_a: str
    stars_a: int
    comment_b: str
    stars_b: int


@dataclass
class WriterConfig:
    """Configuration for post writing."""

    posts_dir: Path
    profiles_dir: Path
    rag_dir: Path
    model_config: ModelConfig | None = None
    enable_rag: bool = True
    retrieval_mode: str = "ann"
    retrieval_nprobe: int | None = None
    retrieval_overfetch: int | None = None


@dataclass
class WriterPromptContext:
    """Context for rendering writer prompts."""

    date: str
    markdown_table: str
    active_authors: str
    group_name: str
    custom_instructions: str
    enable_rag: bool
    rag_context: str


@dataclass
class MediaEnrichmentContext:
    """Context for media enrichment prompts."""

    media_type: str
    media_filename: str
    author: str
    timestamp: str
    nearby_messages: str
    ocr_text: str = ""
    detected_objects: str = ""


@dataclass
class URLEnrichmentContext:
    """Context for URL enrichment prompts."""

    url: str
    date: str
    time: str
    author: str
    nearby_messages: str


@dataclass
class EnrichmentConfig:
    """Configuration for enrichment operations."""

    client: object  # genai.Client
    output_dir: Path
    model: str = "models/gemini-flash-latest"


@dataclass
class EditorContext:
    """Context for editor session setup."""

    post_path: Path
    site_dir: Path
    rag_dir: Path
    model_config: ModelConfig
    additional_context: str = ""


@dataclass
class PostGenerationContext:
    """Context for generating a single post."""

    date: str
    group_slug: GroupSlug
    markdown_table: str
    active_authors: list[str]
    custom_writer_prompt: str | None
    config: WriterConfig
    enable_rag: bool = True
    rag_context: str = ""


@dataclass
class SearchConfig:
    """Configuration for vector search."""

    embedding_dimensionality: int
    where_clause: str
    order_clause: str
    params: list
    min_similarity: float
    top_k: int
    overfetch: int | None
    nprobe: int | None
