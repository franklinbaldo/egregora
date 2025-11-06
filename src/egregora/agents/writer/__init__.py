"""Simple writer: LLM with write_post tool for editorial control.

The LLM decides what's worth writing, how many posts to create, and all metadata.
Uses function calling (write_post tool) to generate 0-N posts per period.

Documentation:
- Multi-Post Generation: docs/features/multi-post.md
- Architecture (Writer): docs/guides/architecture.md#5-writer-writerpy
- Core Concepts (Editorial Control): docs/getting-started/concepts.md#editorial-control-llm-decision-making
"""

from egregora.agents.writer.core import (
    WriterConfig,
    get_top_authors,
    load_markdown_extensions,
    load_site_config,
    write_posts_for_period,
)
from egregora.agents.writer.tools import PostMetadata

__all__ = [
    "PostMetadata",
    "WriterConfig",
    "get_top_authors",
    "load_markdown_extensions",
    "load_site_config",
    "write_posts_for_period",
]
