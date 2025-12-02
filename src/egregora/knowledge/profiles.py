"""Author profiling tools for LLM to read and update author profiles."""

import logging
import re
from pathlib import Path
from typing import Annotated, Any

import ibis.expr.types as ir
import pyarrow as pa  # noqa: TID251

logger = logging.getLogger(__name__)
MAX_ALIAS_LENGTH = 40
ASCII_CONTROL_CHARS_THRESHOLD = 32
YAML_FRONTMATTER_PARTS_COUNT = 3  # YAML front matter splits into 3 parts: ["", content, rest]

# Avatar generation constants
AVATAR_ACCESSORIES = ["Blank", "Kurt", "Prescription01", "Prescription02", "Round", "Sunglasses", "Wayfarers"]
AVATAR_CLOTHES = [
    "BlazerShirt",
    "BlazerSweater",
    "CollarSweater",
    "GraphicShirt",
    "Hoodie",
    "Overall",
    "ShirtCrewNeck",
    "ShirtScoopNeck",
    "ShirtVNeck",
]
AVATAR_EYES = [
    "Close",
    "Cry",
    "Default",
    "Dizzy",
    "EyeRoll",
    "Happy",
    "Hearts",
    "Side",
    "Squint",
    "Surprised",
    "Wink",
    "WinkWacky",
]
AVATAR_EYEBROWS = [
    "Angry",
    "AngryNatural",
    "Default",
    "DefaultNatural",
    "FlatNatural",
    "RaisedExcited",
    "RaisedExcitedNatural",
    "SadConcerned",
    "SadConcernedNatural",
    "UnibrowNatural",
    "UpDown",
    "UpDownNatural",
]
AVATAR_MOUTHS = [
    "Concerned",
    "Default",
    "Disbelief",
    "Eating",
    "Grimace",
    "Sad",
    "ScreamOpen",
    "Serious",
    "Smile",
    "Tongue",
    "Twinkle",
    "Vomit",
]
AVATAR_SKIN_COLORS = ["Tanned", "Yellow", "Pale", "Light", "Brown", "DarkBrown", "Black"]
AVATAR_TOPS = [
    "NoHair",
    "Eyepatch",
    "Hat",
    "Hijab",
    "Turban",
    "WinterHat1",
    "WinterHat2",
    "WinterHat3",
    "WinterHat4",
    "LongHairBigHair",
    "LongHairBob",
    "LongHairBun",
    "LongHairCurly",
    "LongHairCurvy",
    "LongHairDreads",
    "LongHairFrida",
    "LongHairFro",
    "LongHairFroBand",
    "LongHairNotTooLong",
    "LongHairShavedSides",
    "LongHairMiaWallace",
    "LongHairStraight",
    "LongHairStraight2",
    "LongHairStraightStrand",
    "ShortHairDreads01",
    "ShortHairDreads02",
    "ShortHairFrizzle",
    "ShortHairShaggyMullet",
    "ShortHairShortCurly",
    "ShortHairShortFlat",
    "ShortHairShortRound",
    "ShortHairShortWaved",
    "ShortHairSides",
    "ShortHairTheCaesar",
    "ShortHairTheCaesarSidePart",
]
AVATAR_HAIR_COLORS = [
    "Auburn",
    "Black",
    "Blonde",
    "BlondeGolden",
    "Brown",
    "BrownDark",
    "PastelPink",
    "Platinum",
    "Red",
    "SilverGray",
]

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
        logger.info("No existing profile for %s", author_uuid)
        return ""
    logger.info("Reading profile for %s from %s", author_uuid, profile_path)
    return profile_path.read_text(encoding="utf-8")


