"""Handcrafted LLM response mocks for E2E testing.

These responses are:
1. Deterministic (no randomness, repeatable)
2. Realistic (matched to actual LLM patterns)
3. Fixture-aware (tailored to whatsapp_sample.zip)
4. Minimal (just enough to pass smoke tests)

Each mock is keyed to specific messages in the test fixture.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class URLEnrichmentResponse:
    """Mock response for URL enrichment."""

    title: str
    description: str
    image: str
    domain: str
    content_type: str = "article"

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "title": self.title,
            "description": self.description,
            "image": self.image,
            "domain": self.domain,
            "content_type": self.content_type,
        }


@dataclass
class MediaEnrichmentResponse:
    """Mock response for media enrichment."""

    alt_text: str
    detected_objects: list[str]
    estimated_topics: list[str]
    color_palette: list[str]
    contains_text: bool
    text_content: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "alt_text": self.alt_text,
            "detected_objects": self.detected_objects,
            "estimated_topics": self.estimated_topics,
            "color_palette": self.color_palette,
            "contains_text": self.contains_text,
            "text_content": self.text_content,
        }


@dataclass
class WriterPostResponse:
    """Handcrafted writer agent post response."""

    title: str
    slug: str
    summary: str
    tags: list[str]
    content: str
    authors: list[str]
    date: str = "2025-10-28"

    def to_tool_call(self) -> dict:
        """Convert to tool call format."""
        return {
            "tool_name": "write_post_tool",
            "metadata": {
                "title": self.title,
                "slug": self.slug,
                "summary": self.summary,
                "tags": self.tags,
                "authors": self.authors,
                "date": self.date,
            },
            "content": self.content,
        }


# Pre-constructed responses for known URLs in fixture
FIXTURE_URL_ENRICHMENTS = {
    "https://docs.pydantic.dev": URLEnrichmentResponse(
        title="Pydantic: Data Validation with Python Type Hints",
        description="Pydantic is the most widely used data validation library for Python",
        image="https://pydantic.dev/logo.png",
        domain="pydantic.dev",
        content_type="documentation",
    ),
    "https://example.com/testing": URLEnrichmentResponse(
        title="Testing and Quality Assurance Guide",
        description="A comprehensive guide to testing strategies for AI systems",
        image="https://example.com/testing-og.png",
        domain="example.com",
        content_type="article",
    ),
    "https://medium.com/emergence": URLEnrichmentResponse(
        title="Emergence in Distributed Systems",
        description="How collective behavior emerges from local interactions",
        image="https://example.com/emergence.png",
        domain="medium.com",
        content_type="article",
    ),
}

# Pre-constructed responses for fixture images
FIXTURE_MEDIA_ENRICHMENTS = {
    "IMG-20251028-WA0035.jpg": MediaEnrichmentResponse(
        alt_text="Screenshot of test execution results showing pipeline stages",
        detected_objects=["text", "interface", "chart"],
        estimated_topics=["testing", "automation", "metrics"],
        color_palette=["#2E4053", "#F39C12", "#27AE60"],
        contains_text=True,
        text_content="Test Results: PASS (4/4 stages completed)",
    ),
    "IMG-20251028-WA0036.jpg": MediaEnrichmentResponse(
        alt_text="System architecture diagram showing pipeline flow",
        detected_objects=["diagram", "arrows", "boxes"],
        estimated_topics=["architecture", "dataflow", "system-design"],
        color_palette=["#3498DB", "#E74C3C", "#95A5A6"],
        contains_text=True,
        text_content="Parse → Privacy → Enrich → Generate → Publish",
    ),
    "IMG-20251028-WA0037.jpg": MediaEnrichmentResponse(
        alt_text="Concept map showing relationships between system components",
        detected_objects=["network", "nodes", "connections"],
        estimated_topics=["emergence", "collective-intelligence", "synthesis"],
        color_palette=["#9B59B6", "#1ABC9C", "#F1C40F"],
        contains_text=False,
        text_content="",
    ),
    "IMG-20251028-WA0038.jpg": MediaEnrichmentResponse(
        alt_text="Timeline visualization of message flow",
        detected_objects=["timeline", "bars", "labels"],
        estimated_topics=["timeline", "communication", "patterns"],
        color_palette=["#34495E", "#16A085", "#D35400"],
        contains_text=True,
        text_content="Oct 27-28: 25 messages across 2 authors",
    ),
}

# Golden response from expected_output/posts/...
# This is a minimal version for smoke testing
FIXTURE_WRITER_POST = WriterPostResponse(
    title="Test Pipeline Output",
    slug="test-pipeline-output",
    summary="A test post generated by the E2E test pipeline with mocked LLM responses.",
    tags=["test", "e2e", "pipeline"],
    content="""# Test Pipeline Output

This is a test post generated during E2E testing with mocked LLM responses.

## Purpose

This post validates that the writer agent can:
- Generate structured markdown content
- Use provided metadata correctly
- Integrate with the pipeline flow

## Test Context

The pipeline processed a WhatsApp test fixture and generated this output.
All LLM responses were mocked for deterministic, repeatable testing.
""",
    authors=["test-author-uuid-1", "test-author-uuid-2"],
    date="2025-10-28",
)

# Mock metadata for tracking
MOCK_METADATA = {
    "gemini_model": "gemini-flash-2.0-latest",
    "last_validated": "2025-11-26",
    "based_on_cassette": None,  # No VCR cassettes yet
    "notes": "Initial E2E mocks for pipeline smoke testing",
}
