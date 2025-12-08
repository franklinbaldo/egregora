"""Reader agent for post quality evaluation via pairwise comparisons.

The reader agent evaluates blog posts by comparing them pairwise and providing
structured feedback. It operates on Documents delivered by output adapters.

Public API:
    - compare_posts: Main evaluation function
    - EvaluationRequest: Request model with two Documents
    - PostComparison: Result model with winner and feedback
    - ReaderFeedback: Per-post feedback model
    - RankingResult: Final ranking result model

Example:
    >>> from egregora.agents.reader import compare_posts, EvaluationRequest
    >>> from egregora.data_primitives import Document, DocumentType
    >>>
    >>> post_a = Document(content="...", type=DocumentType.POST, metadata={"slug": "post-a"})
    >>> post_b = Document(content="...", type=DocumentType.POST, metadata={"slug": "post-b"})
    >>> request = EvaluationRequest(post_a=post_a, post_b=post_b)
    >>>
    >>> comparison = await compare_posts(request)
    >>> print(comparison.winner)  # 'a', 'b', or 'tie'

"""

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
