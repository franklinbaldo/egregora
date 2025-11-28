"""Mocks for enrichment agents (URL and Media enrichment).

This module provides mock implementations for enrichment operations
to ensure deterministic E2E testing without real API calls.
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydantic_ai.usage import RunUsage

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
        path: Path to media file, filename string, or stub object with .name attribute
        **kwargs: Additional arguments (ignored in mock)

    Returns:
        Dictionary with enrichment data
    """
    # Handle different input types (Path, str, or stub objects)
    if hasattr(path, "name") and not isinstance(path, Path):
        # Stub object with .name attribute
        filename = str(path.name) if not isinstance(path.name, str) else path.name
    elif isinstance(path, str | Path):
        filename = Path(path).name
    else:
        # Fallback for unknown types
        filename = str(path)

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


async def async_mock_url_enrichment(url: str, **kwargs: Any) -> tuple[SimpleNamespace, RunUsage]:
    """Async version of mock_url_enrichment.

    Returns:
        Tuple of (EnrichmentOutput-like object, usage_stats)
    """
    enrichment_dict = mock_url_enrichment(url, **kwargs)

    # Create EnrichmentOutput-like object with markdown and slug attributes
    # The enrichment dict contains the enrichment data which becomes the markdown
    enrichment_output = SimpleNamespace(
        slug=enrichment_dict.get("domain", "unknown").replace(".", "-"),
        markdown=f"# {enrichment_dict['title']}\n\n{enrichment_dict.get('description', '')}",
    )
    usage = RunUsage(input_tokens=10, output_tokens=20)
    return enrichment_output, usage


async def async_mock_media_enrichment(path: str | Path, **kwargs: Any) -> tuple[SimpleNamespace, RunUsage]:
    """Async version of mock_media_enrichment.

    Returns:
        Tuple of (EnrichmentOutput-like object, usage_stats)
    """
    enrichment_dict = mock_media_enrichment(path, **kwargs)

    # Create EnrichmentOutput-like object with markdown and slug attributes
    # Extract filename for slug
    if hasattr(path, "name") and not isinstance(path, Path):
        filename = str(path.name) if not isinstance(path.name, str) else path.name
    elif isinstance(path, str | Path):
        filename = Path(path).stem
    else:
        filename = "unknown"

    enrichment_output = SimpleNamespace(
        slug=filename.lower().replace(" ", "-"),
        markdown=enrichment_dict.get("alt_text", ""),
    )
    usage = RunUsage(input_tokens=15, output_tokens=25)
    return enrichment_output, usage
