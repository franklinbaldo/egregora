"""Reader agent comparison helpers.

The production system would call an LLM to compare two posts. For tests and
offline development we provide a deterministic default implementation that can
be patched or overridden easily.
"""

from __future__ import annotations

import logging
from typing import Any

from egregora.agents.reader.models import EvaluationRequest, PostComparison, ReaderFeedback

logger = logging.getLogger(__name__)


def _default_feedback(message: str) -> ReaderFeedback:
    return ReaderFeedback(comment=message, star_rating=3, engagement_level="medium")


async def compare_posts(request: EvaluationRequest, **_: Any) -> PostComparison:
    """Compare two posts.

    The fallback implementation simply returns a tie with neutral feedback. Tests
    patch this coroutine to provide deterministic outcomes without invoking an
    external LLM.
    """

    logger.info("Default compare_posts invoked for %s vs %s", request.post_a_slug, request.post_b_slug)
    return PostComparison(
        post_a_slug=request.post_a_slug,
        post_b_slug=request.post_b_slug,
        winner="tie",
        reasoning="Default comparison used for offline execution.",
        feedback_a=_default_feedback("Balanced content"),
        feedback_b=_default_feedback("Balanced content"),
    )
