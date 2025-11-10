"""Simple writer: LLM with write_post tool for editorial control.

The LLM decides what's worth writing, how many posts to create, and all metadata.
Uses function calling (write_post tool) to generate 0-N posts per window.

Documentation:
- Multi-Post Generation: docs/features/multi-post.md
- Architecture (Writer): docs/guides/architecture.md#5-writer-writerpy
- Core Concepts (Editorial Control): docs/getting-started/concepts.md#editorial-control-llm-decision-making
"""

from egregora.agents.writer.core import (
    WriterConfig,
    get_top_authors,
    index_all_posts_for_rag,
    index_new_posts_for_rag,
    write_posts_for_window,
)
from egregora.agents.writer.tools import PostMetadata

__all__ = [
    "PostMetadata",
    "WriterConfig",
    "get_top_authors",
    "index_all_posts_for_rag",
    "index_new_posts_for_rag",
    "write_posts_for_window",
]
