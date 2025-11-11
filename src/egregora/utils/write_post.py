"""write_post tool: Save blog posts with front matter (CMS-like interface for LLM).

DEPRECATED: This module is being phased out in favor of OutputFormat coordinator pattern.
Use OutputFormat.posts.write() instead for new code.
"""

import datetime
from pathlib import Path
from typing import Any

import yaml

from egregora.utils import safe_path_join, slugify

# Constants
ISO_DATE_LENGTH = 10  # Length of ISO date format (YYYY-MM-DD)


def write_post(content: str, metadata: dict[str, Any], output_dir: Path = Path("output/posts")) -> str:
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
            "date": "2025-01-01",  # Should be YYYY-MM-DD, but handles variations
            "tags": ["AI", "ethics"],
            "summary": "Brief summary",
            "authors": ["a1b2c3d4"],  # anonymized IDs
            "category": "Optional category"
        }

    Returns:
        Path where post was saved

    Raises:
        ValueError: If required metadata is missing

    Note:
        PRIVACY VALIDATION REMOVED: The validate_newsletter_privacy() check was removed
        as part of the adapter pattern refactoring. Privacy strategy shifted from
        write-time validation to prevention at input time. Focus is now on:
        - Anonymization before LLM processing (privacy/anonymizer.py)
        - PII detection at ingestion (privacy/detector.py)
        - Not allowing PII to enter the system in the first place

        If you need PII validation at write time, implement it in your PostStorage
        implementation's write() method.

    """
    required = ["title", "slug", "date"]
    for key in required:
        if key not in metadata:
            msg = f"Missing required metadata: {key}"
            raise ValueError(msg)

    # DEPRECATED: validate_newsletter_privacy(content) removed - see docstring above
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse and clean date to extract YYYY-MM-DD (handles window labels like "2025-03-02 08:01 to 12:49")
    raw_date = metadata["date"]
    date_prefix = _extract_clean_date(raw_date)

    base_slug = slugify(metadata["slug"])
    slug_candidate = base_slug
    filename = f"{date_prefix}-{slug_candidate}.md"
    filepath = safe_path_join(output_dir, filename)
    suffix = 2
    while filepath.exists():
        slug_candidate = f"{base_slug}-{suffix}"
        filename = f"{date_prefix}-{slug_candidate}.md"
        filepath = safe_path_join(output_dir, filename)
        suffix += 1
    front_matter = {}
    front_matter["title"] = metadata["title"]

    # Use cleaned date for front matter
    try:
        front_matter["date"] = datetime.date.fromisoformat(date_prefix)
    except (ValueError, AttributeError):
        front_matter["date"] = date_prefix

    front_matter["slug"] = slug_candidate
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


def _extract_clean_date(date_str: str) -> str:
    """Extract clean YYYY-MM-DD date from various formats.

    Handles:
    - Clean dates: "2025-03-02"
    - ISO timestamps: "2025-03-02T10:30:00"
    - Window labels: "2025-03-02 08:01 to 12:49"
    - Datetimes: "2025-03-02 10:30:45"

    Args:
        date_str: Date string in various formats

    Returns:
        Clean date in YYYY-MM-DD format

    """
    # Remove leading/trailing whitespace
    date_str = date_str.strip()

    # Try to parse as ISO date first (most common)
    try:
        # Handle ISO format (YYYY-MM-DD)
        if len(date_str) == ISO_DATE_LENGTH and date_str[4] == "-" and date_str[7] == "-":
            datetime.date.fromisoformat(date_str)  # Validate
            return date_str
    except (ValueError, AttributeError):
        pass

    # Extract YYYY-MM-DD from longer strings (window labels, timestamps)
    # Pattern: YYYY-MM-DD at the start of the string
    import re

    match = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
    if match:
        clean_date = match.group(1)
        try:
            datetime.date.fromisoformat(clean_date)  # Validate
        except (ValueError, AttributeError):
            pass
        else:
            return clean_date

    # Fallback: return original if we can't parse it
    return date_str
