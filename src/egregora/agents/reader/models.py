"""Data models for reader agent evaluation and feedback.

Defines structured types for post comparisons, reader feedback, and evaluation results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


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
        max_stars = 5
        if not 1 <= self.star_rating <= max_stars:
            msg = f"Star rating must be 1-{max_stars}, got {self.star_rating}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PostComparison:
    """Result of comparing two posts."""

    post_a_slug: str
    """Slug of first post"""

    post_b_slug: str
    """Slug of second post"""

    winner: Literal["a", "b", "tie"]
    """Which post the reader preferred"""

    reasoning: str
    """Natural language explanation of the choice"""

    feedback_a: ReaderFeedback
    """Feedback for post A"""

    feedback_b: ReaderFeedback
    """Feedback for post B"""


@dataclass(frozen=True, slots=True)
class EvaluationRequest:
    """Request to evaluate posts."""

    post_a_slug: str
    """Slug of first post"""

    post_b_slug: str
    """Slug of second post"""

    post_a_content: str
    """Full markdown content of post A"""

    post_b_content: str
    """Full markdown content of post B"""


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
