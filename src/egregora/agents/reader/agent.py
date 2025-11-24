"""Pydantic AI reader agent for post quality evaluation.

The reader agent simulates human readers performing pairwise post comparisons,
providing structured feedback, and determining winners for ELO ranking.

The agent operates on Documents delivered by output adapters, maintaining clean
separation between the pipeline (produces Documents) and evaluation (consumes Documents).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from egregora.agents.reader.models import PostComparison, ReaderFeedback
from egregora.utils.retry import RetryPolicy, retry_async

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
    engagement_level: Literal["low", "medium", "high"] = Field(
        description="Predicted engagement: low, medium, or high"
    )


class ComparisonResult(BaseModel):
    """Result of comparing two posts."""

    winner: Literal["a", "b", "tie"] = Field(description="Which post won: 'a', 'b', or 'tie'")
    reasoning: str = Field(description="Explanation of the choice")
    feedback_a: ReaderFeedbackResult = Field(description="Feedback for post A")
    feedback_b: ReaderFeedbackResult = Field(description="Feedback for post B")


async def compare_posts(
    request: EvaluationRequest,
    model: str | None = None,
    api_key: str | None = None,
) -> PostComparison:
    r"""Compare two posts and return structured comparison result.

    The reader agent evaluates Documents delivered by output adapters. Each
    EvaluationRequest contains two Document instances with full content and metadata.

    Uses pydantic-ai for structured output generation.

    Args:
        request: Evaluation request with two Document instances
        model: Optional model override (defaults to google-gla:gemini-flash-latest)
        api_key: Optional API key (defaults to GOOGLE_API_KEY env var)

    Returns:
        PostComparison with winner, reasoning, feedback, and Document references

    """
    # Ensure API key availability (PydanticAI will pick it up from env if not explicitly passed,
    # but we check here for early failure if completely missing)
    if not api_key and not os.environ.get("GOOGLE_API_KEY"):
        msg = "GOOGLE_API_KEY environment variable not set"
        raise ValueError(msg)

    # Build comparison prompt
    prompt = f"""Compare these two blog posts:

# Post A ({request.post_a_slug})
{request.post_a_content}

# Post B ({request.post_b_slug})
{request.post_b_content}

Evaluate both posts and determine which is better quality overall.
"""

    # Use default model if not specified
    # Note: PydanticAI models are typically "provider:model", e.g. "google-gla:gemini-flash-latest"
    model_name = model or "google-gla:gemini-flash-latest"

    agent = Agent(model=model_name, result_type=ComparisonResult, system_prompt=READER_SYSTEM_PROMPT)

    logger.debug("Comparing posts: %s vs %s", request.post_a_slug, request.post_b_slug)

    async def _run_agent() -> ComparisonResult:
        result = await agent.run(prompt)
        return result.data

    # Execute with centralized retry policy
    comparison_result = await retry_async(_run_agent, RetryPolicy())

    # Convert to PostComparison (includes full Document references)
    return PostComparison(
        post_a=request.post_a,
        post_b=request.post_b,
        winner=comparison_result.winner,
        reasoning=comparison_result.reasoning,
        feedback_a=ReaderFeedback(
            comment=comparison_result.feedback_a.comment,
            star_rating=comparison_result.feedback_a.star_rating,
            engagement_level=comparison_result.feedback_a.engagement_level,
        ),
        feedback_b=ReaderFeedback(
            comment=comparison_result.feedback_b.comment,
            star_rating=comparison_result.feedback_b.star_rating,
            engagement_level=comparison_result.feedback_b.engagement_level,
        ),
    )
