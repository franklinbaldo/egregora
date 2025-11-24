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

Your task is to compare two blog posts and determine which is better quality.
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

    Implements exponential backoff retry strategy for rate limit errors via shared utility.

    Args:
        request: Evaluation request with two Document instances
        model: Optional model override (defaults to gemini-flash-latest)
        api_key: Optional API key (defaults to GOOGLE_API_KEY env var)

    Returns:
        PostComparison with winner, reasoning, feedback, and Document references

    Raises:
        RuntimeError: On persistent errors after retries

    """
    # Get API key from environment
    api_key = api_key or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        msg = "GOOGLE_API_KEY environment variable not set"
        raise ValueError(msg)

    # Ensure env var is set for pydantic_ai if provided explicitly
    if api_key and "GOOGLE_API_KEY" not in os.environ:
        os.environ["GOOGLE_API_KEY"] = api_key

    # Use default model if not specified
    model_name = model or "gemini-flash-latest"

    # Initialize agent
    # We construct the model string assuming google-gla provider for consistency
    agent_model = f"google-gla:{model_name}" if ":" not in model_name else model_name

    agent = Agent(
        agent_model,
        result_type=ComparisonResult,
        system_prompt=READER_SYSTEM_PROMPT,
    )

    # Build comparison prompt
    prompt = f"""Compare these two blog posts:

# Post A ({request.post_a_slug})
{request.post_a_content}

# Post B ({request.post_b_slug})
{request.post_b_content}

Evaluate both posts and determine which is better quality overall.
"""

    logger.debug("Comparing posts: %s vs %s", request.post_a_slug, request.post_b_slug)

    async def _run_agent() -> Any:
        return await agent.run(prompt)

    # Execute with shared retry policy
    policy = RetryPolicy(max_attempts=5)

    # Run the agent
    result = await retry_async(_run_agent, policy)
    data = result.data

    # Convert to PostComparison (includes full Document references)
    return PostComparison(
        post_a=request.post_a,
        post_b=request.post_b,
        winner=data.winner,
        reasoning=data.reasoning,
        feedback_a=ReaderFeedback(
            comment=data.feedback_a.comment,
            star_rating=data.feedback_a.star_rating,
            engagement_level=data.feedback_a.engagement_level,
        ),
        feedback_b=ReaderFeedback(
            comment=data.feedback_b.comment,
            star_rating=data.feedback_b.star_rating,
            engagement_level=data.feedback_b.engagement_level,
        ),
    )
