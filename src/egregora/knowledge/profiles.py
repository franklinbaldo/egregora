"""Author profiling tools for LLM to read and update author profiles.

## Two Profile Systems Overview

Egregora has two distinct but complementary profile systems:

### 1. Author Self-Service Profiles (this module)
- Location: `output/profiles/{slug}.md` (formerly `{author_uuid}.md`)
- Purpose: Store author metadata and preferences (aliases, bios, avatars)
- Created by: User commands (/egregora set alias, set bio, etc.)
- Format: Markdown files with YAML frontmatter
- Key function: `write_profile()`
- **IMPORTANT**: These files include `subject` metadata in their frontmatter

### 2. Egregora-Generated Profile Posts (agents/profile/generator.py)
- Location: `docs/posts/profiles/{author_uuid}/{slug}.md` (via output adapters)
- Purpose: LLM-generated analytical content ABOUT authors
- Created by: Profile generation agent analyzing message history
- Format: Document objects that go through the output adapter pipeline
- Key function: `generate_profile_posts()`
- **CRITICAL**: These Documents MUST include `subject: author_uuid` in metadata

## Integration
- Both systems use `subject` metadata to identify the profile subject
- Self-service profiles are read by the LLM when generating profile posts
- Generated profile posts route to author-specific directories via `subject` metadata
- The `.authors.yml` file is synced from self-service profiles for MkDocs integration

## Routing Requirement
ALL profile Documents (type=DocumentType.PROFILE) MUST include `subject` metadata
to ensure they route to `/posts/profiles/{author_uuid}/` instead of `/posts/`.
This is validated by `validate_profile_document()` in orchestration/persistence.py.
"""

import contextlib
import hashlib
import html
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any

import frontmatter
import ibis
import ibis.common.exceptions
import ibis.expr.types as ir
import yaml

from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.profile_cache import get_opted_out_authors_from_db
from egregora.knowledge.exceptions import (
    AuthorExtractionError,
    AuthorsFileLoadError,
    AuthorsFileParseError,
    AuthorsFileSaveError,
    InvalidAliasError,
    ProfileError,
    ProfileNotFoundError,
    ProfileParseError,
)

logger = logging.getLogger(__name__)
MAX_ALIAS_LENGTH = 40
ASCII_CONTROL_CHARS_THRESHOLD = 32
YAML_FRONTMATTER_PARTS_COUNT = 3  # YAML front matter splits into 3 parts: ["", content, rest]
PROFILE_DATE_REGEX = re.compile(r"(\d{4}-\d{2}-\d{2})")
# Fast author extraction regex for performance-critical bulk operations
_AUTHORS_LIST_REGEX = re.compile(r"^authors:\s*\n((?:\s*-\s+.+\n?)+)", re.MULTILINE)
_AUTHORS_SINGLE_REGEX = re.compile(r"^authors:\s*(.+)$", re.MULTILINE)


def _get_uuid_from_profile(profile_path: Path) -> str:
    """Extract UUID from profile frontmatter."""
    if not profile_path.exists():
        msg = f"Profile not found at {profile_path}"
        raise ProfileNotFoundError(msg, path=str(profile_path))
    try:
        content = profile_path.read_text(encoding="utf-8")
        metadata = _parse_frontmatter(content)
        for key in ("uuid", "subject", "author_uuid"):
            if key in metadata:
                return str(metadata[key])

        # Fallback for legacy files where filename IS the uuid
        stem = profile_path.stem
        # Basic heuristic: UUID is 36 chars (with dashes) or 32 (hex)
        if len(stem) in (32, 36) and all(c in "0123456789abcdefABCDEF-" for c in stem):
            return stem
    except (OSError, UnicodeError, ValueError, TypeError) as e:
        msg = f"Failed to parse profile {profile_path}: {e}"
        raise ProfileParseError(msg, path=str(profile_path)) from e
    msg = f"Could not extract UUID from {profile_path}"
    raise ProfileParseError(msg, path=str(profile_path))


def _find_profile_path(
    author_uuid: str,
    profiles_dir: Path,
) -> Path:
    """Find profile file for a given UUID, scanning directory if needed."""
    # Fast path: check if {uuid}/index.md exists (new structure)
    index_path = profiles_dir / author_uuid / "index.md"
    if index_path.exists():
        return index_path

    # Check potential legacy flat file (by UUID)
    legacy_path = profiles_dir / f"{author_uuid}.md"
    if legacy_path.exists():
        return legacy_path

    # Scan directory for legacy slug-based files
    if not profiles_dir.exists():
        msg = f"Profiles directory not found for {author_uuid}"
        raise ProfileNotFoundError(msg, author_uuid=author_uuid)

    for path in profiles_dir.glob("*.md"):
        if path.name == "index.md":
            continue
        try:
            if _get_uuid_from_profile(path) == author_uuid:
                return path
        except ProfileError:
            # Ignore malformed profiles during search
            continue

    msg = f"No profile found for author {author_uuid}"
    raise ProfileNotFoundError(msg, author_uuid=author_uuid)


