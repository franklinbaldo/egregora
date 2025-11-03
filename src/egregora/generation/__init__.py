"""Generation stage - LLM-powered content creation.

This package handles content generation:
- Blog post writing via LLM with tool calling
- Interactive document editing
"""

from . import editor, writer
from .writer import write_posts_for_period

__all__ = [
    "writer",
    "editor",
    "write_posts_for_period",
]
