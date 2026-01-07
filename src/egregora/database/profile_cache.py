"""Document caching to eliminate file I/O bottleneck.

This module caches all documents (profiles, posts, media, journals) in the database
during pipeline startup, eliminating the need to repeatedly read markdown files from disk.

The caching strategy:
1. On startup: scan all document files and load into respective tables
2. During execution: query from database instead of reading files
3. On update: sync both file and database

This addresses the performance bottleneck identified in:
- load_profiles_context() - reads N profiles per writer agent init
- load_profile_posts() - reads all posts per profile generation
- get_opted_out_authors() - recursive scan + double read
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import frontmatter
import ibis
import ibis.common.exceptions
import yaml

from egregora.database import schemas

if TYPE_CHECKING:
    from egregora.database.duckdb_manager import DuckDBStorageManager

logger = logging.getLogger(__name__)

MIN_POST_PATH_PARTS = 2


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter from profile content."""
    try:
        post = frontmatter.loads(content)
        return dict(post.metadata)
    except yaml.YAMLError as e:
        logger.debug("Failed to parse frontmatter: %s", e)
        return {}


def _calculate_checksum(content: str) -> str:
    """Calculate SHA-256 checksum of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _extract_uuid_from_path(profile_path: Path) -> str | None:
    """Extract author UUID from profile path.

    Handles both structures:
    - output/profiles/{uuid}/index.md
    - output/profiles/{uuid}.md
    """
    # Check if it's the index.md structure
    if profile_path.name == "index.md":
        return profile_path.parent.name

    # Check if it's the flat structure
    stem = profile_path.stem
    # Basic heuristic: UUID is 36 chars (with dashes) or 32 (hex)
    if len(stem) in (32, 36) and all(c in "0123456789abcdefABCDEF-" for c in stem):
        return stem

    return None


def scan_and_cache_profiles(
    storage: DuckDBStorageManager,
    profiles_dir: Path,
) -> int:
    """Scan all profile files and cache them in the database.

    Args:
        storage: Database storage manager
        profiles_dir: Directory containing profile files

    Returns:
        Number of profiles cached

    """
    # Ensure profiles table exists, even if directory doesn't yet
    schemas.create_table_if_not_exists(
        storage._conn,
        "profiles",
        schemas.PROFILES_SCHEMA,
        overwrite=False,
    )
    if not profiles_dir.exists():
        logger.info("Profiles directory does not exist, skipping scan: %s", profiles_dir)
        return 0

    # Find all profile markdown files
    profile_paths = list(profiles_dir.rglob("*.md"))
    logger.info("Found %d profile files to cache", len(profile_paths))

    cached_count = 0
    for profile_path in profile_paths:
        try:
            # Extract UUID
            author_uuid = _extract_uuid_from_path(profile_path)
            if not author_uuid:
                logger.debug("Skipping non-profile file: %s", profile_path)
                continue

            # Read content
            content = profile_path.read_text(encoding="utf-8")

            # Parse frontmatter
            metadata = _parse_frontmatter(content)

            # Build row for profiles table
            row = {
                "id": author_uuid,  # Use UUID as ID
                "content": content,
                "created_at": datetime.now(UTC),
                "source_checksum": _calculate_checksum(content),
                "subject_uuid": author_uuid,
                "title": metadata.get("alias", metadata.get("name", author_uuid)),
                "alias": metadata.get("alias", ""),
                "summary": metadata.get("bio", ""),
                "avatar_url": metadata.get("avatar", ""),
                "interests": metadata.get("interests", []),
            }

            # Upsert into database (delete + insert)
            storage.replace_rows(
                "profiles",
                ibis.memtable([row]),
                by_keys={"id": author_uuid},
            )

            cached_count += 1
            logger.debug("Cached profile for %s", author_uuid)

        except (ibis.common.exceptions.IbisError, OSError) as e:
            logger.warning("Failed to cache profile %s: %s", profile_path, e)
            continue

    logger.info("Successfully cached %d profiles to database", cached_count)
    return cached_count


def get_profile_from_db(
    storage: DuckDBStorageManager,
    author_uuid: str,
) -> str:
    """Get profile content from database.

    Args:
        storage: Database storage manager
        author_uuid: Author UUID

    Returns:
        Profile content as markdown (empty string if not found)

    """
    try:
        table = storage.read_table("profiles")
        result = table.filter(table.subject_uuid == author_uuid).execute()

        if len(result) == 0:
            logger.debug("No profile found in DB for %s", author_uuid)
            return ""

        return str(result.iloc[0]["content"])
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to read profile from DB for %s: %s", author_uuid, e)
        return ""


def get_all_profiles_from_db(
    storage: DuckDBStorageManager,
) -> dict[str, str]:
    """Get all profiles from database.

    Args:
        storage: Database storage manager

    Returns:
        Dict mapping author UUID to profile content

    """
    try:
        table = storage.read_table("profiles")
        result = table.execute()

        profiles = {}
        for _, row in result.iterrows():
            profiles[row["subject_uuid"]] = row["content"]

        logger.debug("Retrieved %d profiles from database", len(profiles))
        return profiles
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to read profiles from DB: %s", e)
        return {}


def get_opted_out_authors_from_db(
    storage: DuckDBStorageManager,
) -> set[str]:
    """Get list of opted-out authors from database.

    Replaces the file-scanning version that performs recursive glob + double read.

    Args:
        storage: Database storage manager

    Returns:
        Set of opted-out author UUIDs

    """
    try:
        table = storage.read_table("profiles")
        result = table.execute()

        opted_out = set()
        for _, row in result.iterrows():
            content = row["content"]
            # Check for opt-out marker in content
            if "opt-out: true" in content.lower() or "opted_out: true" in content.lower():
                opted_out.add(row["subject_uuid"])

        logger.debug("Found %d opted-out authors in database", len(opted_out))
        return opted_out
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to read opted-out authors from DB: %s", e)
        return set()


def _extract_author_from_path(post_path: Path, posts_dir: Path) -> list[str]:
    """Extract author UUIDs from post path.

    If post is in profiles/{uuid}/ subdirectory, extract that UUID.
    Otherwise, try to extract from frontmatter or return empty list.

    Args:
        post_path: Path to post file
        posts_dir: Base posts directory

    Returns:
        List of author UUIDs

    """
    try:
        # Get relative path from posts_dir
        rel_path = post_path.relative_to(posts_dir)
        parts = rel_path.parts

        # Check if this is a profile post: profiles/{uuid}/filename.md
        if len(parts) >= MIN_POST_PATH_PARTS and parts[0] == "profiles":
            uuid_candidate = parts[1]
            # Validate UUID format
            if len(uuid_candidate) in (32, 36) and all(
                c in "0123456789abcdefABCDEF-" for c in uuid_candidate
            ):
                return [uuid_candidate]
    except (ValueError, IndexError):
        pass

    return []


def scan_and_cache_posts(
    storage: DuckDBStorageManager,
    posts_dir: Path,
) -> int:
    """Scan all post files and cache them in the database.

    Args:
        storage: Database storage manager
        posts_dir: Directory containing post files

    Returns:
        Number of posts cached

    """
    # Ensure posts table exists, even if directory doesn't yet
    schemas.create_table_if_not_exists(
        storage._conn,
        "posts",
        schemas.POSTS_SCHEMA,
        overwrite=False,
    )
    if not posts_dir.exists():
        logger.info("Posts directory does not exist, skipping scan: %s", posts_dir)
        return 0

    # Find all post markdown files
    post_paths = list(posts_dir.rglob("*.md"))
    logger.info("Found %d post files to cache", len(post_paths))

    cached_count = 0
    for post_path in post_paths:
        try:
            # Skip index.md files
            if post_path.name == "index.md":
                continue

            # Read content
            content = post_path.read_text(encoding="utf-8")

            # Parse frontmatter
            metadata = _parse_frontmatter(content)

            # Extract slug from filename or metadata
            slug = metadata.get("slug", post_path.stem)

            # Extract authors from path or frontmatter
            authors = _extract_author_from_path(post_path, posts_dir)
            if not authors and "authors" in metadata:
                authors = metadata.get("authors", [])

            # Build row for posts table
            row = {
                "id": slug,  # Use slug as ID
                "content": content,
                "created_at": datetime.now(UTC),
                "source_checksum": _calculate_checksum(content),
                "title": metadata.get("title", ""),
                "slug": slug,
                "date": metadata.get("date"),
                "summary": metadata.get("description", ""),
                "authors": authors,
                "tags": metadata.get("tags", []),
                "status": metadata.get("status", "published"),
            }

            # Upsert into database (delete + insert)
            storage.replace_rows(
                "posts",
                ibis.memtable([row]),
                by_keys={"id": slug},
            )

            cached_count += 1
            logger.debug("Cached post: %s (authors: %s)", slug, authors)

        except (ibis.common.exceptions.IbisError, OSError) as e:
            logger.warning("Failed to cache post %s: %s", post_path, e)
            continue

    logger.info("Successfully cached %d posts to database", cached_count)
    return cached_count


def get_profile_posts_from_db(
    storage: DuckDBStorageManager,
    author_uuid: str,
) -> list[dict[str, Any]]:
    """Get all profile posts for an author from database.

    Args:
        storage: Database storage manager
        author_uuid: Author UUID

    Returns:
        List of post dicts with content, metadata, etc.

    """
    try:
        table = storage.read_table("posts")

        # Filter for posts where this author is in the authors array
        # Using contains for array filtering
        result = table.filter(table.authors.contains(author_uuid)).execute()

        posts = []
        for _, row in result.iterrows():
            posts.append(
                {
                    "slug": row["slug"],
                    "title": row["title"],
                    "content": row["content"],
                    "date": str(row["date"]) if row["date"] else "",
                    "summary": row["summary"],
                }
            )

        logger.debug("Retrieved %d profile posts for %s from database", len(posts), author_uuid)
        return posts
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to read profile posts from DB for %s: %s", author_uuid, e)
        return []


def scan_and_cache_all_documents(
    storage: DuckDBStorageManager,
    profiles_dir: Path,
    posts_dir: Path,
) -> dict[str, int]:
    """Scan and cache all document types (profiles, posts, etc.).

    Args:
        storage: Database storage manager
        profiles_dir: Directory containing profile files
        posts_dir: Directory containing post files

    Returns:
        Dict with counts for each document type cached

    """
    logger.info("Starting comprehensive document caching...")

    counts = {
        "profiles": scan_and_cache_profiles(storage, profiles_dir),
        "posts": scan_and_cache_posts(storage, posts_dir),
    }

    total = sum(counts.values())
    logger.info("Document caching complete: %d total documents (%s)", total, counts)

    return counts
