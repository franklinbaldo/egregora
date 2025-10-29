"""write_post tool: Save blog posts with front matter (CMS-like interface for LLM)."""

from pathlib import Path
from typing import Any

import yaml

from .privacy import validate_newsletter_privacy


def write_post(
    content: str,
    metadata: dict[str, Any],
    output_dir: Path = Path("output/posts"),
) -> str:
    """
    Save a blog post with YAML front matter.

    This is a tool for the LLM to use as a CMS. The LLM decides:
    - How many posts to create (0-N per period)
    - Title, slug, tags, summary, authors
    - Post content

    Args:
        content: Markdown post content
        metadata: {
            "title": "Post Title",
            "slug": "post-slug",
            "date": "2025-01-01",
            "tags": ["AI", "ethics"],
            "summary": "Brief summary",
            "authors": ["a1b2c3d4"],  # anonymized IDs
            "category": "Optional category"
        }

    Returns:
        Path where post was saved

    Raises:
        PrivacyViolationError: If content contains PII (phone numbers, etc)
        ValueError: If required metadata is missing
    """

    required = ["title", "slug", "date"]
    for key in required:
        if key not in metadata:
            raise ValueError(f"Missing required metadata: {key}")

    validate_newsletter_privacy(content)

    front_matter = {
        "title": metadata["title"],
        "date": metadata["date"],
        "slug": metadata["slug"],
        "tags": metadata.get("tags"),
        "summary": metadata.get("summary"),
        "authors": metadata.get("authors"),
        "category": metadata.get("category"),
    }

    yaml_front = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True)

    full_post = f"---\n{yaml_front}---\n\n{content}"

    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{metadata['date']}-{metadata['slug']}.md"
    filepath = output_dir / filename

    filepath.write_text(full_post, encoding="utf-8")

    return str(filepath)
