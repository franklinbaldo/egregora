#!/usr/bin/env python3
"""Generate configuration documentation from Pydantic models.

This script auto-generates docs/configuration.md from the Pydantic V2 models
in egregora.config.settings, ensuring documentation stays in sync with code.

Usage:
    python dev_tools/generate_config_docs.py
"""

from pathlib import Path
from typing import get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from egregora.config.settings import (
    DatabaseSettings,
    EgregoraConfig,
    EnrichmentSettings,
    FeaturesSettings,
    ModelSettings,
    OutputSettings,
    PathsSettings,
    PipelineSettings,
    PrivacySettings,
    QuotaSettings,
    RAGSettings,
    ReaderSettings,
    WriterAgentSettings,
)


def format_type(field_info: FieldInfo) -> str:
    """Format field type for documentation."""
    annotation = field_info.annotation

    # Handle Optional types
    origin = get_origin(annotation)
    if origin is type(None) or (origin and any(arg is type(None) for arg in get_args(annotation))):
        # Extract non-None type
        args = get_args(annotation)
        if args:
            non_none = next((arg for arg in args if arg is not type(None)), None)
            if non_none:
                type_str = getattr(non_none, "__name__", str(non_none))
                return f"`{type_str}` (optional)"

    # Handle list types
    if origin is list:
        args = get_args(annotation)
        if args:
            inner_type = getattr(args[0], "__name__", str(args[0]))
            return f"`list[{inner_type}]`"

    # Handle dict types
    if origin is dict:
        return "`dict`"

    # Simple types
    type_name = getattr(annotation, "__name__", str(annotation))
    return f"`{type_name}`"


def get_default_value(field_info: FieldInfo) -> str:
    """Get formatted default value."""
    if field_info.is_required():
        return "**required**"

    default = field_info.default
    if default is None:
        return "`null`"
    if isinstance(default, str):
        return f'`"{default}"`'
    if isinstance(default, int | float | bool):
        return f"`{default}`"
    if isinstance(default, list):
        return f"`{default}`"

    return f"`{default}`"


def document_model(model: type[BaseModel], level: int = 3) -> str:
    """Generate markdown documentation for a Pydantic model."""
    lines = []
    heading = "#" * level

    # Model name and docstring
    lines.append(f"{heading} {model.__name__}")
    lines.append("")
    if model.__doc__:
        lines.append(model.__doc__.strip())
        lines.append("")

    # Fields table
    lines.append("| Field | Type | Default | Description |")
    lines.append("|-------|------|---------|-------------|")

    for field_name, field_info in model.model_fields.items():
        type_str = format_type(field_info)
        default_str = get_default_value(field_info)
        description = field_info.description or ""

        lines.append(f"| `{field_name}` | {type_str} | {default_str} | {description} |")

    lines.append("")
    return "\n".join(lines)


