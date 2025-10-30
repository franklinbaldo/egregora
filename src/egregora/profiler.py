"""Author profiling tools for LLM to read and update author profiles."""

import logging
import re
from pathlib import Path
from typing import Any

import pyarrow as pa

logger = logging.getLogger(__name__)

# Constants for alias validation
MAX_ALIAS_LENGTH = 40
ASCII_CONTROL_CHARS_THRESHOLD = 32


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


    profile_path.write_text(content, encoding="utf-8")
    logger.info(f"Saved profile for {author_uuid} to {profile_path}")

    return str(profile_path)


def get_active_authors(df: Any) -> list[str]:
    """
    Get list of unique authors from a Table.

    Args:
        df: Ibis Table with 'author' column

    Returns:
        List of unique author UUIDs (excluding 'system' and 'egregora')
    """
    authors_raw: list[str | None] = []

    try:
        arrow_table = df.select("author").distinct().to_pyarrow()
    except AttributeError:  # pragma: no cover - fallback for non-ibis tables
        result = df.select("author").distinct().execute()
        if hasattr(result, "columns"):
            if "author" in result.columns:
                authors_raw = [
                    value if isinstance(value, str) else None
                    for value in result["author"].tolist()
                ]
            else:  # pragma: no cover - defensive path for misnamed columns
                authors_raw = [
                    value if isinstance(value, str) else None
                    for value in result.iloc[:, 0].tolist()
                ]
        elif hasattr(result, "tolist"):
            authors_raw = [
                value if isinstance(value, str) else None for value in result.tolist()
            ]
        else:  # pragma: no cover - defensive path
            authors_raw = [value if isinstance(value, str) else None for value in result]
    else:
        if arrow_table.num_columns == 0:
            return []
        column = arrow_table.column(0)
        if isinstance(column, pa.ChunkedArray):
            values = column.to_pylist()
        else:  # pragma: no cover - pyarrow tables always use ChunkedArray
            values = list(column)
        authors_raw = [value if isinstance(value, str) else None for value in values]

    # Filter out system and enrichment entries
    return [
        author
        for author in authors_raw
        if isinstance(author, str) and author not in {"system", "egregora", ""}
    ]


def _validate_alias(alias: str | None) -> str | None:
    """
    Validate and sanitize alias input.

    Args:
        alias: Raw alias from user command

    Returns:
        Sanitized alias or None if invalid
    """
    if not alias:
        return None

    # Strip whitespace and quotes
    alias = alias.strip().strip("\"'")

    # Length check (1-MAX_ALIAS_LENGTH characters)
    if not (1 <= len(alias) <= MAX_ALIAS_LENGTH):
        logger.warning(f"Alias length invalid: {len(alias)} chars (must be 1-{MAX_ALIAS_LENGTH})")
        return None

    # Escape dangerous characters (code injection, HTML, markdown)
    # Remove control characters (ASCII < ASCII_CONTROL_CHARS_THRESHOLD)
    if any(ord(c) < ASCII_CONTROL_CHARS_THRESHOLD for c in alias):
        logger.warning("Alias contains control characters (rejected)")
        return None

    # Escape HTML special characters
    alias = alias.replace("&", "&amp;")
    alias = alias.replace("<", "&lt;")
    alias = alias.replace(">", "&gt;")
    alias = alias.replace('"', "&quot;")
    alias = alias.replace("'", "&#x27;")

    # Escape backticks (prevent markdown code injection)
    alias = alias.replace("`", "&#96;")

    return alias


