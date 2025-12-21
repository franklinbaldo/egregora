"""Writer agent package entry point.

Refactored from `egregora.agents.writer` into a cohesive package.
"""

from egregora.agents.writer.agent import write_posts_with_pydantic_agent
from egregora.agents.writer.orchestrator import (
    WindowProcessingParams,
    write_posts_for_window,
)

__all__ = ["WindowProcessingParams", "write_posts_for_window", "write_posts_with_pydantic_agent"]
