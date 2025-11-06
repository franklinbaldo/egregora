"""Author profiling tools for LLM to read and update author profiles."""

import logging
import re
from pathlib import Path
from typing import Annotated, Any

import pyarrow as pa

logger = logging.getLogger(__name__)

# Constants for alias validation
MAX_ALIAS_LENGTH = 40
ASCII_CONTROL_CHARS_THRESHOLD = 32


def read_profile(
    author_uuid: Annotated[str, "The UUID5 pseudonym of the author"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> Annotated[str, "The profile content as markdown, or an empty string if no profile exists"]:
    """Read the current profile for an author.

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
    author_uuid: Annotated[str, "The UUID5 pseudonym of the author"],
    content: Annotated[str, "The profile content in markdown format"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> Annotated[str, "The path to the saved profile file"]:
    """Write or update an author's profile.

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
    if any(suspicious in content.lower() for suspicious in ["phone", "email", "@", "whatsapp", "real name"]):
        logger.warning(f"Profile for {author_uuid} contains suspicious content")

    profile_path.write_text(content, encoding="utf-8")
    logger.info(f"Saved profile for {author_uuid} to {profile_path}")

    return str(profile_path)


def get_active_authors(
    table: Annotated[Any, "The Ibis table with an 'author' column"],
    limit: Annotated[int | None, "An optional limit on the number of authors to return"] = None,
) -> Annotated[list[str], "A list of unique author UUIDs, excluding 'system' and 'egregora'"]:
    """Get list of unique authors from a Table.

    Args:
        table: Ibis Table with 'author' column
        limit: Optional limit on number of authors to return (most active first)

    Returns:
        List of unique author UUIDs (excluding 'system' and 'egregora')

    """
    authors: list[str | None] = []

    try:
        arrow_table = table.select("author").distinct().to_pyarrow()
    except AttributeError:  # pragma: no cover - fallback for non-ibis tables
        result = table.select("author").distinct().execute()
        if hasattr(result, "columns"):
            if "author" in result.columns:
                authors = result["author"].tolist()
            else:  # pragma: no cover - defensive path for misnamed columns
                authors = result.iloc[:, 0].tolist()
        elif hasattr(result, "tolist"):
            authors = list(result.tolist())
        else:  # pragma: no cover - defensive path
            authors = list(result)
    else:
        if arrow_table.num_columns == 0:
            return []
        column = arrow_table.column(0)
        if isinstance(column, pa.ChunkedArray):
            authors = column.to_pylist()
        else:  # pragma: no cover - pyarrow tables always use ChunkedArray
            authors = list(column)

    # Filter out system and enrichment entries
    filtered_authors = [
        author for author in authors if author is not None and author not in ("system", "egregora", "")
    ]

    # Apply limit if specified (return most active authors first)
    if limit is not None and limit > 0:
        # Count messages per author to get most active
        author_counts = {}
        for author in filtered_authors:
            count = table.filter(table.author == author).count().execute()
            author_counts[author] = count

        # Sort by message count descending and take top N
        sorted_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)
        return [author for author, _ in sorted_authors[:limit]]

    return filtered_authors


def _validate_alias(alias: str) -> str | None:
    """Validate and sanitize alias input.

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
    author_uuid: Annotated[str, "The anonymized author UUID"],
    command: Annotated[dict[str, Any], "The command dictionary from the parser"],
    timestamp: Annotated[str, "The timestamp of when the command was issued"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> Annotated[str, "The path to the updated profile"]:
    """Apply an egregora command to an author's profile.

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
        if not isinstance(value, str):
            logger.warning(f"Invalid alias for {author_uuid} (not a string)")
            return str(profile_path)
        validated_value = _validate_alias(value)
        if not validated_value:
            logger.warning(f"Invalid alias for {author_uuid} (rejected)")
            return str(profile_path)

        content = _update_profile_metadata(
            content,
            "Display Preferences",
            "alias",
            f'- Alias: "{validated_value}" (set on {timestamp})\n- Public: true',
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
        content = _update_profile_metadata(content, "User Bio", "bio", f'"{value}"\n\n(Set on {timestamp})')
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
    """Update a metadata section in profile content.

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
                content = content[: first_section.start()] + new_section + content[first_section.start() :]
            else:
                content += new_section
        else:
            content += new_section

    return content


def get_author_display_name(
    author_uuid: Annotated[str, "The anonymized author UUID"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> Annotated[str, "The author's alias if set and public, otherwise their UUID"]:
    """Get display name for an author.

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
    commands: Annotated[list[dict[str, Any]], "A list of command dictionaries from extract_commands()"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> Annotated[int, "The number of commands processed"]:
    """Process a batch of egregora commands.

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


def is_opted_out(
    author_uuid: Annotated[str, "The anonymized author UUID"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> Annotated[bool, "True if the author has opted out, False otherwise"]:
    """Check if an author has opted out of processing.

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


def get_opted_out_authors(
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> Annotated[set[str], "A set of author UUIDs who have opted out"]:
    """Get set of all authors who have opted out.

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
    table: Annotated[Any, "The Ibis table with an 'author' column"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> tuple[
    Annotated[Any, "The filtered table"],
    Annotated[int, "The number of removed messages"],
]:
    """Remove all messages from opted-out authors.

    This should be called EARLY in the pipeline, BEFORE anonymization,
    enrichment, or any processing.

    Args:
        table: Ibis Table with 'author' column
        profiles_dir: Where profiles are stored

    Returns:
        (filtered_table, num_removed_messages)

    """
    if table.count().execute() == 0:
        return table, 0

    # Get opted-out authors
    opted_out = get_opted_out_authors(profiles_dir)

    if not opted_out:
        return table, 0

    logger.info(f"Found {len(opted_out)} opted-out authors")

    # Count messages before filtering
    original_count = table.count().execute()

    # Filter out opted-out authors
    filtered_table = table.filter(~table.author.isin(list(opted_out)))

    removed_count = original_count - filtered_table.count().execute()

    if removed_count > 0:
        logger.warning(f"⚠️  Removed {removed_count} messages from {len(opted_out)} opted-out users")
        for author in opted_out:
            author_msg_count = table.filter(table.author == author).count().execute()
            if author_msg_count > 0:
                logger.warning(f"   - {author}: {author_msg_count} messages removed")

    return filtered_table, removed_count


def update_profile_avatar(  # noqa: PLR0913
    author_uuid: Annotated[str, "The anonymized author UUID"],
    avatar_uuid: Annotated[str, "The UUID of the avatar image"],
    avatar_path: Annotated[Path, "The path to the avatar image"],
    moderation_status: Annotated[str, "The moderation status: approved, questionable, or blocked"],
    moderation_reason: Annotated[str, "The reason for the moderation decision"],
    timestamp: Annotated[str, "The timestamp of when the avatar was set"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> Annotated[str, "The path to the updated profile"]:
    """Update an author's profile with avatar information.

    This should be called after avatar moderation is complete.
    Only approved avatars will be set as active.

    Args:
        author_uuid: The anonymized author UUID
        avatar_uuid: UUID of the avatar image
        avatar_path: Path to the avatar image
        moderation_status: approved, questionable, or blocked
        moderation_reason: Reason for moderation decision
        timestamp: When the avatar was set
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

    # Build avatar section content
    if moderation_status == "approved":
        avatar_content = (
            f"- UUID: {avatar_uuid}\n- Path: {avatar_path}\n- Status: ✅ Approved\n- Set on: {timestamp}"
        )
        logger.info(f"✅ Avatar approved for {author_uuid}")
    elif moderation_status == "questionable":
        avatar_content = (
            f"- UUID: {avatar_uuid}\n"
            f"- Path: {avatar_path}\n"
            f"- Status: ⚠️ Pending Review\n"
            f"- Reason: {moderation_reason}\n"
            f"- Set on: {timestamp}\n"
            f"- Note: This avatar requires manual review before it can be used"
        )
        logger.warning(f"⚠️ Avatar requires review for {author_uuid}: {moderation_reason}")
    else:  # blocked
        avatar_content = (
            f"- UUID: {avatar_uuid}\n"
            f"- Status: ❌ Blocked\n"
            f"- Reason: {moderation_reason}\n"
            f"- Attempted on: {timestamp}\n"
            f"- Note: This avatar was rejected and cannot be used"
        )
        logger.warning(f"❌ Avatar blocked for {author_uuid}: {moderation_reason}")

    # Update profile
    content = _update_profile_metadata(content, "Avatar", "avatar", avatar_content)

    # Save updated profile
    profile_path.write_text(content, encoding="utf-8")
    return str(profile_path)


def remove_profile_avatar(
    author_uuid: Annotated[str, "The anonymized author UUID"],
    timestamp: Annotated[str, "The timestamp of when the avatar was removed"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> Annotated[str, "The path to the updated profile"]:
    """Remove avatar from an author's profile.

    Args:
        author_uuid: The anonymized author UUID
        timestamp: When the avatar was removed
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

    # Update avatar section to show it was removed
    avatar_content = f"- Status: None (removed on {timestamp})"

    content = _update_profile_metadata(content, "Avatar", "avatar", avatar_content)

    # Save updated profile
    profile_path.write_text(content, encoding="utf-8")
    logger.info(f"Removed avatar for {author_uuid}")
    return str(profile_path)


def get_avatar_info(
    author_uuid: Annotated[str, "The anonymized author UUID"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> Annotated[dict | None, "Avatar info dict or None if no avatar"]:
    """Get avatar information from an author's profile.

    Args:
        author_uuid: The anonymized author UUID
        profiles_dir: Where profiles are stored

    Returns:
        Dict with avatar info or None if no avatar:
        {
            'uuid': '...',
            'path': '...',
            'status': 'approved|questionable|blocked',
            'reason': '...',  # if not approved
        }

    """
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profiles_dir / f"{author_uuid}.md"

    if not profile_path.exists():
        return None

    content = profile_path.read_text(encoding="utf-8")

    # Look for Avatar section
    avatar_section_match = re.search(r"## Avatar\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)

    if not avatar_section_match:
        return None

    avatar_section = avatar_section_match.group(1)

    # Parse avatar info
    uuid_match = re.search(r"- UUID:\s*(.+)", avatar_section)
    path_match = re.search(r"- Path:\s*(.+)", avatar_section)
    status_match = re.search(r"- Status:\s*(.+)", avatar_section)
    reason_match = re.search(r"- Reason:\s*(.+)", avatar_section)

    if not uuid_match:
        return None

    info = {
        "uuid": uuid_match.group(1).strip(),
        "path": path_match.group(1).strip() if path_match else None,
        "status": "unknown",
    }

    if status_match:
        status_text = status_match.group(1).strip()
        if "Approved" in status_text or "✅" in status_text:
            info["status"] = "approved"
        elif "Pending" in status_text or "⚠️" in status_text:
            info["status"] = "questionable"
        elif "Blocked" in status_text or "❌" in status_text:
            info["status"] = "blocked"
        elif "None" in status_text or "removed" in status_text:
            return None

    if reason_match:
        info["reason"] = reason_match.group(1).strip()

    return info
