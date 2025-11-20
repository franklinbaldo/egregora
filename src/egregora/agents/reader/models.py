from __future__ import annotations

from pydantic import BaseModel, Field


class ReaderFeedback(BaseModel):
    """Reader feedback for a single post."""

    comment: str = Field(description="Natural language feedback about the post")
    star_rating: int = Field(ge=1, le=5, description="Star rating from 1-5")
    engagement_level: str = Field(description="Predicted engagement: low, medium, or high")


class EvaluationRequest(BaseModel):
    """Request payload for comparing two posts."""

    post_a_slug: str
    post_b_slug: str
    post_a_content: str
    post_b_content: str


class PostComparison(BaseModel):
    """Structured result of comparing two posts."""

    post_a_slug: str
    post_b_slug: str
    winner: str
    reasoning: str
    feedback_a: ReaderFeedback
    feedback_b: ReaderFeedback
