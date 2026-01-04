"""Profile history generation using Jinja templates.

Compiles all profile posts for an author into a chronological history
that can be included in the writer agent's context window.

This enables the LLM to:
- See how the author's profile has evolved over time
- Avoid repeating previous analyses
- Build on prior insights
- Track significant changes in interests/contributions
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Template

logger = logging.getLogger(__name__)

# Minimum number of parts required for date-aspect-authorid filename format (YYYY-MM-DD-aspect)
MIN_FILENAME_PARTS = 4


@dataclass
class ProfilePost:
    """Represents a single profile post in the history."""

    date: str
    title: str
    slug: str
    content: str
    file_path: Path
    aspect: str  # Extracted from title (e.g., "Technical Contributions")

    @property
    def summary(self) -> str:
        """Return first paragraph as summary."""
        lines = [line for line in self.content.split("\n") if line.strip() and not line.startswith("#")]
        return lines[0] if lines else ""


@dataclass
class ProfileHistory:
    """Complete profile history for an author."""

    author_uuid: str
    posts: list[ProfilePost]
    total_posts: int
    date_range: tuple[str, str] | None
    aspects_analyzed: set[str]

    @classmethod
    def from_posts(cls, author_uuid: str, posts: list[ProfilePost]) -> "ProfileHistory":
        """Create ProfileHistory from list of posts."""
        if not posts:
            return cls(
                author_uuid=author_uuid,
                posts=[],
                total_posts=0,
                date_range=None,
                aspects_analyzed=set(),
            )

        # Sort by date
        sorted_posts = sorted(posts, key=lambda p: p.date)

        # Extract aspects
        aspects = {post.aspect for post in posts if post.aspect}

        # Get date range
        first_date = sorted_posts[0].date
        last_date = sorted_posts[-1].date

        return cls(
            author_uuid=author_uuid,
            posts=sorted_posts,
            total_posts=len(posts),
            date_range=(first_date, last_date),
            aspects_analyzed=aspects,
        )


DEFAULT_HISTORY_TEMPLATE = """# Profile History for {{ author_uuid }}

{% if history.total_posts == 0 %}
No profile posts exist yet for this author.
{% else %}
{{ history.total_posts }} profile post(s) from {{ history.date_range[0] }} to {{ history.date_range[1] }}

**Aspects analyzed:** {{ history.aspects_analyzed | join(", ") }}

---

## Chronological Timeline

{% for post in history.posts %}
### {{ post.date }}: {{ post.title }}

**Aspect:** {{ post.aspect }}
**Summary:** {{ post.summary }}

<details>
<summary>Full content</summary>

{{ post.content }}

</details>

---
{% endfor %}

## Analysis Guidelines

Based on the profile history above:
1. **Avoid repetition**: Don't restate insights from previous posts
2. **Build on prior work**: Reference and extend previous analyses
3. **Track evolution**: Note how the author's interests/contributions have changed
4. **Identify gaps**: Look for aspects not yet analyzed