def apply_command_to_profile(
    author_uuid: str,
    command: dict,
    timestamp: str,
    profiles_dir: Path = Path("output/profiles"),
) -> str:
    """
    Apply an egregora command to an author's profile.

    Commands update profile metadata (aliases, bio, links, etc).
    These are user-controlled preferences, not LLM-generated content.

    Args:
        author_uuid: The anonymized author UUID
        command: Command dict from parser {'command': 'set', 'target': 'alias', 'value': 'Franklin'}
        timestamp: When the command was issued
        profiles_dir: Where profiles are stored

    Returns:
        Path to updated profile
    """
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profiles_dir / f"{author_uuid}.md"

    # Read existing profile or create new one
    if profile_path.exists():
        content = profile_path.read_text(encoding="utf-8")
    else:
        content = f"# Profile: {author_uuid}\n\n"

    # Apply command
    cmd_type = command["command"]
    target = command["target"]
    value = command.get("value")

    if cmd_type == "set" and target == "alias":
        # Validate and sanitize alias
        value = _validate_alias(value)
        if not value:
            logger.warning(f"Invalid alias for {author_uuid} (rejected)")
            return str(profile_path)

        content = _update_profile_metadata(
            content,
            "Display Preferences",
            "alias",
            f'- Alias: "{value}" (set on {timestamp})\n- Public: true',
        )
        logger.info(f"Set alias for {author_uuid}")  # No PII in logs

    elif cmd_type == "remove" and target == "alias":
        content = _update_profile_metadata(
            content,
            "Display Preferences",
            "alias",
            f"- Alias: None (removed on {timestamp})\n- Public: false",
        )
        logger.info(f"Removed alias for {author_uuid}")

    elif cmd_type == "set" and target == "bio":
        content = _update_profile_metadata(
            content, "User Bio", "bio", f'"{value}"\n\n(Set on {timestamp})'
        )
        logger.info(f"Set bio for {author_uuid}")

    elif cmd_type == "set" and target == "twitter":
        content = _update_profile_metadata(content, "Links", "twitter", f"- Twitter: {value}")
        logger.info(f"Set twitter for {author_uuid}")

    elif cmd_type == "set" and target == "website":
        content = _update_profile_metadata(content, "Links", "website", f"- Website: {value}")
        logger.info(f"Set website for {author_uuid}")

    elif cmd_type == "opt-out":
        content = _update_profile_metadata(
            content,
            "Privacy Preferences",
            "opted-out",
            f"- Status: OPTED OUT (on {timestamp})\n- All messages will be excluded from processing",
        )
        logger.warning(f"⚠️  User {author_uuid} OPTED OUT - all messages will be removed")

    elif cmd_type == "opt-in":
        content = _update_profile_metadata(
            content,
            "Privacy Preferences",
            "opted-out",
            f"- Status: Opted in (on {timestamp})\n- Messages will be included in processing",
        )
        logger.info(f"User {author_uuid} opted back in")

    # Save updated profile
    profile_path.write_text(content, encoding="utf-8")
    return str(profile_path)


def _update_profile_metadata(content: str, section_name: str, key: str, new_value: str) -> str:
    """
    Update a metadata section in profile content.

    Creates section if it doesn't exist. Replaces entire section content
    to ensure idempotence (no duplicate accumulation).

    Args:
        content: Current profile markdown content
        section_name: Section header (e.g., "Display Preferences")
        key: Metadata key (used for logging, not for matching)
        new_value: New content for the section

    Returns:
        Updated profile content
    """
    section_pattern = rf"(## {section_name}\s*\n)(.*?)(?=\n## |\Z)"

    # Check if section exists
    match = re.search(section_pattern, content, re.DOTALL)

    if match:
        # Section exists - replace entire section content
        # This ensures idempotence (no duplicate accumulation)
        updated_section = f"{match.group(1)}{new_value}\n"
        content = content[: match.start()] + updated_section + content[match.end() :]
    else:
        # Section doesn't exist, create it
        new_section = f"\n## {section_name}\n{new_value}\n"
        # Add before any existing sections or at end
        if "##" in content:
            # Insert before first section
            first_section = re.search(r"\n## ", content)
            if first_section:
                content = (
                    content[: first_section.start()]
                    + new_section
                    + content[first_section.start() :]
                )
            else:
                content += new_section
        else:
            content += new_section

    return content


