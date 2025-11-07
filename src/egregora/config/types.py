"""Configuration dataclasses to reduce function parameter counts."""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

from egregora.config.model import ModelConfig


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
    step_size: Annotated[int, "Size of each processing window"] = 1
    step_unit: Annotated[str, "Unit for windowing: 'messages', 'hours', 'days'"] = "days"
    overlap_ratio: Annotated[float, "Fraction of window to overlap (0.0-0.5, default 0.2 = 20%)"] = 0.2
    max_window_time: Annotated[timedelta | None, "Optional maximum time span per window"] = None
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
    max_prompt_tokens: Annotated[int, "Maximum tokens per prompt (default 100k cap)"] = 100_000
    use_full_context_window: Annotated[
        bool, "Override max_prompt_tokens and use full model context window"
    ] = False

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
class EnrichmentConfig:
    """Configuration for enrichment operations."""

    client: Annotated[object, "The Gemini client"]
    output_dir: Annotated[Path, "The directory to save enriched data"]
    model: Annotated[str, "The Gemini model to use for enrichment"] = "models/gemini-flash-latest"
