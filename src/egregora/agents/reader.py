"""Reader agent package - backward compatibility shim.

This module maintains backward compatibility for existing imports while the
reader agent has been refactored into a package structure.

Deprecated: Import directly from egregora.agents.reader instead.

New structure:
    - egregora.agents.reader.agent: Core comparison logic
    - egregora.agents.reader.models: Data models
    - egregora.agents.reader: Public API

Example (preferred):
    >>> from egregora.agents.reader import compare_posts, EvaluationRequest

Example (deprecated, still works):
    >>> from egregora.agents.reader import compare_posts  # Same as above

"""

# Re-export public API for backward compatibility
from egregora.agents.reader.agent import compare_posts
from egregora.agents.reader.models import (
    EvaluationRequest,
    PostComparison,
    RankingResult,
    ReaderFeedback,
)

__all__ = [
    "EvaluationRequest",
    "PostComparison",
    "RankingResult",
    "ReaderFeedback",
    "compare_posts",
]