def get_author_display_name(
    author_uuid: str,
    profiles_dir: Path = Path("output/profiles"),
) -> str:
    """
    Get display name for an author.

    Returns alias if set and public, otherwise returns UUID.

    NOTE: This is for RENDERING only. Post content should ALWAYS use UUIDs.
    The alias is already HTML-escaped during storage (_validate_alias),
    so it's safe to use in HTML templates.

    Args:
        author_uuid: The anonymized author UUID
        profiles_dir: Where profiles are stored

    Returns:
        Alias (if set, pre-escaped) or UUID
    """
    profile = read_profile(author_uuid, profiles_dir)

    if not profile:
        return author_uuid

    # Parse alias from Display Preferences section
    # Alias is already HTML-escaped during storage (_validate_alias)
    alias_match = re.search(r'Alias: "([^"]+)".*Public: true', profile, re.DOTALL)
    if alias_match:
        return alias_match.group(1)

    return author_uuid


def process_commands(
    commands: list[dict],
    profiles_dir: Path = Path("output/profiles"),
) -> int:
    """
    Process a batch of egregora commands.

    Updates author profiles based on commands extracted from messages.
    Commands are processed in timestamp order to ensure deterministic results.

    Args:
        commands: List of command dicts from extract_commands()
        profiles_dir: Where to save profiles

    Returns:
        Number of commands processed
    """
    if not commands:
        return 0

    logger.info(f"Processing {len(commands)} egregora commands")

    # Sort commands by timestamp for deterministic processing
    # (multiple commands in same export must be applied in order)
    sorted_commands = sorted(commands, key=lambda c: c["timestamp"])

    for cmd_data in sorted_commands:
        author_uuid = cmd_data["author"]
        timestamp = str(cmd_data["timestamp"])
        command = cmd_data["command"]

        try:
            apply_command_to_profile(author_uuid, command, timestamp, profiles_dir)
        except Exception as e:
            logger.error(f"Failed to process command for {author_uuid}: {e}")

    return len(commands)


def is_opted_out(author_uuid: str, profiles_dir: Path = Path("output/profiles")) -> bool:
    """
    Check if an author has opted out of processing.

    Args:
        author_uuid: The anonymized author UUID
        profiles_dir: Where profiles are stored

    Returns:
        True if opted out, False otherwise
    """
    profile = read_profile(author_uuid, profiles_dir)

    if not profile:
        return False

    # Check for opt-out status in Privacy Preferences
    return "Status: OPTED OUT" in profile


def get_opted_out_authors(profiles_dir: Path = Path("output/profiles")) -> set[str]:
    """
    Get set of all authors who have opted out.

    Scans all profiles to find opted-out users.

    Args:
        profiles_dir: Where profiles are stored

    Returns:
        Set of author UUIDs who have opted out
    """
    if not profiles_dir.exists():
        return set()

    opted_out = set()

    for profile_path in profiles_dir.glob("*.md"):
        author_uuid = profile_path.stem
        if is_opted_out(author_uuid, profiles_dir):
            opted_out.add(author_uuid)

    return opted_out


def filter_opted_out_authors(
    df: Any,
    profiles_dir: Path = Path("output/profiles"),
) -> tuple[Any, int]:
    """
    Remove all messages from opted-out authors.

    This should be called EARLY in the pipeline, BEFORE anonymization,
    enrichment, or any processing.

    Args:
        df: Ibis Table with 'author' column
        profiles_dir: Where profiles are stored

    Returns:
        (filtered_df, num_removed_messages)
    """
    if df.count().execute() == 0:
        return df, 0

    # Get opted-out authors
    opted_out = get_opted_out_authors(profiles_dir)

    if not opted_out:
        return df, 0

    logger.info(f"Found {len(opted_out)} opted-out authors")

    # Count messages before filtering
    original_count = df.count().execute()

    # Filter out opted-out authors
    filtered_df = df.filter(~df.author.isin(list(opted_out)))

    removed_count = original_count - filtered_df.count().execute()

    if removed_count > 0:
        logger.warning(f"⚠️  Removed {removed_count} messages from {len(opted_out)} opted-out users")
        for author in opted_out:
            author_msg_count = df.filter(df.author == author).count().execute()
            if author_msg_count > 0:
                logger.warning(f"   - {author}: {author_msg_count} messages removed")

    return filtered_df, removed_count
