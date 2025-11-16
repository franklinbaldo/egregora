"""Pydantic AI reader agent for post quality evaluation.

The reader agent simulates human readers performing pairwise post comparisons,
providing structured feedback, and determining winners for ELO ranking.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from egregora.agents.reader.models import PostComparison, ReaderFeedback

if TYPE_CHECKING:
    from egregora.agents.reader.models import EvaluationRequest

logger = logging.getLogger(__name__)


def _is_rate_limit_error(exception: Exception) -> bool:
    """Check if exception is a rate limit error (429 RESOURCE_EXHAUSTED)."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code == 429
    return False


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
    """Get JSON schema for structured output from Gemini."""
    return {
        "type": "object",
        "properties": {
            "winner": {
                "type": "string",
                "description": "Which post won: 'a', 'b', or 'tie'",
                "enum": ["a", "b", "tie"],
            },
            "reasoning": {"type": "string", "description": "Explanation of the choice"},
            "feedback_a": {
                "type": "object",
                "properties": {
                    "comment": {"type": "string", "description": "Natural language feedback about the post"},
                    "star_rating": {
                        "type": "integer",
                        "description": "Star rating from 1-5",
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "engagement_level": {
                        "type": "string",
                        "description": "Predicted engagement: low, medium, or high",
                        "enum": ["low", "medium", "high"],
                    },
                },
                "required": ["comment", "star_rating", "engagement_level"],
            },
            "feedback_b": {
                "type": "object",
                "properties": {
                    "comment": {"type": "string", "description": "Natural language feedback about the post"},
                    "star_rating": {
                        "type": "integer",
                        "description": "Star rating from 1-5",
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "engagement_level": {
                        "type": "string",
                        "description": "Predicted engagement: low, medium, or high",
                        "enum": ["low", "medium", "high"],
                    },
                },
                "required": ["comment", "star_rating", "engagement_level"],
            },
        },
        "required": ["winner", "reasoning", "feedback_a", "feedback_b"],
    }


@retry(
    retry=_is_rate_limit_error,
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def compare_posts(
    request: EvaluationRequest,
    model: str | None = None,
    api_key: str | None = None,
) -> PostComparison:
    """Compare two posts and return structured comparison result.

    Implements exponential backoff retry strategy for rate limit errors (429).
    Retries up to 5 times with wait times: 4s, 8s, 16s, 32s, 60s (max).

    Args:
        request: Evaluation request with post slugs and content
        model: Optional model override (defaults to gemini-flash-latest)
        api_key: Optional API key (defaults to GOOGLE_API_KEY env var)

    Returns:
        PostComparison with winner, reasoning, and feedback for both posts

    Raises:
        httpx.HTTPStatusError: On persistent rate limit or API errors after retries

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
    # Get API key from environment
    api_key = api_key or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
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
    model_name = model or "gemini-flash-latest"

    # Build request payload
    payload = _build_gemini_request(prompt, READER_SYSTEM_PROMPT, _get_response_schema())

    # Make API request with httpx (VCR-compatible)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"

    logger.debug("Comparing posts: %s vs %s", request.post_a_slug, request.post_b_slug)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json=payload,
                params={"key": api_key},
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if _is_rate_limit_error(e):
                logger.warning(
                    "Rate limit hit for %s vs %s, retrying with backoff",
                    request.post_a_slug,
                    request.post_b_slug,
                )
            raise

    # Parse response
    response_data = response.json()

    # Extract the generated content
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
        comparison_result = ComparisonResult(**result_data)
    except ValidationError as e:
        msg = f"Invalid comparison result from Gemini: {e}\nData: {result_data}"
        raise ValueError(msg) from e

    # Convert to PostComparison
    return PostComparison(
        post_a_slug=request.post_a_slug,
        post_b_slug=request.post_b_slug,
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
