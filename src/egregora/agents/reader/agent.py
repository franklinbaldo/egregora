"""Pydantic AI reader agent for post quality evaluation.

The reader agent simulates human readers performing pairwise post comparisons,
providing structured feedback, and determining winners for ELO ranking.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from egregora.agents.reader.models import PostComparison, ReaderFeedback

if TYPE_CHECKING:
    from egregora.agents.reader.models import EvaluationRequest

logger = logging.getLogger(__name__)


# System prompt for reader agent
READER_SYSTEM_PROMPT = """You are a discerning reader evaluating blog posts.

Your task is to compare two blog posts and determine which one is better quality.
Consider these criteria:

1. **Clarity**: Is the writing clear and easy to understand?
2. **Engagement**: Would this keep a reader's interest?
3. **Insight**: Does it offer valuable or interesting perspectives?
4. **Structure**: Is it well-organized and flows logically?
5. **Authenticity**: Does it feel genuine rather than generic?

For each post, provide:
- A star rating (1-5 stars)
- Engagement level (low, medium, high)
- Constructive feedback

Then decide which post is better overall, or if they're equal quality (tie).
"""


# Pydantic models for agent result
class ReaderFeedbackResult(BaseModel):
    """Feedback for a single post."""

    comment: str = Field(description="Natural language feedback about the post")
    star_rating: int = Field(ge=1, le=5, description="Star rating from 1-5")
    engagement_level: str = Field(description="Predicted engagement: low, medium, or high")


class ComparisonResult(BaseModel):
    """Result of comparing two posts."""

    winner: str = Field(description="Which post won: 'a', 'b', or 'tie'")
    reasoning: str = Field(description="Explanation of the choice")
    feedback_a: ReaderFeedbackResult = Field(description="Feedback for post A")
    feedback_b: ReaderFeedbackResult = Field(description="Feedback for post B")


# Reader agent dependencies (passed via RunContext)
class ReaderDeps(BaseModel):
    """Dependencies for reader agent."""

    post_a_slug: str
    post_b_slug: str


def _create_reader_agent(model: str) -> Agent[ReaderDeps, ComparisonResult]:
    """Create reader agent instance with specified model."""
    return Agent(
        model,
        result_type=ComparisonResult,
        system_prompt=READER_SYSTEM_PROMPT,
        deps_type=ReaderDeps,
    )


async def compare_posts(
    request: EvaluationRequest,
    model: str | None = None,
) -> PostComparison:
    """Compare two posts and return structured comparison result.

    Args:
        request: Evaluation request with post slugs and content
        model: Optional model override (defaults to gemini-2.0-flash-exp)

    Returns:
        PostComparison with winner, reasoning, and feedback for both posts

    Example:
        >>> request = EvaluationRequest(
        ...     post_a_slug="intro-to-python",
        ...     post_b_slug="advanced-python",
        ...     post_a_content="# Intro to Python\n\n...",
        ...     post_b_content="# Advanced Python\n\n...",
        ... )
        >>> comparison = await compare_posts(request)
        >>> print(comparison.winner)  # 'a', 'b', or 'tie'
    """
    # Prepare dependencies
    deps = ReaderDeps(
        post_a_slug=request.post_a_slug,
        post_b_slug=request.post_b_slug,
    )

    # Build comparison prompt
    prompt = f"""Compare these two blog posts:

# Post A ({request.post_a_slug})
{request.post_a_content}

# Post B ({request.post_b_slug})
{request.post_b_content}

Evaluate both posts and determine which is better quality overall.
"""

    # Create agent with specified model (or default)
    agent_model = model or "google-gla:gemini-2.0-flash-exp"
    agent = _create_reader_agent(agent_model)

    # Run agent
    result = await agent.run(prompt, deps=deps)

    # Convert agent result to PostComparison
    return PostComparison(
        post_a_slug=request.post_a_slug,
        post_b_slug=request.post_b_slug,
        winner=result.data.winner,  # type: ignore[attr-defined]
        reasoning=result.data.reasoning,  # type: ignore[attr-defined]
        feedback_a=ReaderFeedback(
            comment=result.data.feedback_a.comment,  # type: ignore[attr-defined]
            star_rating=result.data.feedback_a.star_rating,  # type: ignore[attr-defined]
            engagement_level=result.data.feedback_a.engagement_level,  # type: ignore[attr-defined]
        ),
        feedback_b=ReaderFeedback(
            comment=result.data.feedback_b.comment,  # type: ignore[attr-defined]
            star_rating=result.data.feedback_b.star_rating,  # type: ignore[attr-defined]
            engagement_level=result.data.feedback_b.engagement_level,  # type: ignore[attr-defined]
        ),
    )
