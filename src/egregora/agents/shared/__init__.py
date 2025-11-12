"""Agent tools and utilities.

This package contains tools that agents use to perform their tasks:
- rag: Retrieval augmented generation
- annotations: Conversation annotation storage
- profiler: Author profiling
- shared: Common tool functions (edit_line, query_rag, etc.)
"""

from egregora.agents.shared.annotations import AnnotationStore
from egregora.agents.shared.author_profiles import get_active_authors
from egregora.agents.shared.llm_tools import AVAILABLE_TOOLS

__all__ = ["AVAILABLE_TOOLS", "AnnotationStore", "get_active_authors"]
