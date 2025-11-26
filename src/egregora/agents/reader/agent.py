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
from egregora.config.settings import EgregoraConfig
from egregora.resources.prompts import render_prompt
from egregora.utils.retry import retry_async
from llama_index.core.program import LLMTextCompletionProgram
from llama_index.llms.gemini import Gemini

if TYPE_CHECKING:
    from egregora.agents.reader.models import EvaluationRequest

logger = logging.getLogger(__name__)


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
    """Compare two posts and return structured comparison result."""
    config = EgregoraConfig()
    use_llama_index = config.agent.engine == "llama-index"

    if use_llama_index:
        return await compare_posts_with_llama_index(request, model, api_key)
    return await compare_posts_with_pydantic_ai(request, model, api_key)


async def compare_posts_with_llama_index(
    request: EvaluationRequest,
    model: str | None = None,
    api_key: str | None = None,
) -> PostComparison:
    """Compare two posts using LlamaIndex PydanticProgram."""
    if not api_key and not os.environ.get("GOOGLE_API_KEY"):
        msg = "GOOGLE_API_KEY environment variable not set"
        raise ValueError(msg)

    config = EgregoraConfig()
    model_name = model or config.models.reader
    system_prompt = render_prompt("reader_system.jinja")

    prompt_template_str = f"""{system_prompt}

Compare these two blog posts:

# Post A ({request.post_a_slug})
{request.post_a_content}

# Post B ({request.post_b_slug})
{request.post_b_content}

Evaluate both posts and determine which is better quality overall.
"""

    program = LLMTextCompletionProgram.from_defaults(
        output_cls=ComparisonResult,
        llm=Gemini(model_name=model_name),
        prompt_template_str=prompt_template_str,
        verbose=True,
    )

    async def _run_program() -> ComparisonResult:
        return await program.acall()

    comparison_result = await retry_async(_run_program)
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


async def compare_posts_with_pydantic_ai(
    request: EvaluationRequest,
    model: str | None = None,
    api_key: str | None = None,
) -> PostComparison:
    """Original implementation with pydantic-ai."""
    if not api_key and not os.environ.get("GOOGLE_API_KEY"):
        msg = "GOOGLE_API_KEY environment variable not set"
        raise ValueError(msg)

    prompt = f"""Compare these two blog posts:

# Post A ({request.post_a_slug})
{request.post_a_content}

# Post B ({request.post_b_slug})
{request.post_b_content}

Evaluate both posts and determine which is better quality overall.
"""
    config = EgregoraConfig()
    model_name = model or config.models.reader
    system_prompt = render_prompt("reader_system.jinja")
    agent = Agent(model=model_name, result_type=ComparisonResult, system_prompt=system_prompt)

    logger.debug("Comparing posts: %s vs %s", request.post_a_slug, request.post_b_slug)

    async def _run_agent() -> ComparisonResult:
        result = await agent.run(prompt)
        return result.data

    comparison_result = await retry_async(_run_agent)
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
