"""Mocks for enrichment agents (URL and Media enrichment).

This module provides mock implementations for enrichment operations
to ensure deterministic E2E testing without real API calls.
"""

from pathlib import Path
from typing import Any

from tests.e2e.mocks.llm_responses import (
    FIXTURE_MEDIA_ENRICHMENTS,
    FIXTURE_URL_ENRICHMENTS,
)


def mock_url_enrichment(url: str, **kwargs: Any) -> dict:
    """Mock URL enrichment function.

    Args:
        url: URL to enrich
        **kwargs: Additional arguments (ignored in mock)

    Returns:
        Dictionary with enrichment data
    """
    # Get fixture response or return default
    enrichment = FIXTURE_URL_ENRICHMENTS.get(
        url,
        {
            "title": f"Mock: {url}",
            "description": "Generic enrichment for unknown URL",
            "image": "",
            "domain": url.split("/")[2] if "/" in url else "example.com",
            "content_type": "article",
        },
    )

    # Convert to dict if it's a dataclass
    if hasattr(enrichment, "to_dict"):
        return enrichment.to_dict()
    return enrichment


def mock_media_enrichment(path: str | Path, **kwargs: Any) -> dict:
    """Mock media enrichment function.

    Args:
        path: Path to media file
        **kwargs: Additional arguments (ignored in mock)

    Returns:
        Dictionary with enrichment data
    """
    filename = Path(path).name

    # Get fixture response or return default
    enrichment = FIXTURE_MEDIA_ENRICHMENTS.get(
        filename,
        {
            "alt_text": f"Image: {filename}",
            "detected_objects": ["image"],
            "estimated_topics": ["test"],
            "color_palette": ["#000000"],
            "contains_text": False,
            "text_content": "",
        },
    )

    # Convert to dict if it's a dataclass
    if hasattr(enrichment, "to_dict"):
        return enrichment.to_dict()
    return enrichment


async def async_mock_url_enrichment(url: str, **kwargs: Any) -> dict:
    """Async version of mock_url_enrichment."""
    return mock_url_enrichment(url, **kwargs)


async def async_mock_media_enrichment(path: str | Path, **kwargs: Any) -> dict:
    """Async version of mock_media_enrichment."""
    return mock_media_enrichment(path, **kwargs)
