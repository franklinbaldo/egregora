"""Configuration dataclasses to reduce function parameter counts."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated

from egregora.config.model import ModelConfig
from egregora.types import GroupSlug


@dataclass
class ProcessConfig:
    """Configuration for chat export processing (source-agnostic).

    This config object replaces long parameter lists (15+ params) with a single
    structured configuration object. Benefits:
    - Type safety and validation
    - Clear grouping of related settings
    - Easy to extend with new options
    - Simpler function signatures
    - Works with any source (WhatsApp, Slack, Discord, etc.)
    """

    zip_file: Annotated[Path, "Path to the chat export file (ZIP, JSON, etc.)"]
    output_dir: Annotated[Path, "Directory for the generated site"]
    period: Annotated[str, "Grouping period: 'day' or 'week'"] = "day"
    enable_enrichment: Annotated[bool, "Enable LLM enrichment for URLs/media"] = True
    from_date: Annotated[date | None, "Only process messages from this date onwards"] = None
    to_date: Annotated[date | None, "Only process messages up to this date"] = None
    timezone: Annotated[str | None, "Timezone for date parsing (e.g., 'America/New_York')"] = None
    gemini_key: Annotated[str | None, "Google Gemini API key"] = None
    model: Annotated[str | None, "Gemini model to use (or configure in mkdocs.yml)"] = None
    debug: Annotated[bool, "Enable debug logging"] = False
    retrieval_mode: Annotated[str, "Retrieval strategy: 'ann' (default) or 'exact'"] = "ann"
    retrieval_nprobe: Annotated[int | None, "Advanced: override DuckDB VSS nprobe for ANN retrieval"] = None
    retrieval_overfetch: Annotated[int | None, "Advanced: multiply ANN candidate pool before filtering"] = (
        None
    )
    batch_threshold: Annotated[int, "Minimum items before batching API calls"] = 10

    @property
    def input_path(self) -> Path:
        """Alias for zip_file (source-agnostic naming).

        Returns the input file path regardless of format (ZIP, JSON, etc.).
        This property provides a more generic name while maintaining
        backward compatibility with the zip_file field.
        """
        return self.zip_file


@dataclass
class RankingCliConfig:
    """Configuration for ranking CLI command."""

    site_dir: Annotated[Path, "Path to MkDocs site directory"]
    comparisons: Annotated[int, "Number of comparisons to run"] = 1
    strategy: Annotated[str, "Post selection strategy"] = "fewest_games"
    export_parquet: Annotated[bool, "Export rankings to Parquet after comparisons"] = False
    model: Annotated[str | None, "Gemini model to use (or configure in mkdocs.yml)"] = None
    debug: Annotated[bool, "Enable debug logging"] = False


@dataclass
class ComparisonConfig:
    """Configuration for a single ranking comparison."""

    site_dir: Annotated[Path, "Path to MkDocs site directory"]
    api_key: Annotated[str, "Google Gemini API key"]
    model: Annotated[str, "Gemini model to use for ranking"]
    profile_id: Annotated[str, "ID of the profile to use as the judge"]


@dataclass
class ComparisonData:
    """Data from a completed comparison."""

    comparison_id: Annotated[str, "Unique ID for the comparison"]
    timestamp: Annotated[str, "Timestamp of the comparison"]
    profile_id: Annotated[str, "ID of the profile used as the judge"]
    post_a: Annotated[str, "ID of the first post"]
    post_b: Annotated[str, "ID of the second post"]
    winner: Annotated[str, "ID of the winning post"]
    comment_a: Annotated[str, "Judge's comment on post A"]
    stars_a: Annotated[int, "Judge's star rating for post A"]
    comment_b: Annotated[str, "Judge's comment on post B"]
    stars_b: Annotated[int, "Judge's star rating for post B"]


@dataclass
class WriterConfig:
    """Configuration for post writing."""

    posts_dir: Annotated[Path, "Directory to save posts"]
    profiles_dir: Annotated[Path, "Directory to save profiles"]
    rag_dir: Annotated[Path, "Directory for RAG data"]
    model_config: Annotated[ModelConfig | None, "Model configuration"] = None
    enable_rag: Annotated[bool, "Enable RAG"] = True


@dataclass
class WriterPromptContext:
    """Context for rendering writer prompts."""

    date: Annotated[str, "The date of the period being processed"]
    markdown_table: Annotated[str, "The conversation formatted as a markdown table"]
    active_authors: Annotated[str, "A list of active authors in the period"]
    group_name: Annotated[str, "The name of the WhatsApp group"]
    custom_instructions: Annotated[str, "Custom instructions for the writer from the site config"]
    enable_rag: Annotated[bool, "Whether RAG is enabled"]
    rag_context: Annotated[str, "The context retrieved from the RAG system"]


@dataclass
class MediaEnrichmentContext:
    """Context for media enrichment prompts."""

    media_type: Annotated[str, "The type of media (e.g., 'image', 'video')"]
    media_filename: Annotated[str, "The filename of the media"]
    author: Annotated[str, "The author of the message containing the media"]
    timestamp: Annotated[str, "The timestamp of the message"]
    nearby_messages: Annotated[str, "Messages sent immediately before and after the media"]
    ocr_text: Annotated[str, "Text extracted from the media via OCR"] = ""
    detected_objects: Annotated[str, "Objects detected in the media"] = ""


@dataclass
class URLEnrichmentContext:
    """Context for URL enrichment prompts."""

    url: Annotated[str, "The URL to enrich"]
    date: Annotated[str, "The date of the message containing the URL"]
    time: Annotated[str, "The time of the message containing the URL"]
    author: Annotated[str, "The author of the message"]
    nearby_messages: Annotated[str, "Messages sent immediately before and after the URL"]


@dataclass
class EnrichmentConfig:
    """Configuration for enrichment operations."""

    client: Annotated[object, "The Gemini client"]
    output_dir: Annotated[Path, "The directory to save enriched data"]
    model: Annotated[str, "The Gemini model to use for enrichment"] = "models/gemini-flash-latest"


@dataclass
class EditorContext:
    """Context for editor session setup."""

    post_path: Annotated[Path, "The path to the post being edited"]
    site_dir: Annotated[Path, "The path to the site directory"]
    rag_dir: Annotated[Path, "The path to the RAG directory"]
    model_config: Annotated[ModelConfig, "The model configuration"]
    additional_context: Annotated[str, "Additional context for the editor"] = ""


@dataclass
class PostGenerationContext:
    """Context for generating a single post."""

    date: Annotated[str, "The date of the period being processed"]
    group_slug: Annotated[GroupSlug, "The slug of the WhatsApp group"]
    markdown_table: Annotated[str, "The conversation formatted as a markdown table"]
    active_authors: Annotated[list[str], "A list of active authors in the period"]
    custom_writer_prompt: Annotated[str | None, "Custom instructions for the writer from the site config"]
    config: Annotated[WriterConfig, "The writer configuration"]
    enable_rag: Annotated[bool, "Whether RAG is enabled"] = True
    rag_context: Annotated[str, "The context retrieved from the RAG system"] = ""
