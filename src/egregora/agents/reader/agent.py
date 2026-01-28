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
from tenacity import Retrying

from egregora.agents.reader.models import PostComparison, ReaderFeedback
from egregora.config.settings import EgregoraConfig
from egregora.llm.api_keys import get_google_api_key
from egregora.llm.retry import RETRY_IF, RETRY_STOP, RETRY_WAIT
from egregora.resources.prompts import render_prompt

if TYPE_CHECKING:
    from egregora.agents.reader.models import EvaluationRequest

logger = logging.getLogger(__name__)


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


def compare_posts(
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
        model: Optional model override (defaults to configured reader model)
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

    # Load configuration
    config = EgregoraConfig()
    model_name = model or config.models.reader
    system_prompt = render_prompt("reader_system.jinja")

    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    provider = GoogleProvider(api_key=get_google_api_key())
    model = GoogleModel(
        model_name.removeprefix("google-gla:"),
        provider=provider,
    )
    agent = Agent(model=model, output_type=ComparisonResult, system_prompt=system_prompt)

    logger.debug("Comparing posts: %s vs %s", request.post_a_slug, request.post_b_slug)

    for attempt in Retrying(stop=RETRY_STOP, wait=RETRY_WAIT, retry=RETRY_IF, reraise=True):
        with attempt:
            result = agent.run_sync(prompt)
    comparison_result = result.output

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
