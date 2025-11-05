"""Agent tools and utilities.

This package contains tools that agents use to perform their tasks:
- rag: Retrieval augmented generation
- annotations: Conversation annotation storage
- profiler: Author profiling
- shared: Common tool functions (edit_line, query_rag, etc.)
"""

from egregora.agents.tools.annotations import AnnotationStore
from egregora.agents.tools.profiler import get_active_authors
from egregora.agents.tools.shared import AVAILABLE_TOOLS

__all__ = [
    "AVAILABLE_TOOLS",
    "AnnotationStore",
    "get_active_authors",
]