def generate_config_docs() -> str:
    """Generate complete configuration documentation."""
    lines = [
        "# Configuration Reference",
        "",
        "Complete reference for `.egregora/config.yml` configuration file.",
        "",
        "**Auto-generated from Pydantic models** - Do not edit manually!",
        "To regenerate: `python dev_tools/generate_config_docs.py`",
        "",
        "## Overview",
        "",
        "Egregora uses Pydantic V2 for configuration with 13 settings classes:",
        "",
    ]

    # List all settings classes
    settings_classes = [
        ModelSettings,
        RAGSettings,
        WriterAgentSettings,
        PrivacySettings,
        EnrichmentSettings,
        PipelineSettings,
        PathsSettings,
        DatabaseSettings,
        OutputSettings,
        ReaderSettings,
        FeaturesSettings,
        QuotaSettings,
    ]

    lines.extend(
        f"- [`{cls.__name__}`](#{cls.__name__.lower()}) - {cls.__doc__ or 'Configuration settings'}"
        for cls in settings_classes
    )

    lines.extend(
        [
            "",
            "## Root Configuration",
            "",
            "The root configuration class is `EgregoraConfig`, which contains all other settings.",
            "",
        ]
    )

    # Document EgregoraConfig
    lines.append(document_model(EgregoraConfig, level=3))

    # Document each settings class
    lines.append("## Settings Classes")
    lines.append("")

    lines.extend(document_model(cls, level=3) for cls in settings_classes)

    # Add example configuration
    lines.extend(
        [
            "## Example Configuration",
            "",
            "```yaml",
            "# Minimal configuration",
            "models:",
            "  writer: google-gla:gemini-flash-latest",
            "  embedding: google-gla:gemini-embedding-001",
            "",
            "rag:",
            "  enabled: true",
            "  top_k: 5",
            "",
            "pipeline:",
            "  step_size: 1",
            "  step_unit: days",
            "```",
            "",
            "```yaml",
            "# Complete configuration with all options",
            "models:",
            "  writer: google-gla:gemini-flash-latest",
            "  enricher: google-gla:gemini-flash-latest",
            "  enricher_vision: google-gla:gemini-flash-latest",
            "  ranking: google-gla:gemini-flash-latest",
            "  editor: google-gla:gemini-flash-latest",
            "  reader: google-gla:gemini-flash-latest",
            "  embedding: google-gla:gemini-embedding-001",
            "  banner: google-gla:gemini-imagen-latest",
            "",
            "rag:",
            "  enabled: true",
            "  top_k: 5",
            "  min_similarity_threshold: 0.7",
            '  indexable_types: ["POST"]',
            "  embedding_max_batch_size: 100",
            "  embedding_timeout: 60.0",
            "  embedding_max_retries: 3",
            "",
            "writer:",
            "  custom_instructions: |",
            "    Write in a conversational tone.",
            "    Focus on clarity and simplicity.",
            "",
            "enrichment:",
            "  enabled: true",
            "  enable_url: true",
            "  enable_media: true",
            "  max_enrichments: 100",
            "",
            "pipeline:",
            "  step_size: 1",
            "  step_unit: days",
            "  overlap_ratio: 0.0",
            "  timezone: UTC",
            "  checkpoint_enabled: false",
            "",
            "paths:",
            "  egregora_dir: .egregora",
            "  docs_dir: docs",
            "  posts_dir: docs/blog/posts",
            "",
            "database:",
            "  pipeline_db: .egregora/pipeline.duckdb",
            "  runs_db: .egregora/runs.duckdb",
            "",
            "output:",
            "  format: mkdocs",
            "",
            "reader:",
            "  enabled: true",
            "  comparisons_per_post: 5",
            "  k_factor: 32",
            "",
            "quota:",
            "  daily_llm_requests: null",
            "  per_second_limit: 1.0",
            "  concurrency: 5",
            "```",
            "",
            "## Custom Prompts",
            "",
            "Override default prompts by placing Jinja2 templates in `.egregora/prompts/`:",
            "",
            "- `writer.jinja` - Writer agent prompt",
            "- `banner.jinja` - Banner agent prompt",
            "- `reader_system.jinja` - Reader system prompt",
            "- `media_detailed.jinja` - Media enrichment prompt",
            "- `url_detailed.jinja` - URL enrichment prompt",
            "",
            "## Programmatic Configuration",
            "",
            "```python",
            "from egregora.config.overrides import ConfigOverrideBuilder",
            "from egregora.config.settings import EgregoraConfig",
            "",
            "# Load base config",
            "config = EgregoraConfig.load()",
            "",
            "# Build overrides",
            "overrides = ConfigOverrideBuilder()",
            'overrides.set_model("writer", "google-gla:gemini-pro-latest")',
            "overrides.set_rag_enabled(False)",
            "",
            "# Apply overrides",
            "config = overrides.build(config)",
            "```",
            "",
            "## Related Documentation",
            "",
            "- [CLAUDE.md](../CLAUDE.md) - Quick reference",
            "- [Architecture Overview](architecture/README.md) - System architecture",
            "- [Protocols](architecture/protocols.md) - Core protocols",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    """Generate configuration documentation."""
    # Generate docs
    docs = generate_config_docs()

    # Write to file
    output_path = Path("docs/configuration.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(docs)


if __name__ == "__main__":
    main()