def _determine_profile_path(
    author_uuid: str,
    metadata: dict[str, Any],
    profiles_dir: Path,
    current_path: Path | None = None,
) -> Path:
    """Determine the correct filename for a profile based on alias/name."""
    # Always use {author_uuid}/index.md for the static profile
    # This separates static metadata from dynamic posts in the same folder
    author_dir = profiles_dir / author_uuid
    author_dir.mkdir(parents=True, exist_ok=True)
    return author_dir / "index.md"


def read_profile(
    author_uuid: Annotated[str, "The UUID5 pseudonym of the author"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
) -> Annotated[str, "The profile content as markdown"]:
    """Read the current profile for an author.

    Args:
        author_uuid: The UUID5 pseudonym of the author
        profiles_dir: Directory where profiles are stored

    Returns:
        The profile content as markdown

    Raises:
        ProfileNotFoundError: If no profile exists for the given author.

    """
    profiles_dir.mkdir(parents=True, exist_ok=True)
    try:
        profile_path = _find_profile_path(author_uuid, profiles_dir)
        logger.info("Reading profile for %s from %s", author_uuid, profile_path)
        return profile_path.read_text(encoding="utf-8")
    except ProfileNotFoundError:
        logger.info("No existing profile for %s", author_uuid)
        return ""


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

    # Find existing file to preserve identity/handle renames
    try:
        existing_path = _find_profile_path(author_uuid, profiles_dir)
        metadata = _extract_profile_metadata(existing_path)
    except ProfileNotFoundError:
        existing_path = None
        metadata = {}

    if any(suspicious in content.lower() for suspicious in ["phone", "email", "@", "whatsapp", "real name"]):
        logger.warning("Profile for %s contains suspicious content", author_uuid)

    # Create front-matter with metadata
    front_matter = {
        "uuid": author_uuid,
        "subject": author_uuid,
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

    # Determine filename
    target_path = _determine_profile_path(author_uuid, front_matter, profiles_dir, current_path=existing_path)

    target_path.write_text(full_profile, encoding="utf-8")
    logger.info("Saved profile for %s to %s", author_uuid, target_path)

    # Clean up old file if renamed
    if existing_path and existing_path.resolve() != target_path.resolve():
        try:
            existing_path.unlink()
            logger.info("Renamed profile from %s to %s", existing_path.name, target_path.name)
        except OSError as e:
            logger.warning("Failed to delete old profile %s: %s", existing_path, e)

    # Update .authors.yml
    if "avatar" not in front_matter and avatar_url:
        front_matter_for_authors = front_matter.copy()
        front_matter_for_authors["avatar"] = avatar_url
        _update_authors_yml(
            profiles_dir.parent, author_uuid, front_matter_for_authors, filename=target_path.name
        )
    else:
        _update_authors_yml(profiles_dir.parent, author_uuid, front_matter, filename=target_path.name)

    return str(target_path)


# Cache for avatar options to avoid repeated file I/O
_AVATAR_OPTIONS_CACHE: dict[str, list[str]] | None = None


def _load_avatar_options() -> dict[str, list[str]]:
    """Load avatar options from YAML file."""
    global _AVATAR_OPTIONS_CACHE
    if _AVATAR_OPTIONS_CACHE is not None:
        return _AVATAR_OPTIONS_CACHE

    try:
        # Use importlib.resources to access package data reliably
        from importlib import resources

        # The path should be relative to the 'egregora' package
        # Assuming 'resources' is a subdirectory of 'egregora'
        with resources.files("egregora").joinpath("resources/avatar_options.yml").open("r") as f:
            options = yaml.safe_load(f)
            if not isinstance(options, dict):
                raise TypeError("Avatar options YAML must be a dictionary.")
            _AVATAR_OPTIONS_CACHE = options
            return options
    except (ModuleNotFoundError, FileNotFoundError, yaml.YAMLError, TypeError) as e:
        logger.exception("Failed to load avatar_options.yml, avatar generation may fail: %s", e)
        # Return an empty dict on failure to prevent crashes
        return {}


def generate_fallback_avatar_url(author_uuid: str) -> str:
    """Generate a deterministic fallback avatar URL using avataaars.io.

    Args:
        author_uuid: The author's UUID

    Returns:
        A URL to a generated avatar image

    """
    options = _load_avatar_options()
    if not options:
        return ""  # Return empty if options failed to load

    # Deterministically select options based on UUID hash
    h = hashlib.sha256(author_uuid.encode()).hexdigest()

    # Helper to pick from options
    def pick(key: str, offset: int) -> str:
        choices = options.get(key, [""])
        if not choices:
            return ""
        idx = int(h[offset : offset + 2], 16) % len(choices)
        return choices[idx]

    params = [
        f"accessoriesType={pick('accessories', 0)}",
        "avatarStyle=Circle",
        f"clotheType={pick('clothes', 2)}",
        f"eyeType={pick('eyes', 4)}",
        f"eyebrowType={pick('eyebrows', 6)}",
        "facialHairType=Blank",
        f"hairColor={pick('hair_colors', 8)}",
        f"mouthType={pick('mouths', 10)}",
        f"skinColor={pick('skin_colors', 12)}",
        f"topType={pick('tops', 14)}",
    ]

    return f"https://avataaars.io/?{'&'.join(params)}"


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
        authors = arrow_table.column(0).to_pylist()
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


def _validate_alias(alias: str) -> str:
    """Validate and sanitize alias input.

    Args:
        alias: Raw alias from user command

    Returns:
        Sanitized alias

    Raises:
        InvalidAliasError: If the alias is invalid.

    """
    if not alias:
        raise InvalidAliasError("Alias cannot be empty.", alias=alias)
    alias = alias.strip().strip("\"'")
    if not alias:
        raise InvalidAliasError("Alias cannot be empty.", alias=alias)
    if not 1 <= len(alias) <= MAX_ALIAS_LENGTH:
        msg = f"Alias length invalid: {len(alias)} chars (must be 1-{MAX_ALIAS_LENGTH})"
        raise InvalidAliasError(msg, alias=alias)
    if any(ord(c) < ASCII_CONTROL_CHARS_THRESHOLD for c in alias):
        raise InvalidAliasError("Alias contains control characters.", alias=alias)
    alias = alias.replace("&", "&amp;")
    alias = alias.replace("<", "&lt;")
    alias = alias.replace(">", "&gt;")
    alias = alias.replace('"', "&quot;")
    alias = alias.replace("'", "&#x27;")
    return alias.replace("`", "&#96;")


@dataclass
class CommandContext:
    """Context for command handling."""

    author_uuid: str
    timestamp: str
    content: str


def _handle_alias_command(
    cmd_type: str,
    target: str,
    value: Any,
    context: CommandContext,
) -> str:
    """Handle set/remove alias commands."""
    if cmd_type == "set" and target == "alias":
        if not isinstance(value, str):
            logger.warning("Invalid alias for %s (not a string)", context.author_uuid)
            return context.content
        try:
            validated_value = _validate_alias(value)
            content = _update_profile_metadata(
                context.content,
                "Display Preferences",
                "alias",
                f'- Alias: "{validated_value}" (set on {context.timestamp})\n- Public: true',
            )
            logger.info("Set alias for %s", context.author_uuid)
        except InvalidAliasError as e:
            logger.warning("Invalid alias for %s (rejected): %s", context.author_uuid, e)
            return context.content
    elif cmd_type == "remove" and target == "alias":
        content = _update_profile_metadata(
            context.content,
            "Display Preferences",
            "alias",
            f"- Alias: None (removed on {context.timestamp})\n- Public: false",
        )
        logger.info("Removed alias for %s", context.author_uuid)
    else:
        content = context.content
    return content


def _handle_simple_set_command(
    cmd_type: str,
    target: str,
    value: Any,
    context: CommandContext,
) -> str:
    """Handle simple set commands (bio, twitter, website)."""
    if cmd_type != "set":
        return context.content

    content = context.content
    if target == "bio":
        content = _update_profile_metadata(
            content, "User Bio", "bio", f'"{value}"\n\n(Set on {context.timestamp})'
        )
        logger.info("Set bio for %s", context.author_uuid)
    elif target == "twitter":
        content = _update_profile_metadata(content, "Links", "twitter", f"- Twitter: {value}")
        logger.info("Set twitter for %s", context.author_uuid)
    elif target == "website":
        content = _update_profile_metadata(content, "Links", "website", f"- Website: {value}")
        logger.info("Set website for %s", context.author_uuid)
    return content


def _handle_privacy_command(
    cmd_type: str,
    author_uuid: str,
    timestamp: str,
    content: str,
) -> str:
    """Handle opt-in/opt-out privacy commands."""
    if cmd_type == "opt-out":
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
    return content


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

    # Locate existing profile using flexible lookup
    try:
        profile_path = _find_profile_path(author_uuid, profiles_dir)
        content = profile_path.read_text(encoding="utf-8")
    except ProfileNotFoundError:
        # Create new profile with required frontmatter
        profile_path = None
        front_matter = {"uuid": author_uuid, "subject": author_uuid}
        content = f"---\n{yaml.dump(front_matter)}---\n\n# Profile: {author_uuid}\n\n"

    cmd_type = command["command"]
    target = command["target"]
    value = command.get("value")

    # Apply transformations pipeline
    ctx = CommandContext(author_uuid=author_uuid, timestamp=timestamp, content=content)
    content = _handle_alias_command(cmd_type, target, value, ctx)
    ctx.content = content
    content = _handle_simple_set_command(cmd_type, target, value, ctx)
    content = _handle_privacy_command(cmd_type, author_uuid, timestamp, content)

    # Now decide where to save it
    # We must extract metadata from the NEW content to know if alias changed
    metadata = _parse_frontmatter(content)
    # Also parse legacy sections (like ## Display Preferences) to get alias
    _extract_legacy_metadata(content, metadata)

    target_path = _determine_profile_path(author_uuid, metadata, profiles_dir, current_path=profile_path)

    target_path.write_text(content, encoding="utf-8")

    # Rename/Cleanup
    if profile_path and profile_path.resolve() != target_path.resolve():
        try:
            profile_path.unlink()
            logger.info("Renamed profile from %s to %s", profile_path.name, target_path.name)
        except OSError:
            pass

    # Update .authors.yml
    _update_authors_yml(profiles_dir.parent, author_uuid, metadata, filename=target_path.name)

    return str(target_path)


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
    try:
        profile = read_profile(author_uuid, profiles_dir)
        return "Status: OPTED OUT" in profile
    except ProfileNotFoundError:
        return False


def get_opted_out_authors(
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
    storage: DuckDBStorageManager | None = None,
) -> Annotated[set[str], "A set of author UUIDs who have opted out"]:
    """Get set of all authors who have opted out.

    Reads from database cache if available, eliminating file I/O bottleneck.
    Falls back to file-based scanning if storage is not provided.

    Args:
        profiles_dir: Where profiles are stored
        storage: DuckDBStorageManager instance for database access (optional)

    Returns:
        Set of author UUIDs who have opted out

    """
    # Use database cache if available
    if storage is not None:
        try:
            return get_opted_out_authors_from_db(storage)
        except ibis.common.exceptions.IbisError as e:
            logger.warning("Failed to read opted-out authors from DB, falling back to files: %s", e)
            # Fall through to file-based scanning

    # Fallback to file-based scanning
    if not profiles_dir.exists():
        return set()
    opted_out = set()
    for profile_path in profiles_dir.rglob("*.md"):
        if profile_path.name == "index.md" and profile_path.parent == profiles_dir:
            continue
        try:
            author_uuid = _get_uuid_from_profile(profile_path)
            if author_uuid and is_opted_out(author_uuid, profiles_dir):
                opted_out.add(author_uuid)
        except ProfileError as e:
            logger.warning("Skipping malformed profile %s: %s", profile_path, e)
            continue
    return opted_out


def filter_opted_out_authors(
    table: Annotated[ir.Table, "The Ibis table with an 'author_uuid' column"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"] = Path("output/profiles"),
    storage: DuckDBStorageManager | None = None,
) -> tuple[Annotated[ir.Table, "The filtered table"], Annotated[int, "The number of removed messages"]]:
    """Remove all messages from opted-out authors.

    This should be called EARLY in the pipeline, BEFORE anonymization,
    enrichment, or any processing.

    Args:
        table: Ibis Table with 'author_uuid' column
        profiles_dir: Where profiles are stored
        storage: DuckDBStorageManager instance for database access (optional)

    Returns:
        (filtered_table, num_removed_messages)

    """
    if table.count().execute() == 0:
        return (table, 0)
    opted_out = get_opted_out_authors(profiles_dir, storage=storage)
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
    try:
        profile_path = _find_profile_path(author_uuid, profiles_dir)
        content = profile_path.read_text(encoding="utf-8")
    except ProfileNotFoundError:
        profile_path = None
        # Create new
        front_matter = {"uuid": author_uuid, "subject": author_uuid}
        content = f"---\n{yaml.dump(front_matter)}---\n\n# Profile: {author_uuid}\n\n"

    avatar_content = f"- URL: {avatar_url}\n- Set on: {timestamp}"
    logger.info("✅ Avatar set for %s: %s", author_uuid, avatar_url)

    content = _update_profile_metadata(content, "Avatar", "avatar", avatar_content)

    # Check if we need to rename (metadata logic relies on content having the info)
    # But update_profile_avatar only changes content
    # If filename is uuid, it stays uuid. If alias is set, it might stay slug.
    # We should re-eval filename just in case
    metadata = _parse_frontmatter(content)
    _extract_legacy_metadata(content, metadata)

    target_path = _determine_profile_path(author_uuid, metadata, profiles_dir, current_path=profile_path)

    target_path.write_text(content, encoding="utf-8")

    if profile_path and profile_path.resolve() != target_path.resolve():
        with contextlib.suppress(OSError):
            profile_path.unlink()

    # Update .authors.yml
    _update_authors_yml(profiles_dir.parent, author_uuid, metadata, filename=target_path.name)

    return str(target_path)


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
    try:
        profile_path = _find_profile_path(author_uuid, profiles_dir)
        content = profile_path.read_text(encoding="utf-8")
    except ProfileNotFoundError:
        profile_path = None
        # Create new
        front_matter = {"uuid": author_uuid, "subject": author_uuid}
        content = f"---\n{yaml.dump(front_matter)}---\n\n# Profile: {author_uuid}\n\n"

    avatar_content = f"- Status: None (removed on {timestamp})"
    content = _update_profile_metadata(content, "Avatar", "avatar", avatar_content)

    # Save
    metadata = _extract_profile_metadata(profile_path) if profile_path else {}
    target_path = _determine_profile_path(author_uuid, metadata, profiles_dir, current_path=profile_path)
    target_path.write_text(content, encoding="utf-8")

    if profile_path and profile_path.resolve() != target_path.resolve():
        with contextlib.suppress(OSError):
            profile_path.unlink()

    # Update .authors.yml
    _update_authors_yml(profiles_dir.parent, author_uuid, metadata, filename=target_path.name)

    logger.info("Removed avatar for %s", author_uuid)
    return str(target_path)


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Extract YAML front-matter from content."""
    if content.startswith("---"):
        try:
            parts = content.split("---", 2)
            if len(parts) >= YAML_FRONTMATTER_PARTS_COUNT:
                front_matter = yaml.safe_load(parts[1])
                if isinstance(front_matter, dict):
                    return front_matter
        except yaml.YAMLError:
            pass
    return {}


def _extract_legacy_metadata(content: str, metadata: dict[str, Any]) -> None:
    """Extract metadata from legacy profile sections."""
    alias_match = re.search('Alias: "([^"]+)".*Public: true', content, re.DOTALL)
    if alias_match and "alias" not in metadata:
        metadata["alias"] = alias_match.group(1)
        metadata["name"] = alias_match.group(1)

    avatar_match = re.search("- URL:\\s*(.+)", content)
    if avatar_match and "avatar" not in metadata:
        metadata["avatar"] = avatar_match.group(1).strip()

    bio_match = re.search('## User Bio\\s*\\n"([^"]+)"', content)
    if bio_match and "bio" not in metadata:
        metadata["bio"] = bio_match.group(1)

    social = {}
    twitter_match = re.search("- Twitter:\\s*(.+)", content)
    if twitter_match:
        social["twitter"] = twitter_match.group(1).strip()

    website_match = re.search("- Website:\\s*(.+)", content)
    if website_match:
        social["website"] = website_match.group(1).strip()

    if social and "social" not in metadata:
        metadata["social"] = social


def _extract_profile_metadata(profile_path: Path) -> dict[str, Any]:
    """Extract metadata from an existing profile file.

    Reads YAML front-matter and profile sections to build metadata dict.

    Args:
        profile_path: Path to profile markdown file

    Returns:
        Dictionary with profile metadata (alias, avatar, bio, social, commands_used)

    """
    if not profile_path.exists():
        return {}

    content = profile_path.read_text(encoding="utf-8")
    metadata = _parse_frontmatter(content)
    _extract_legacy_metadata(content, metadata)

    return metadata


def _update_authors_yml(
    site_root: Path, author_uuid: str, front_matter: dict[str, Any], filename: str | None = None
) -> None:
    """Update or create .authors.yml for MkDocs blog plugin.

    Args:
        site_root: Site root directory (profiles parent)
        author_uuid: Author UUID
        front_matter: Profile front-matter dict
        filename: The actual filename of the profile (e.g. 'franklin.md')

    """
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

    # URL to profile page (relative to docs root)
    # URL to profile page (relative to docs root)
    # New structure: profiles/{uuid}/ (which serves index.md)
    author_entry["url"] = f"profiles/{author_uuid}/"

    # Update authors dict
    authors[author_uuid] = author_entry

    # Write back to .authors.yml
    try:
        with authors_yml_path.open("w", encoding="utf-8") as f:
            yaml.dump(authors, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info("Updated .authors.yml with %s", author_uuid)
    except (OSError, yaml.YAMLError) as e:
        logger.warning("Failed to write .authors.yml: %s", e)


def ensure_author_profile_index(author_uuid: str, profiles_dir: Path) -> Path:
    """Create or refresh the index.md inside an author's profile directory."""
    author_dir = profiles_dir / author_uuid
    author_dir.mkdir(parents=True, exist_ok=True)

    index_path = author_dir / "index.md"
    existing_metadata = _extract_profile_metadata(index_path) if index_path.exists() else {}
    alias = existing_metadata.get("alias") or existing_metadata.get("name") or author_uuid
    name = existing_metadata.get("name", alias)
    avatar = existing_metadata.get("avatar") or generate_fallback_avatar_url(author_uuid)
    bio = existing_metadata.get("bio") or existing_metadata.get("description") or ""
    interests_value = existing_metadata.get("interests") or []
    interests = (
        list(interests_value)
        if isinstance(interests_value, list)
        else [interests_value]
        if interests_value
        else []
    )

    posts = _collect_profile_posts(author_dir)
    posts.sort(key=lambda entry: entry["date_obj"] or date.min, reverse=True)

    front_matter: dict[str, Any] = {
        "uuid": author_uuid,
        "title": name,
        "type": "profile",
        "alias": alias,
        "name": name,
        "avatar": avatar,
        "autogenerated": True,
    }
    if bio:
        front_matter["bio"] = bio
    if interests:
        front_matter["interests"] = interests
    if posts:
        front_matter["posts"] = [
            {"title": entry["title"], "slug": entry["slug"], "date": entry["date_str"]} for entry in posts
        ]

    body = _render_profile_index_body(name=name, alias=alias, bio=bio, interests=interests, posts=posts)

    yaml_front = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    index_path.write_text(f"---\n{yaml_front}---\n\n{body}", encoding="utf-8")

    _update_authors_yml(profiles_dir.parent, author_uuid, front_matter, filename=index_path.name)
    logger.info("Ensured profile index for %s at %s", author_uuid, index_path)
    return index_path


def _collect_profile_posts(author_dir: Path) -> list[dict[str, Any]]:
    posts = []
    for path in sorted(author_dir.glob("*.md")):
        if path.name == "index.md":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue

        metadata = _parse_frontmatter(content)
        slug = metadata.get("slug") or path.stem
        title = metadata.get("title") or slug.replace("-", " ").title()
        date_obj = _normalize_profile_post_date(metadata.get("date"), slug, path)
        date_str = date_obj.isoformat() if date_obj else "Undated"

        posts.append(
            {
                "title": title,
                "slug": slug,
                "date_obj": date_obj,
                "date_str": date_str,
            }
        )
    return posts


def _normalize_profile_post_date(date_value: Any, slug: str, path: Path) -> date | None:
    parsed = _normalize_date_value(date_value)
    if parsed:
        return parsed

    match = PROFILE_DATE_REGEX.match(slug)
    if match:
        try:
            return datetime.fromisoformat(match.group(1)).date()
        except ValueError:
            pass

    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return mtime.date()
    except OSError:
        return None


def _normalize_date_value(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            pass
    return None


def _render_profile_index_body(
    *, name: str, alias: str, bio: str, interests: list[Any], posts: list[dict[str, Any]]
) -> str:
    sections: list[str] = []
    sections.append("![Avatar]({ page.meta.avatar }){ align=left width=150 }")
    sections.append(f"# {html.escape(name)}")
    if alias and alias != name:
        sections.append(f"*Alias: {html.escape(alias)}*")
    if bio:
        sections.append(html.escape(bio))
    if interests:
        escaped = ", ".join(html.escape(str(item)) for item in interests if item)
        if escaped:
            sections.append("## Interests")
            sections.append(escaped)
    if posts:
        sections.append("## Profile Posts")
        for entry in posts:
            title = html.escape(entry["title"])
            slug = entry["slug"]
            date = entry["date_str"]
            sections.append(f"- [{title}]({slug}.md) — {date}")
    else:
        sections.append("_No profile posts exist yet._")
    return "\n\n".join(sections) + "\n"


def _build_author_entry(
    profile_path: Path,
    metadata: dict,
    *,
    author_uuid: str | None = None,
    url: str | None = None,
) -> dict:
    """Build an author entry dict from profile metadata."""
    # If author_uuid not passed, try to get from metadata or filename(deprecated)
    if not author_uuid:
        author_uuid = str(metadata.get("uuid", profile_path.stem))

    # Ensure we have a name (default to UUID if missing)
    name = metadata.get("name", metadata.get("alias", author_uuid))

    # Ensure avatar fallback if missing
    avatar = metadata.get("avatar", generate_fallback_avatar_url(author_uuid))

    # Build entry
    entry = {"name": metadata.get("alias", name), "url": url or f"profiles/{author_uuid}/"}
    if "bio" in metadata:
        entry["description"] = metadata["bio"]
    entry["avatar"] = avatar
    if "social" in metadata:
        entry.update(metadata["social"])

    return entry


def _infer_docs_dir_from_profiles_dir(profiles_dir: Path) -> Path:
    """Return docs_dir given either legacy or posts-centric profiles_dir."""
    if profiles_dir.name == "profiles" and profiles_dir.parent.name == "posts":
        return profiles_dir.parent.parent
    return profiles_dir.parent


def sync_all_profiles(profiles_dir: Path = Path("output/profiles")) -> int:
    """Sync all profiles from directory to .authors.yml.

    Args:
        profiles_dir: Directory containing profile markdown files.

    Returns:
        Number of profiles synced.

    """
    if not profiles_dir.exists():
        return 0

    docs_dir = _infer_docs_dir_from_profiles_dir(profiles_dir)
    authors_yml_path = docs_dir / ".authors.yml"
    authors = {}

    count = 0
    # Logic 1: nested dirs (posts/profiles/{uuid}/*.md) - handled by agents/profile/generator usually?
    # No, profiles.py deals with output/profiles/{slug}.md

    # Handle direct files in profiles_dir
    # Handle direct files in profiles_dir (legacy flat structure)
    for profile_path in profiles_dir.glob("*.md"):
        if profile_path.name == "index.md":
            continue
        try:
            metadata = _extract_profile_metadata(profile_path)
            author_uuid = str(metadata.get("uuid", profile_path.stem))
            entry = _build_author_entry(profile_path, metadata, author_uuid=author_uuid)
            authors[author_uuid] = entry
            count += 1
        except (OSError, yaml.YAMLError) as e:
            logger.warning("Failed to sync profile %s: %s", profile_path, e)

    # Handle nested directories (new structure: {uuid}/index.md)
    # We iterate over directories in profiles_dir
    for author_dir in profiles_dir.iterdir():
        if not author_dir.is_dir():
            continue

        index_path = author_dir / "index.md"
        target_path = index_path
        if not index_path.exists():
            # Fallback: look for ANY markdown file in the directory
            md_files = [
                p for p in author_dir.glob("*.md") if p.name != "index.md"
            ]  # exclude index.md to be safe
            if not md_files:
                continue
            # Pick the first one (arbitrary tie-break if multiple)
            # Typically dynamic posts are named by slug.
            target_path = md_files[0]

        try:
            metadata = _extract_profile_metadata(target_path)
            # UUID should be the directory name or in metadata
            author_uuid = str(metadata.get("uuid", author_dir.name))

            # Determine base URL path relative to docs directory
            try:
                base_url = profiles_dir.relative_to(docs_dir).as_posix()
            except ValueError:
                # Fallback if not relative to docs_dir (unlikely given how docs_dir is inferred)
                base_url = "profiles"

            # For nested structure, we want URL to be specific to the file found
            if target_path.name == "index.md":
                url = f"{base_url}/{author_uuid}/"
            else:
                url = f"{base_url}/{author_uuid}/{target_path.name}"

            entry = _build_author_entry(target_path, metadata, author_uuid=author_uuid, url=url)
            authors[author_uuid] = entry
            count += 1
        except (OSError, yaml.YAMLError) as e:
            logger.warning("Failed to sync profile %s: %s", target_path, e)

        # We handled this directory, continue outer loop
        continue

        # (Original code continued below, but I am replacing the block)

    # Write complete file
    try:
        with authors_yml_path.open("w", encoding="utf-8") as f:
            yaml.dump(authors, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info("Synced %d lists to %s", count, authors_yml_path)
    except OSError:
        logger.exception("Failed to write authors file")

    return count


def update_authors_file(authors_path: Path, author_ids: list[str]) -> int:
    """Load, update, and save the .authors.yml file.

    This is the core, shared logic for registering new authors.

    Args:
        authors_path: The path to the .authors.yml file.
        author_ids: A list of author IDs to ensure are registered.

    Returns:
        The number of new authors that were added to the file.

    """
    # Auto-create if missing
    if not authors_path.exists():
        authors = {}
        # Ensure directory exists
        authors_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        authors = load_authors_yml(authors_path)

    new_ids = register_new_authors(authors, author_ids)
    if new_ids:
        save_authors_yml(authors_path, authors, len(new_ids))
    return len(new_ids)


def ensure_author_entries(output_dir: Path, author_ids: list[str] | None) -> None:
    """Ensure every referenced author has an entry in `.authors.yml`."""
    if not author_ids:
        return

    authors_path = find_authors_yml(output_dir)
    update_authors_file(authors_path, author_ids)


def find_authors_yml(output_dir: Path) -> Path:
    """Finds the .authors.yml file by searching upwards for a `docs` directory."""
    current_dir = output_dir.resolve()
    # More robustly search up the tree for a 'docs' directory
    for parent in [current_dir, *current_dir.parents]:
        if parent.name == "docs":
            return parent / ".authors.yml"

    logger.warning(
        "Could not find 'docs' directory in ancestry of %s. "
        "Falling back to legacy path resolution for .authors.yml.",
        output_dir,
    )
    return output_dir.resolve().parent.parent / ".authors.yml"


def load_authors_yml(path: Path) -> dict:
    """Loads the .authors.yml file."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as e:
        raise AuthorsFileLoadError(str(path), e) from e
    except yaml.YAMLError as e:
        raise AuthorsFileParseError(str(path), e) from e


def register_new_authors(authors: dict, author_ids: list[str]) -> list[str]:
    """Registers new authors."""
    new_ids = []
    for author_id in author_ids:
        if author_id and author_id not in authors:
            authors[author_id] = {
                "name": author_id,
                "url": f"profiles/{author_id}.md",
            }
            new_ids.append(author_id)
    return new_ids


def save_authors_yml(path: Path, authors: dict, count: int) -> None:
    """Saves the .authors.yml file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.dump(authors, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        logger.info("Registered %d new author(s) in %s", count, path)
    except OSError as e:
        raise AuthorsFileSaveError(str(path), e) from e


def extract_authors_from_post(md_file: Path, *, fast: bool = True) -> set[str]:
    """Load a single post file and extract its author IDs.

    Args:
        md_file: Path to markdown file with YAML frontmatter
        fast: Use regex-based extraction (faster but less robust). Default True.

    Returns:
        Set of author IDs found in the post

    Performance:
        - fast=True: ~2-3x faster, uses regex to extract authors field
        - fast=False: Robust YAML parsing via frontmatter library

    """
    try:
        if fast:
            # Fast path: Use regex to extract authors without full YAML parsing
            with md_file.open("r", encoding="utf-8") as f:
                content = f.read(4096)  # Read first 4KB (frontmatter typically <1KB)

            # Try list format first: "authors:\n  - foo\n  - bar"
            list_match = _AUTHORS_LIST_REGEX.search(content)
            if list_match:
                authors_block = list_match.group(1)
                # Extract author IDs from "  - author_id" lines
                authors = set()
                for line in authors_block.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("-"):
                        # Remove the leading "- " and any surrounding whitespace/quotes
                        author = stripped[1:].strip().strip("'\"")
                        if author:
                            authors.add(author)
                return authors if authors else set()

            # Try single value format: "authors: foo"
            single_match = _AUTHORS_SINGLE_REGEX.search(content)
            if single_match:
                author = single_match.group(1).strip()
                if author and not author.startswith("["):  # Not a JSON array
                    return {author}

            return set()
        # Slow path: Full YAML parsing (more robust, handles edge cases)
        post = frontmatter.load(str(md_file))
        authors_meta = post.metadata.get("authors")
        if not authors_meta:
            return set()

        # Normalize to a list
        if not isinstance(authors_meta, list):
            authors_meta = [authors_meta]

        return {str(a) for a in authors_meta if a}

    except OSError as e:
        raise AuthorExtractionError(str(md_file), e) from e


def sync_authors_from_posts(posts_dir: Path, docs_dir: Path | None = None) -> int:
    """Scan all posts and ensure every referenced author exists in .authors.yml."""
    authors_path = find_authors_yml(posts_dir)

    all_author_ids: set[str] = set()
    for md_file in posts_dir.rglob("*.md"):
        all_author_ids.update(extract_authors_from_post(md_file))

    if not all_author_ids:
        return 0

    new_count = update_authors_file(authors_path, list(all_author_ids))
    if new_count > 0:
        logger.info("Synced %d new author(s) from posts to %s", new_count, authors_path)

    return new_count
