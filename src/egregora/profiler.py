"""Author profiling tools for LLM to read and update author profiles."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def read_profile(
    author_uuid: str,
    profiles_dir: Path = Path("output/profiles"),
) -> str:
    """
    Read the current profile for an author.

    Args:
        author_uuid: The UUID5 pseudonym of the author
        profiles_dir: Directory where profiles are stored

    Returns:
        The profile content as markdown, or empty string if no profile exists
    """
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profiles_dir / f"{author_uuid}.md"

    if not profile_path.exists():
        logger.info(f"No existing profile for {author_uuid}")
        return ""

    logger.info(f"Reading profile for {author_uuid} from {profile_path}")
    return profile_path.read_text(encoding="utf-8")


def write_profile(
    author_uuid: str,
    content: str,
    profiles_dir: Path = Path("output/profiles"),
) -> str:
    """
    Write or update an author's profile.

    Args:
        author_uuid: The UUID5 pseudonym of the author
        content: The profile content in markdown format
        profiles_dir: Directory where profiles are stored

    Returns:
        Path to the saved profile file
    """
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profiles_dir / f"{author_uuid}.md"

    # Validation: ensure no PII leakage
    if any(suspicious in content.lower() for suspicious in [
        "phone", "email", "@", "whatsapp", "real name"
    ]):
        logger.warning(f"Profile for {author_uuid} contains suspicious content")

    profile_path.write_text(content, encoding="utf-8")
    logger.info(f"Saved profile for {author_uuid} to {profile_path}")

    return str(profile_path)


def get_active_authors(df: Any) -> list[str]:
    """
    Get list of unique authors from a DataFrame.

    Args:
        df: Polars DataFrame with 'author' column

    Returns:
        List of unique author UUIDs (excluding 'system' and 'egregora')
    """
    authors = df.select("author").unique().to_series().to_list()
    # Filter out system and enrichment entries
    return [
        author for author in authors
        if author not in ("system", "egregora", None, "")
    ]
