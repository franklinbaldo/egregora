"""Data models for reader agent evaluation and feedback.

Defines structured types for post comparisons, reader feedback, and evaluation results.

The reader agent consumes Documents produced by the pipeline and delivered by output
adapters. All evaluation operates on Document instances, not raw strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from egregora.data_primitives import Document

# Constants for validation
MIN_STAR_RATING = 1
MAX_STAR_RATING = 5


@dataclass(frozen=True, slots=True)
class ReaderFeedback:
    """Structured feedback from a simulated reader."""

    comment: str
    """Natural language feedback about the post"""

    star_rating: int
    """Star rating from 1-5"""

    engagement_level: Literal["low", "medium", "high"]
    """Predicted reader engagement"""

    def __post_init__(self) -> None:
        """Validate star rating is in valid range."""
        if not MIN_STAR_RATING <= self.star_rating <= MAX_STAR_RATING:
            msg = f"Star rating must be {MIN_STAR_RATING}-{MAX_STAR_RATING}, got {self.star_rating}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PostComparison:
    """Result of comparing two posts.

    The reader agent evaluates Documents delivered by output adapters.
    Each comparison references the evaluated Documents directly.
    """

    post_a: Document
    """First post (Document instance)"""

    post_b: Document
    """Second post (Document instance)"""

    winner: Literal["a", "b", "tie"]
    """Which post the reader preferred"""

    reasoning: str
    """Natural language explanation of the choice"""

    feedback_a: ReaderFeedback
    """Feedback for post A"""

    feedback_b: ReaderFeedback
    """Feedback for post B"""

    @property
    def post_a_slug(self) -> str:
        """Slug of post A (extracted from Document metadata)."""
        return str(self.post_a.metadata.get("slug", self.post_a.document_id[:8]))

    @property
    def post_b_slug(self) -> str:
        """Slug of post B (extracted from Document metadata)."""
        return str(self.post_b.metadata.get("slug", self.post_b.document_id[:8]))


@dataclass(frozen=True, slots=True)
class EvaluationRequest:
    """Request to evaluate posts.

    The reader agent operates on Documents produced by the pipeline.
    Output adapters deliver Documents to the reader for evaluation.
    """

    post_a: Document
    """First post (Document instance with content and metadata)"""

    post_b: Document
    """Second post (Document instance with content and metadata)"""

    @property
    def post_a_slug(self) -> str:
        """Slug of post A (extracted from Document metadata)."""
        return str(self.post_a.metadata.get("slug", self.post_a.document_id[:8]))

    @property
    def post_b_slug(self) -> str:
        """Slug of post B (extracted from Document metadata)."""
        return str(self.post_b.metadata.get("slug", self.post_b.document_id[:8]))

    @property
    def post_a_content(self) -> str:
        """Content of post A (extracted from Document)."""
        if isinstance(self.post_a.content, bytes):
            return self.post_a.content.decode("utf-8")
        return self.post_a.content

    @property
    def post_b_content(self) -> str:
        """Content of post B (extracted from Document)."""
        if isinstance(self.post_b.content, bytes):
            return self.post_b.content.decode("utf-8")
        return self.post_b.content


@dataclass(frozen=True, slots=True)
class RankingResult:
    """Post quality ranking result."""

    post_slug: str
    """Post identifier"""

    rating: float
    """ELO rating"""

    rank: int
    """Position in ranking (1 = highest)"""

    comparisons: int
    """Number of comparisons performed"""

    win_rate: float
    """Percentage of comparisons won"""
