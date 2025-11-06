"""write_post tool: Save blog posts with front matter (CMS-like interface for LLM)."""

import datetime
from pathlib import Path
from typing import Any

import yaml

from egregora.privacy.detector import validate_newsletter_privacy
from egregora.utils import safe_path_join, slugify


def write_post(
    content: str,
    metadata: dict[str, Any],
    output_dir: Path = Path("output/posts"),
) -> str:
    """Save a blog post with YAML front matter.

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

    output_dir.mkdir(parents=True, exist_ok=True)
    date_prefix = metadata["date"]

    # Sanitize slug FIRST to ensure consistency between filename and front matter
    base_slug = slugify(metadata["slug"])
    slug_candidate = base_slug

    # Ensure path stays within output_dir
    filename = f"{date_prefix}-{slug_candidate}.md"
    filepath = safe_path_join(output_dir, filename)

    # Handle duplicates by appending suffix in lockstep with slug/front matter
    suffix = 2
    while filepath.exists():
        slug_candidate = f"{base_slug}-{suffix}"
        filename = f"{date_prefix}-{slug_candidate}.md"
        filepath = safe_path_join(output_dir, filename)
        suffix += 1

    # Build front matter with the final slug candidate
    front_matter = {}
    front_matter["title"] = metadata["title"]
    # Parse date string to date object so YAML doesn't quote it (Material blog plugin requires unquoted dates)
    try:
        front_matter["date"] = datetime.date.fromisoformat(date_prefix)
    except (ValueError, AttributeError):
        # Fallback to string if parsing fails
        front_matter["date"] = date_prefix
    front_matter["slug"] = slug_candidate  # ✅ Use sanitized slug in front matter

    if "tags" in metadata:
        front_matter["tags"] = metadata["tags"]
    if "summary" in metadata:
        front_matter["summary"] = metadata["summary"]
    if "authors" in metadata:
        front_matter["authors"] = metadata["authors"]
    if "category" in metadata:
        front_matter["category"] = metadata["category"]

    yaml_front = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True)

    full_post = f"---\n{yaml_front}---\n\n{content}"

    filepath.write_text(full_post, encoding="utf-8")

    return str(filepath)