def write_profile(
    author_uuid: Annotated[str, "The UUID5 pseudonym of the author"],
    content: Annotated[str, "The profile content in markdown format"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> Annotated[str, "The path to the saved profile file"]:
    """Write or update an author's profile with YAML front-matter.

    Args:
        author_uuid: The UUID5 pseudonym of the author
        content: The profile content in markdown format (without front-matter)
        profiles_dir: Directory where profiles are stored

    Returns:
        Path to the saved profile file

    """
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profiles_dir / f"{author_uuid}.md"

    if any(suspicious in content.lower() for suspicious in ["phone", "email", "@", "whatsapp", "real name"]):
        logger.warning("Profile for %s contains suspicious content", author_uuid)

    # Extract metadata from existing profile if it exists
    metadata = _extract_profile_metadata(profile_path) if profile_path.exists() else {}

    # Create front-matter with metadata
    front_matter = {
        "uuid": author_uuid,
        "name": metadata.get("name", author_uuid),  # Default to UUID if no alias set
    }

    # Add optional fields if they exist in metadata
    if "alias" in metadata:
        front_matter["alias"] = metadata["alias"]
    if "avatar" in metadata:
        front_matter["avatar"] = metadata["avatar"]
    if "bio" in metadata:
        front_matter["bio"] = metadata["bio"]
    if "social" in metadata:
        front_matter["social"] = metadata["social"]
    if "commands_used" in metadata:
        front_matter["commands_used"] = metadata["commands_used"]

    # Write profile with front-matter
    import yaml

    yaml_front = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Prepend avatar if available OR use fallback
    profile_body = content
    avatar_url = front_matter.get("avatar")

    if not avatar_url:
        avatar_url = generate_fallback_avatar_url(author_uuid)
        # Save fallback URL to front_matter so it's available for page generation
        front_matter["avatar"] = avatar_url
        yaml_front = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True, sort_keys=False)

    if avatar_url:
        # Use MkDocs macros to render avatar from frontmatter
        # This allows dynamic updates if frontmatter changes
        profile_body = "![Avatar]({{ page.meta.avatar }}){ align=left width=150 }\n\n" + profile_body

    full_profile = f"---\n{yaml_front}---\n\n{profile_body}"
    profile_path.write_text(full_profile, encoding="utf-8")

    logger.info("Saved profile for %s to %s", author_uuid, profile_path)

    # Update .authors.yml for MkDocs blog plugin
    # Also use fallback for authors.yml if needed
    if "avatar" not in front_matter and avatar_url:
        # Create a copy for authors.yml that includes the fallback
        front_matter_for_authors = front_matter.copy()
        front_matter_for_authors["avatar"] = avatar_url
        _update_authors_yml(profiles_dir.parent, author_uuid, front_matter_for_authors)
    else:
        _update_authors_yml(profiles_dir.parent, author_uuid, front_matter)

    return str(profile_path)


def generate_fallback_avatar_url(author_uuid: str) -> str:
    """Generate a deterministic fallback avatar URL using getavataaars.com.

    Args:
        author_uuid: The author's UUID

    Returns:
        A URL to a generated avatar image

    """
    import hashlib

    # Deterministically select options based on UUID hash
    # We use different slices of the hash to pick different attributes
    h = hashlib.sha256(author_uuid.encode()).hexdigest()

    # Helper to pick from options
    def pick(options: list[str], offset: int) -> str:
        idx = int(h[offset : offset + 2], 16) % len(options)
        return options[idx]

    params = [
        f"accessoriesType={pick(AVATAR_ACCESSORIES, 0)}",
        "avatarStyle=Circle",
        f"clotheType={pick(AVATAR_CLOTHES, 2)}",
        f"eyeType={pick(AVATAR_EYES, 4)}",
        f"eyebrowType={pick(AVATAR_EYEBROWS, 6)}",
        "facialHairType=Blank",
        f"hairColor={pick(AVATAR_HAIR_COLORS, 8)}",
        f"mouthType={pick(AVATAR_MOUTHS, 10)}",
        f"skinColor={pick(AVATAR_SKIN_COLORS, 12)}",
        f"topType={pick(AVATAR_TOPS, 14)}",
    ]

    return f"https://getavataaars.com/?{'&'.join(params)}"


def get_active_authors(
    table: Annotated[ir.Table, "The Ibis table with an 'author_uuid' column"],
    limit: Annotated[int | None, "An optional limit on the number of authors to return"] = None,
) -> Annotated[list[str], "A list of unique author UUIDs, excluding 'system' and 'egregora'"]:
    """Get list of unique authors from a Table.

    Args:
        table: Ibis Table with 'author_uuid' column (IR v1 schema)
        limit: Optional limit on number of authors to return (most active first)

    Returns:
        List of unique author UUIDs (excluding 'system' and 'egregora')

    """
    authors: list[str | None] = []
    try:
        # IR v1: use author_uuid column instead of author
        # Cast UUID to string for PyArrow compatibility
        arrow_table = table.select(author_uuid=table.author_uuid.cast(str)).distinct().to_pyarrow()
    except AttributeError:
        result = table.select(author_uuid=table.author_uuid.cast(str)).distinct().execute()
        if hasattr(result, "columns"):
            if "author_uuid" in result.columns:
                authors = result["author_uuid"].tolist()
            else:
                authors = result.iloc[:, 0].tolist()
        elif hasattr(result, "tolist"):
            authors = list(result.tolist())
        else:
            authors = list(result)
    else:
        if arrow_table.num_columns == 0:
            return []
        column = arrow_table.column(0)
        if isinstance(column, pa.ChunkedArray):
            authors = column.to_pylist()
        else:
            authors = list(column)
    filtered_authors = [
        author for author in authors if author is not None and author not in ("system", "egregora", "")
    ]
    if limit is not None and limit > 0:
        author_counts = {}
        for author in filtered_authors:
            # IR v1: use author_uuid column
            count = table.filter(table.author_uuid == author).count().execute()
            author_counts[author] = count
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
    alias = alias.strip().strip("\"'")
    if not 1 <= len(alias) <= MAX_ALIAS_LENGTH:
        logger.warning("Alias length invalid: %s chars (must be 1-%s)", len(alias), MAX_ALIAS_LENGTH)
        return None
    if any(ord(c) < ASCII_CONTROL_CHARS_THRESHOLD for c in alias):
        logger.warning("Alias contains control characters (rejected)")
        return None
    alias = alias.replace("&", "&amp;")
    alias = alias.replace("<", "&lt;")
    alias = alias.replace(">", "&gt;")
    alias = alias.replace('"', "&quot;")
    alias = alias.replace("'", "&#x27;")
    return alias.replace("`", "&#96;")


def apply_command_to_profile(  # noqa: C901
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
    if profile_path.exists():
        content = profile_path.read_text(encoding="utf-8")
    else:
        content = f"# Profile: {author_uuid}\n\n"
    cmd_type = command["command"]
    target = command["target"]
    value = command.get("value")
    if cmd_type == "set" and target == "alias":
        if not isinstance(value, str):
            logger.warning("Invalid alias for %s (not a string)", author_uuid)
            return str(profile_path)
        validated_value = _validate_alias(value)
        if not validated_value:
            logger.warning("Invalid alias for %s (rejected)", author_uuid)
            return str(profile_path)
        content = _update_profile_metadata(
            content,
            "Display Preferences",
            "alias",
            f'- Alias: "{validated_value}" (set on {timestamp})\n- Public: true',
        )
        logger.info("Set alias for %s", author_uuid)
    elif cmd_type == "remove" and target == "alias":
        content = _update_profile_metadata(
            content,
            "Display Preferences",
            "alias",
            f"- Alias: None (removed on {timestamp})\n- Public: false",
        )
        logger.info("Removed alias for %s", author_uuid)
    elif cmd_type == "set" and target == "bio":
        content = _update_profile_metadata(content, "User Bio", "bio", f'"{value}"\n\n(Set on {timestamp})')
        logger.info("Set bio for %s", author_uuid)
    elif cmd_type == "set" and target == "twitter":
        content = _update_profile_metadata(content, "Links", "twitter", f"- Twitter: {value}")
        logger.info("Set twitter for %s", author_uuid)
    elif cmd_type == "set" and target == "website":
        content = _update_profile_metadata(content, "Links", "website", f"- Website: {value}")
        logger.info("Set website for %s", author_uuid)
    elif cmd_type == "opt-out":
        content = _update_profile_metadata(
            content,
            "Privacy Preferences",
            "opted-out",
            f"- Status: OPTED OUT (on {timestamp})\n- All messages will be excluded from processing",
        )
        logger.warning("⚠️  User %s OPTED OUT - all messages will be removed", author_uuid)
    elif cmd_type == "opt-in":
        content = _update_profile_metadata(
            content,
            "Privacy Preferences",
            "opted-out",
            f"- Status: Opted in (on {timestamp})\n- Messages will be included in processing",
        )
        logger.info("User %s opted back in", author_uuid)
    profile_path.write_text(content, encoding="utf-8")
    return str(profile_path)


def _update_profile_metadata(content: str, section_name: str, _key: str, new_value: str) -> str:
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
    section_pattern = f"(## {section_name}\\s*\\n)(.*?)(?=\\n## |\\Z)"
    match = re.search(section_pattern, content, re.DOTALL)
    if match:
        updated_section = f"{match.group(1)}{new_value}\n"
        content = content[: match.start()] + updated_section + content[match.end() :]
    else:
        new_section = f"\n## {section_name}\n{new_value}\n"
        if "##" in content:
            first_section = re.search("\\n## ", content)
            if first_section:
                content = content[: first_section.start()] + new_section + content[first_section.start() :]
            else:
                content += new_section
        else:
            content += new_section
    return content


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
    logger.info("Processing %s egregora commands", len(commands))
    sorted_commands = sorted(commands, key=lambda c: c["timestamp"])
    for cmd_data in sorted_commands:
        author_uuid = cmd_data["author"]
        timestamp = str(cmd_data["timestamp"])
        command = cmd_data["command"]
        try:
            apply_command_to_profile(author_uuid, command, timestamp, profiles_dir)
        except Exception:
            logger.exception("Failed to process command for %s", author_uuid)
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
    table: Annotated[ir.Table, "The Ibis table with an 'author_uuid' column"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> tuple[Annotated[ir.Table, "The filtered table"], Annotated[int, "The number of removed messages"]]:
    """Remove all messages from opted-out authors.

    This should be called EARLY in the pipeline, BEFORE anonymization,
    enrichment, or any processing.

    Args:
        table: Ibis Table with 'author_uuid' column
        profiles_dir: Where profiles are stored

    Returns:
        (filtered_table, num_removed_messages)

    """
    if table.count().execute() == 0:
        return (table, 0)
    opted_out = get_opted_out_authors(profiles_dir)
    if not opted_out:
        return (table, 0)
    logger.info("Found %s opted-out authors", len(opted_out))
    original_count = table.count().execute()
    filtered_table = table.filter(~table.author_uuid.isin(list(opted_out)))
    removed_count = original_count - filtered_table.count().execute()
    if removed_count > 0:
        logger.warning("⚠️  Removed %s messages from %s opted-out users", removed_count, len(opted_out))
        for author in opted_out:
            author_msg_count = table.filter(table.author_uuid == author).count().execute()
            if author_msg_count > 0:
                logger.warning("   - %s: %s messages removed", author, author_msg_count)
    return (filtered_table, removed_count)


def update_profile_avatar(
    author_uuid: Annotated[str, "The anonymized author UUID"],
    avatar_url: Annotated[str, "The URL of the avatar image"],
    timestamp: Annotated[str, "The timestamp of when the avatar was set"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> Annotated[str, "The path to the updated profile"]:
    """Update an author's profile with avatar URL - simplified.

    Stores just the URL. The image is downloaded to media/images/ like any other media.
    When avatar changes, we just update the URL - old media file stays where it is.

    Args:
        author_uuid: The anonymized author UUID
        avatar_url: URL of the avatar image
        timestamp: When the avatar was set
        profiles_dir: Where profiles are stored

    Returns:
        Path to updated profile

    """
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profiles_dir / f"{author_uuid}.md"
    if profile_path.exists():
        content = profile_path.read_text(encoding="utf-8")
    else:
        content = f"# Profile: {author_uuid}\n\n"

    avatar_content = f"- URL: {avatar_url}\n- Set on: {timestamp}"
    logger.info("✅ Avatar set for %s: %s", author_uuid, avatar_url)

    content = _update_profile_metadata(content, "Avatar", "avatar", avatar_content)
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
    if profile_path.exists():
        content = profile_path.read_text(encoding="utf-8")
    else:
        content = f"# Profile: {author_uuid}\n\n"
    avatar_content = f"- Status: None (removed on {timestamp})"
    content = _update_profile_metadata(content, "Avatar", "avatar", avatar_content)
    profile_path.write_text(content, encoding="utf-8")
    logger.info("Removed avatar for %s", author_uuid)
    return str(profile_path)


def _extract_profile_metadata(profile_path: Path) -> dict[str, Any]:  # noqa: C901
    """Extract metadata from an existing profile file.

    Reads YAML front-matter and profile sections to build metadata dict.

    Args:
        profile_path: Path to profile markdown file

    Returns:
        Dictionary with profile metadata (alias, avatar, bio, social, commands_used)

    """
    if not profile_path.exists():
        return {}

    import yaml

    content = profile_path.read_text(encoding="utf-8")
    metadata: dict[str, Any] = {}

    # Try to parse YAML front-matter first
    if content.startswith("---"):
        try:
            # Extract YAML between --- delimiters
            parts = content.split("---", 2)
            if len(parts) >= YAML_FRONTMATTER_PARTS_COUNT:
                front_matter = yaml.safe_load(parts[1])
                if isinstance(front_matter, dict):
                    metadata.update(front_matter)
        except yaml.YAMLError:
            pass

    # Extract metadata from profile sections (legacy format)
    alias_match = re.search('Alias: "([^"]+)".*Public: true', content, re.DOTALL)
    if alias_match and "alias" not in metadata:
        metadata["alias"] = alias_match.group(1)
        metadata["name"] = alias_match.group(1)  # Use alias as name

    avatar_match = re.search("- URL:\\s*(.+)", content)
    if avatar_match and "avatar" not in metadata:
        metadata["avatar"] = avatar_match.group(1).strip()

    bio_match = re.search('## User Bio\\s*\\n"([^"]+)"', content)
    if bio_match and "bio" not in metadata:
        metadata["bio"] = bio_match.group(1)

    # Extract social links
    social = {}
    twitter_match = re.search("- Twitter:\\s*(.+)", content)
    if twitter_match:
        social["twitter"] = twitter_match.group(1).strip()

    website_match = re.search("- Website:\\s*(.+)", content)
    if website_match:
        social["website"] = website_match.group(1).strip()

    if social and "social" not in metadata:
        metadata["social"] = social

    return metadata


def _update_authors_yml(site_root: Path, author_uuid: str, front_matter: dict[str, Any]) -> None:
    """Update or create .authors.yml for MkDocs blog plugin.

    Args:
        site_root: Site root directory (profiles parent)
        author_uuid: Author UUID
        front_matter: Profile front-matter dict

    """
    import yaml

    authors_yml_path = site_root / ".authors.yml"

    # Load existing .authors.yml or create new
    if authors_yml_path.exists():
        try:
            with authors_yml_path.open("r", encoding="utf-8") as f:
                authors = yaml.safe_load(f) or {}
        except yaml.YAMLError:
            logger.warning("Failed to parse .authors.yml, creating new file")
            authors = {}
    else:
        authors = {}

    # Build author entry
    author_entry: dict[str, Any] = {}

    # Name: use alias if available, otherwise UUID
    author_entry["name"] = front_matter.get("alias", front_matter.get("name", author_uuid))

    # Description: use bio if available
    if "bio" in front_matter:
        author_entry["description"] = front_matter["bio"]

    # Avatar: use avatar URL if available
    if "avatar" in front_matter:
        author_entry["avatar"] = front_matter["avatar"]

    # Social links
    if "social" in front_matter:
        author_entry.update(dict(front_matter["social"].items()))

    # Update authors dict
    authors[author_uuid] = author_entry

    # Write back to .authors.yml
    try:
        with authors_yml_path.open("w", encoding="utf-8") as f:
            yaml.dump(authors, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info("Updated .authors.yml with %s", author_uuid)
    except (OSError, yaml.YAMLError) as e:
        logger.warning("Failed to write .authors.yml: %s", e)