{% endif %}
"""


def load_profile_posts(author_uuid: str, profiles_dir: Path, storage: Any | None = None) -> list[ProfilePost]:
    """Load all profile posts for an author from database or directory.

    Reads from database cache if available, eliminating file I/O bottleneck.
    Falls back to file-based reading if storage is not provided.

    Args:
        author_uuid: The author's UUID
        profiles_dir: Base profiles directory (e.g., docs/posts/profiles/)
        storage: DuckDBStorageManager instance for database access (optional)

    Returns:
        List of ProfilePost objects, sorted by date

    """
    # Use database cache if available
    if storage is not None:
        from egregora.database.profile_cache import get_profile_posts_from_db

        try:
            db_posts = get_profile_posts_from_db(storage, author_uuid)
            posts = []

            for post_data in db_posts:
                # Extract metadata from content or use defaults
                content = post_data["content"]
                slug = post_data["slug"]

                # Parse aspect from slug if possible
                parts = slug.split("-")
                if len(parts) >= MIN_FILENAME_PARTS:
                    aspect_parts = parts[3:-1] if len(parts) > MIN_FILENAME_PARTS else parts[3:4]
                    aspect = " ".join(aspect_parts).replace("-", " ").title()
                else:
                    aspect = "General Profile"

                posts.append(
                    ProfilePost(
                        date=post_data["date"],
                        title=post_data["title"] or "Profile Post",
                        slug=slug,
                        content=content,
                        file_path=profiles_dir / author_uuid / f"{slug}.md",  # Reconstructed path
                        aspect=aspect,
                    )
                )

            logger.info("Loaded %d profile posts for %s from database", len(posts), author_uuid)
            return posts

        except Exception as e:
            logger.warning("Failed to load from database, falling back to files: %s", e)
            # Fall through to file-based loading

    # Fallback to file-based reading
    author_dir = profiles_dir / author_uuid

    if not author_dir.exists():
        logger.debug("No profile directory found for %s", author_uuid)
        return []

    posts = []

    for file_path in author_dir.glob("*.md"):
        if file_path.name == "index.md":
            continue  # Skip index files

        try:
            content = file_path.read_text(encoding="utf-8")

            # Extract metadata from filename: YYYY-MM-DD-aspect-authorid.md
            stem = file_path.stem
            parts = stem.split("-")

            if len(parts) >= MIN_FILENAME_PARTS:
                # Extract date (first 3 parts: YYYY-MM-DD)
                date = f"{parts[0]}-{parts[1]}-{parts[2]}"

                # Extract aspect (everything between date and last part)
                aspect_parts = parts[3:-1] if len(parts) > MIN_FILENAME_PARTS else parts[3:4]
                aspect = " ".join(aspect_parts).replace("-", " ").title()
            else:
                # Fallback for non-standard naming
                date = datetime.now().strftime("%Y-%m-%d")
                aspect = "General Profile"

            # Extract title from content (first H1)
            title = "Profile Post"
            for line in content.split("\n"):
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            posts.append(
                ProfilePost(
                    date=date,
                    title=title,
                    slug=file_path.stem,
                    content=content,
                    file_path=file_path,
                    aspect=aspect,
                )
            )

        except Exception:
            logger.exception("Failed to load profile post: %s", file_path)
            continue

    logger.info("Loaded %d profile posts for %s from files", len(posts), author_uuid)
    return posts


def render_profile_history(
    author_uuid: str,
    profiles_dir: Path,
    template: Template | None = None,
    storage: Any | None = None,
) -> str:
    """Render a complete profile history for an author.

    Args:
        author_uuid: The author's UUID
        profiles_dir: Base profiles directory
        template: Optional custom Jinja template (uses default if None)
        storage: DuckDBStorageManager instance for database access (optional)

    Returns:
        Rendered profile history as markdown

    """
    # Load all profile posts
    posts = load_profile_posts(author_uuid, profiles_dir, storage=storage)

    # Build history object
    history = ProfileHistory.from_posts(author_uuid, posts)

    # Use default template if none provided
    if template is None:
        template = Template(DEFAULT_HISTORY_TEMPLATE)

    # Render template
    return template.render(author_uuid=author_uuid, history=history)


def get_profile_history_for_context(
    author_uuid: str,
    profiles_dir: Path,
    max_posts: int = 5,
    storage: Any | None = None,
) -> str:
    """Get condensed profile history suitable for LLM context window.

    Returns a summary of recent profile posts to include in the writer's
    context without overwhelming the token budget.

    Args:
        author_uuid: The author's UUID
        profiles_dir: Base profiles directory
        max_posts: Maximum number of recent posts to include
        storage: DuckDBStorageManager instance for database access (optional)

    Returns:
        Condensed markdown summary for context window

    """
    posts = load_profile_posts(author_uuid, profiles_dir, storage=storage)

    if not posts:
        return f"# Profile History for {author_uuid}\n\nNo prior profile posts exist."

    # Sort by date descending (most recent first)
    recent_posts = sorted(posts, key=lambda p: p.date, reverse=True)[:max_posts]

    # Build condensed summary
    lines = [
        f"# Profile History for {author_uuid}",
        "",
        f"**Total posts:** {len(posts)} | **Showing:** {len(recent_posts)} most recent",
        "",
    ]

    # Group by aspect
    by_aspect: dict[str, list[ProfilePost]] = defaultdict(list)
    for post in recent_posts:
        by_aspect[post.aspect].append(post)

    # Show recent posts grouped by aspect
    lines.append("## Recent Analyses")
    lines.append("")

    for post in recent_posts:
        lines.append(f"**{post.date}** - *{post.aspect}*: {post.title}")
        lines.append(f"> {post.summary[:200]}...")
        lines.append("")

    # Summary of what's been covered
    all_aspects = {post.aspect for post in posts}
    lines.append("## Coverage Summary")
    lines.append("")
    lines.append(f"**Aspects analyzed ({len(all_aspects)}):** {', '.join(sorted(all_aspects))}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**Guidelines for new analysis:**")
    lines.append("- Build on insights from recent posts above")
    lines.append("- Avoid repeating covered aspects unless there's significant change")
    lines.append("- Focus on new developments or underexplored areas")

    return "\n".join(lines)


__all__ = [
    "ProfileHistory",
    "ProfilePost",
    "get_profile_history_for_context",
    "load_profile_posts",
    "render_profile_history",
]
