"""Pydantic AI reader agent for post quality evaluation.

The reader agent simulates human readers performing pairwise post comparisons,
providing structured feedback, and determining winners for ELO ranking.

The agent operates on Documents delivered by output adapters, maintaining clean
separation between the pipeline (produces Documents) and evaluation (consumes Documents).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

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


<<<<<<< HEAD
def _build_gemini_request(prompt: str, system_prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
    """Build Gemini API request payload with structured output."""
    return {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.95,
            "topK": 40,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        },
    }


def _get_response_schema() -> dict[str, Any]:
    """Get JSON schema for structured output from Gemini.

    Uses Pydantic's model_json_schema() to automatically generate
    the schema from ComparisonResult model, ensuring consistency.
    """
    return ComparisonResult.model_json_schema()


def _parse_comparison_response(response_data: dict[str, Any]) -> ComparisonResult:
    """Parse and validate Gemini API response to ComparisonResult.

    Args:
        response_data: Raw JSON response from Gemini API

    Returns:
        Validated ComparisonResult instance

    Raises:
        ValueError: If response structure is invalid or validation fails

    """
    try:
        candidates = response_data.get("candidates", [])
        if not candidates:
            msg = f"No candidates in response: {response_data}"
            raise ValueError(msg)

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            msg = f"No parts in response content: {content}"
            raise ValueError(msg)

        text = parts[0].get("text", "")
        result_data = json.loads(text)

    except (KeyError, IndexError, json.JSONDecodeError) as e:
        msg = f"Failed to parse Gemini response: {e}\nResponse: {response_data}"
        raise ValueError(msg) from e

    # Validate and parse result
    try:
        return ComparisonResult(**result_data)
    except ValidationError as e:
        msg = f"Invalid comparison result from Gemini: {e}\nData: {result_data}"
        raise ValueError(msg) from e


async def _execute_comparison_request(prompt: str, model_name: str, api_key: str) -> dict[str, Any]:
    """Execute API request to Gemini with retry logic.

    Args:
        prompt: Comparison prompt with both posts
        model_name: Gemini model name to use
        api_key: Google API key

    Returns:
        Raw JSON response from API

    Raises:
        httpx.HTTPStatusError: On persistent API errors after retries

    """
    payload = _build_gemini_request(prompt, READER_SYSTEM_PROMPT, _get_response_schema())
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"

    async def _call_api() -> httpx.Response:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                params={"key": api_key},
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )
            response.raise_for_status()
            return response

    response = await call_with_retries(_call_api)
    return response.json()


=======
>>>>>>> origin/refactor/leaking-abstractions-v2
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
<<<<<<< HEAD
    # Get API key from environment
    effective_api_key = api_key or os.environ.get("GOOGLE_API_KEY")
    if not effective_api_key:
=======
    # Ensure API key availability (PydanticAI will pick it up from env if not explicitly passed,
    # but we check here for early failure if completely missing)
    if not api_key and not os.environ.get("GOOGLE_API_KEY"):
>>>>>>> origin/refactor/leaking-abstractions-v2
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
<<<<<<< HEAD
    model_name = model or _DEFAULT_MODEL_NAME

    logger.debug("Comparing posts: %s vs %s", request.post_a_slug, request.post_b_slug)

    # Execute API request with retry logic
    response_data = await _execute_comparison_request(prompt, model_name, effective_api_key)

    # Parse and validate response
    comparison_result = _parse_comparison_response(response_data)
=======
    # Note: PydanticAI models are typically "provider:model", e.g. "google-gla:gemini-flash-latest"
    model_name = model or "google-gla:gemini-flash-latest"

    agent = Agent(model=model_name, result_type=ComparisonResult, system_prompt=READER_SYSTEM_PROMPT)

    logger.debug("Comparing posts: %s vs %s", request.post_a_slug, request.post_b_slug)

    async def _run_agent() -> ComparisonResult:
        result = await agent.run(prompt)
        return result.data

    # Execute with centralized retry policy
    comparison_result = await retry_async(_run_agent, RetryPolicy())
>>>>>>> origin/refactor/leaking-abstractions-v2

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
