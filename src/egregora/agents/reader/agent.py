"""Pydantic AI reader agent for post quality evaluation.

The reader agent simulates human readers performing pairwise post comparisons,
providing structured feedback, and determining winners for ELO ranking.

The agent operates on Documents delivered by output adapters, maintaining clean
separation between the pipeline (produces Documents) and evaluation (consumes Documents).
"""

from __future__ import annotations

import asyncio
import http
import json
import logging
import os
from typing import TYPE_CHECKING, Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from egregora.agents.reader.models import PostComparison, ReaderFeedback

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from egregora.agents.reader.models import EvaluationRequest

logger = logging.getLogger(__name__)

# Constants for retry logic
_DEFAULT_MAX_RETRIES = 5
_RETRY_WAIT_TIMES = [4, 8, 16, 32, 60]  # Exponential backoff with 60s cap
_DEFAULT_MODEL_NAME = "gemini-flash-latest"


# Retry helper for API calls
async def call_with_retries(
    func: Callable[[], Awaitable[httpx.Response]],
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> httpx.Response:
    """Call async function with exponential backoff retry for rate limits.

    Retries on 429 status code with exponential backoff: 4s, 8s, 16s, 32s, 60s (max).

    Args:
        func: Async function that returns httpx.Response
        max_retries: Maximum number of retries (default: 5)

    Returns:
        Response from successful call

    Raises:
        httpx.HTTPStatusError: On persistent errors after all retries

    """
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except httpx.HTTPStatusError as e:
            if e.response.status_code != http.HTTPStatus.TOO_MANY_REQUESTS or attempt == max_retries:
                raise

            wait_time = _RETRY_WAIT_TIMES[min(attempt, len(_RETRY_WAIT_TIMES) - 1)]
            logger.warning(
                "Rate limit hit (429), retrying in %ds (attempt %d/%d)",
                wait_time,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(wait_time)

    msg = "Unreachable code"
    raise RuntimeError(msg)


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


async def compare_posts(
    request: EvaluationRequest,
    model: str | None = None,
    api_key: str | None = None,
) -> PostComparison:
    r"""Compare two posts and return structured comparison result.

    The reader agent evaluates Documents delivered by output adapters. Each
    EvaluationRequest contains two Document instances with full content and metadata.

    Implements exponential backoff retry strategy for rate limit errors (429).
    Retries up to 5 times with wait times: 4s, 8s, 16s, 32s, 60s (max).

    Args:
        request: Evaluation request with two Document instances
        model: Optional model override (defaults to gemini-flash-latest)
        api_key: Optional API key (defaults to GOOGLE_API_KEY env var)

    Returns:
        PostComparison with winner, reasoning, feedback, and Document references

    Raises:
        httpx.HTTPStatusError: On persistent rate limit or API errors after retries

    Example:
        >>> from egregora.data_primitives import Document, DocumentType
        >>> post_a = Document(
        ...     content="# Intro to Python\n\n...",
        ...     type=DocumentType.POST,
        ...     metadata={"slug": "intro-to-python"}
        ... )
        >>> post_b = Document(
        ...     content="# Advanced Python\n\n...",
        ...     type=DocumentType.POST,
        ...     metadata={"slug": "advanced-python"}
        ... )
        >>> request = EvaluationRequest(post_a=post_a, post_b=post_b)
        >>> comparison = await compare_posts(request)
        >>> print(comparison.winner)  # 'a', 'b', or 'tie'
        >>> print(comparison.post_a.metadata["slug"])  # 'intro-to-python'

    """
    # Get API key from environment
    effective_api_key = api_key or os.environ.get("GOOGLE_API_KEY")
    if not effective_api_key:
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
    model_name = model or _DEFAULT_MODEL_NAME

    logger.debug("Comparing posts: %s vs %s", request.post_a_slug, request.post_b_slug)

    # Execute API request with retry logic
    response_data = await _execute_comparison_request(prompt, model_name, effective_api_key)

    # Parse and validate response
    comparison_result = _parse_comparison_response(response_data)

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
