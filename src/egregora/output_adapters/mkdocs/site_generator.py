"""SiteGenerator for MkDocs output adapter.

This module contains the SiteGenerator class, which is responsible for
generating the static site pages for the MkDocs output adapter. It handles
all presentation-layer logic, such as rendering index pages, calculating
site statistics, and generating author profiles.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import frontmatter
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.text import slugify
from egregora.knowledge.profiles import generate_fallback_avatar_url
from egregora.output_adapters.exceptions import DocumentParsingError

if TYPE_CHECKING:
    from egregora.data_primitives.document import UrlContext
    from egregora.output_adapters.conventions import UrlConvention

logger = logging.getLogger(__name__)


class SiteGenerator:
    """Handles the generation of static site pages for MkDocs."""

    def __init__(
        self,
        site_root: Path,
        docs_dir: Path,
        posts_dir: Path,
        profiles_dir: Path,
        media_dir: Path,
        journal_dir: Path,
        url_convention: UrlConvention,
        url_context: UrlContext,
        db_path: Path | None = None,
    ) -> None:
        self.site_root = site_root
        self.docs_dir = docs_dir
        self.posts_dir = posts_dir
        self.profiles_dir = profiles_dir
        self.media_dir = media_dir
        self.journal_dir = journal_dir
        self.urls_dir = self.media_dir / "urls"
        self._url_convention = url_convention
        self._ctx = url_context
        self.db_path = db_path

        templates_dir = Path(__file__).resolve().parents[2] / "rendering" / "templates" / "site"
        self._template_env = Environment(
            loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape()
        )

    def _read_frontmatter_only(self, path: Path) -> dict[str, Any]:
        """Reads only the YAML frontmatter from a markdown file.

        Optimized to read only the beginning of the file to avoid loading
        large content when only metadata is needed.
        """
        try:
            # Read first 4KB which should cover most frontmatters
            with path.open("r", encoding="utf-8") as f:
                header = f.read(4096)

            if header.startswith("---"):
                # Find the closing delimiter
                end_pos = header.find("\n---", 3)
                if end_pos != -1:
                    yaml_text = header[3:end_pos]
                    return yaml.safe_load(yaml_text) or {}

                # If not found in 4KB, try reading up to 16KB
                with path.open("r", encoding="utf-8") as f:
                    header = f.read(16384)
                end_pos = header.find("\n---", 3)
                if end_pos != -1:
                    yaml_text = header[3:end_pos]
                    return yaml.safe_load(yaml_text) or {}

                # If still not found but starts with ---, it might be huge or malformed.
                # Fallback to full load to ensure correctness.
                post = frontmatter.load(str(path))
                return post.metadata

            return {}

        except (OSError, yaml.YAMLError) as e:
            raise DocumentParsingError(str(path), str(e)) from e

    def _scan_directory(
        self, directory: Path, doc_type: DocumentType, *, metadata_only: bool = False
    ) -> Iterator[Document]:
        """Scans a directory for markdown files and yields Document objects.

        Args:
            directory: Directory to scan
            doc_type: Type of documents to create
            metadata_only: If True, only reads frontmatter and skips content.

        """
        if not directory.exists():
            return
        for path in directory.rglob("*.md"):
            if path.is_file() and "index" not in path.name:
                try:
                    if metadata_only:
                        metadata = self._read_frontmatter_only(path)
                        content = ""
                    else:
                        post = frontmatter.load(str(path))
                        metadata = post.metadata
                        content = post.content

                    doc = Document(content=content, type=doc_type, metadata=metadata)
                    yield doc
                except (OSError, yaml.YAMLError) as e:
                    raise DocumentParsingError(str(path), str(e)) from e

    def get_site_stats(self) -> dict[str, int]:
        """Calculate site statistics for homepage."""
        post_count = len([p for p in self.posts_dir.rglob("*.md") if p.is_file() and "index" not in p.name])
        profile_count = len(list(self.profiles_dir.glob("*/*.md")))  # Count files in author subdirs
        media_count = len([p for p in self.urls_dir.rglob("*.md") if p.is_file() and "index" not in p.name])
        journal_count = len(
            [p for p in self.journal_dir.rglob("*.md") if p.is_file() and "index" not in p.name]
        )

        return {
            "post_count": post_count,
            "profile_count": profile_count,
            "media_count": media_count,
            "journal_count": journal_count,
        }

    def get_profiles_data(self) -> list[dict[str, Any]]:
        """Extract profile metadata for profiles index."""
        profiles = []
        if not self.profiles_dir.exists():
            return profiles

        # Pre-scan posts to build author index
        # Map author_uuid -> list of post stats (metadata, word_count)
        author_posts_map = defaultdict(list)

        if self.posts_dir.exists():
            # Use _scan_directory generator to process posts one by one
            # Avoiding loading all content into a list
            for doc in self._scan_directory(self.posts_dir, DocumentType.POST):
                try:
                    # Calculate word count
                    word_count = len(doc.content.split())

                    # Store lightweight stats
                    post_stats = {"metadata": doc.metadata, "word_count": word_count}

                    # Index by author (deduplicate to avoid double counting)
                    for author_uuid in set(doc.metadata.get("authors", [])):
                        author_posts_map[author_uuid].append(post_stats)

                except Exception as e:
                    logger.warning("Failed to process post for profiles: %s", e)
                    continue

        for author_dir in sorted([p for p in self.profiles_dir.iterdir() if p.is_dir()]):
            try:
                candidates = [p for p in author_dir.glob("*.md") if p.name != "index.md"]
                if not candidates:
                    continue

                profile_path = max(candidates, key=lambda p: p.stat().st_mtime_ns)
                post = frontmatter.load(str(profile_path))
                metadata = post.metadata
                author_uuid = author_dir.name

                # O(1) lookup
                author_posts = author_posts_map.get(author_uuid, [])

                # Calculate topics
                topics = Counter(tag for p in author_posts for tag in p["metadata"].get("tags", []))

                profiles.append(
                    {
                        "uuid": author_uuid,
                        "name": metadata.get("name", author_uuid[:8]),
                        "avatar": metadata.get("avatar", generate_fallback_avatar_url(author_uuid)),
                        "bio": metadata.get("bio", "Profile pending."),
                        "post_count": len(author_posts),
                        "word_count": sum(p["word_count"] for p in author_posts),
                        "topics": [topic for topic, count in topics.most_common()],
                        "topic_counts": topics.most_common(),
                        "member_since": metadata.get("member_since", "2024"),
                    }
                )
            except (OSError, yaml.YAMLError) as e:
                raise DocumentParsingError(str(author_dir), str(e)) from e
        return profiles

    def get_recent_media(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get recent media items for media index."""
        media_items = []
        if not self.urls_dir.exists():
            return media_items

        url_files = sorted(
            [p for p in self.urls_dir.glob("*.md") if p.name != "index.md"],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:limit]

        for path in url_files:
            try:
                post = frontmatter.load(str(path))
                summary = ""
                if "## Summary" in post.content:
                    summary = post.content.split("## Summary", 1)[1].split("##", 1)[0].strip()[:200]
                media_items.append(
                    {
                        "title": post.metadata.get("title", path.stem),
                        "url": post.metadata.get("url", ""),
                        "slug": post.metadata.get("slug", path.stem),
                        "summary": summary or post.metadata.get("description", ""),
                    }
                )
            except (OSError, yaml.YAMLError) as e:
                raise DocumentParsingError(str(path), str(e)) from e
        return media_items

    def get_recent_posts(self, limit: int = 6) -> list[dict[str, Any]]:
        """Get recent published posts for homepage.

        Only returns posts with banner images. Posts without banners are filtered out.
        """
        posts = []
        if not self.posts_dir.exists():
            return posts

        # Get all post markdown files, excluding index
        post_files = [p for p in self.posts_dir.rglob("*.md") if p.name != "index.md"]

        # Sort by modification time (most recent first)
        # Get more candidates to account for filtering posts without banners
        post_files = sorted(post_files, key=lambda p: p.stat().st_mtime, reverse=True)

        for path in post_files:
            # Stop once we have enough posts with banners
            if len(posts) >= limit:
                break
            try:
                metadata = self._read_frontmatter_only(path)

                # Build post URL from date and slug
                post_date = metadata.get("date")
                post_slug = metadata.get("slug", path.stem)

                if post_date:
                    # Format: posts/YYYY/MM/DD/slug
                    if isinstance(post_date, str):
                        # Parse date string
                        from datetime import datetime as dt

                        try:
                            post_date = dt.fromisoformat(post_date).date()
                        except ValueError:
                            logger.warning(
                                "Invalid date format for post %s: %s. Using path stem.",
                                path.name,
                                post_date,
                            )
                            post_date = None

                    if post_date:
                        post_url = f"posts/{post_date.year:04d}/{post_date.month:02d}/{post_date.day:02d}/{post_slug}/"
                    else:
                        post_url = f"posts/{post_slug}/"
                else:
                    post_url = f"posts/{post_slug}/"

                # Get authors with avatars
                authors = []
                for author_uuid in metadata.get("authors", []):
                    author_dir = self.profiles_dir / author_uuid
                    if author_dir.exists():
                        candidates = [p for p in author_dir.glob("*.md") if p.name != "index.md"]
                        if candidates:
                            profile_path = max(candidates, key=lambda p: p.stat().st_mtime_ns)
                            profile_meta = self._read_frontmatter_only(profile_path)
                            authors.append(
                                {
                                    "uuid": author_uuid,
                                    "name": profile_meta.get("name", author_uuid[:8]),
                                    "avatar": profile_meta.get(
                                        "avatar", generate_fallback_avatar_url(author_uuid)
                                    ),
                                }
                            )

                # Get banner - required for homepage display
                banner = metadata.get("banner") or metadata.get("image")

                # Skip posts without banners - they won't display well in the grid
                if not banner:
                    logger.debug("Skipping post without banner: %s", path.name)
                    continue

                posts.append(
                    {
                        "title": metadata.get("title", "Untitled"),
                        "url": post_url,
                        "date": metadata.get("date"),
                        "summary": metadata.get("summary", ""),
                        "authors": authors,
                        "tags": metadata.get("tags", []),
                        "reading_time": metadata.get("reading_time", 5),
                        "banner": banner,
                    }
                )
            except (OSError, yaml.YAMLError) as e:
                logger.warning("Could not parse post %s: %s", path, e)
                continue

        return posts

    def get_top_posts_by_elo(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get top-rated posts by ELO ranking.

        Only returns posts with banner images and valid ELO ratings.
        Requires reader database to exist at self.db_path.

        Args:
            limit: Maximum number of top posts to return (default: 5)

        Returns:
            List of post dictionaries with metadata, sorted by ELO rating (highest first)

        """
        posts = []

        # Check if database exists
        if not self.db_path or not self.db_path.exists():
            logger.debug("Reader database not found at %s, skipping top posts", self.db_path)
            return posts

        try:
            from egregora.database.duckdb_manager import DuckDBStorageManager
            from egregora.database.elo_store import EloStore

            # Get top rated posts from database
            with DuckDBStorageManager(self.db_path) as storage:
                elo_store = EloStore(storage)
                top_rated = elo_store.get_top_posts(
                    limit=limit * 2
                ).execute()  # Get extra to account for filtering

            if top_rated.empty:
                logger.debug("No ELO ratings found in database")
                return posts

            # Map post_id to ELO data
            elo_map = {
                row.post_id: {
                    "elo_rating": row.elo_global,
                    "comparisons": row.num_comparisons,
                    "win_rate": row.win_rate if hasattr(row, "win_rate") else None,
                }
                for row in top_rated.itertuples(index=False)
            }

            # Load post metadata from markdown files
            if not self.posts_dir.exists():
                return posts

            post_files = list(self.posts_dir.rglob("*.md"))
            post_files = [p for p in post_files if p.name != "index.md"]

            for path in post_files:
                if len(posts) >= limit:
                    break

                try:
                    metadata = self._read_frontmatter_only(path)
                    post_slug = metadata.get("slug", path.stem)

                    # Skip if not in top rated list
                    if post_slug not in elo_map:
                        continue

                    # Build post URL
                    post_date = metadata.get("date")
                    if post_date:
                        from datetime import datetime as dt

                        if isinstance(post_date, str):
                            try:
                                post_date = dt.fromisoformat(post_date).date()
                            except ValueError:
                                logger.warning(
                                    "Invalid date format for top post %s: %s. Using slug.",
                                    post_slug,
                                    post_date,
                                )
                                post_date = None

                        if post_date:
                            post_url = f"posts/{post_date.year:04d}/{post_date.month:02d}/{post_date.day:02d}/{post_slug}/"
                        else:
                            post_url = f"posts/{post_slug}/"
                    else:
                        post_url = f"posts/{post_slug}/"

                    # Get authors with avatars
                    authors = []
                    for author_uuid in metadata.get("authors", []):
                        author_dir = self.profiles_dir / author_uuid
                        if author_dir.exists():
                            candidates = [p for p in author_dir.glob("*.md") if p.name != "index.md"]
                            if candidates:
                                profile_path = max(candidates, key=lambda p: p.stat().st_mtime_ns)
                                profile_meta = self._read_frontmatter_only(profile_path)
                                authors.append(
                                    {
                                        "uuid": author_uuid,
                                        "name": profile_meta.get("name", author_uuid[:8]),
                                        "avatar": profile_meta.get(
                                            "avatar", generate_fallback_avatar_url(author_uuid)
                                        ),
                                    }
                                )

                    # Get banner - required for display
                    banner = metadata.get("banner") or metadata.get("image")
                    if not banner:
                        logger.debug("Skipping top post without banner: %s", post_slug)
                        continue

                    # Add ELO data to post
                    elo_data = elo_map[post_slug]
                    posts.append(
                        {
                            "title": metadata.get("title", "Untitled"),
                            "url": post_url,
                            "date": metadata.get("date"),
                            "summary": metadata.get("summary", ""),
                            "authors": authors,
                            "tags": metadata.get("tags", []),
                            "reading_time": metadata.get("reading_time", 5),
                            "banner": banner,
                            "elo_rating": elo_data["elo_rating"],
                            "comparisons": elo_data["comparisons"],
                            "win_rate": elo_data["win_rate"],
                        }
                    )
                except (OSError, yaml.YAMLError) as e:
                    logger.warning("Could not parse post %s: %s", path, e)
                    continue

            # Sort by ELO rating (highest first)
            posts.sort(key=lambda x: x["elo_rating"], reverse=True)

        except Exception as e:
            logger.warning("Failed to get top posts by ELO: %s", e)
            return []

        return posts[:limit]

    def regenerate_tags_page(self) -> None:
        """Regenerate the tags.md page."""
        all_posts = self._scan_directory(self.posts_dir, DocumentType.POST, metadata_only=True)
        tag_counts = Counter(tag for post in all_posts for tag in post.metadata.get("tags", []))
        if not tag_counts:
            return

        max_count = max(tag_counts.values())
        tags_data = []
        for tag, count in tag_counts.items():
            level = int(((count - 1) / (max_count - 1)) * 9) + 1 if max_count > 1 else 5
            tags_data.append({"name": tag, "slug": slugify(tag), "count": count, "frequency_level": level})

        template = self._template_env.get_template("docs/posts/tags.md.jinja")
        content = template.render(tags=sorted(tags_data, key=lambda x: x["count"], reverse=True))
        (self.posts_dir / "tags.md").write_text(content, encoding="utf-8")

    def regenerate_feeds_page(self) -> None:
        """Regenerate the feeds/index.md page listing all available RSS feeds."""
        # Collect categories/tags from all posts
        all_posts = self._scan_directory(self.posts_dir, DocumentType.POST, metadata_only=True)
        tag_counts = Counter(tag for post in all_posts for tag in post.metadata.get("tags", []))

        if not tag_counts:
            categories = []
        else:
            categories = [
                {"name": tag, "slug": slugify(tag), "count": count} for tag, count in tag_counts.items()
            ]
            categories.sort(key=lambda x: x["count"], reverse=True)

        template = self._template_env.get_template("docs/feeds/index.md.jinja")
        content = template.render(categories=categories)

        feeds_dir = self.docs_dir / "feeds"
        feeds_dir.mkdir(exist_ok=True)
        (feeds_dir / "index.md").write_text(content, encoding="utf-8")

    def regenerate_main_index(self) -> None:
        """Regenerates the main index.md from a template."""
        import os

        # Calculate relative paths for template links
        blog_relative = Path(os.path.relpath(self.posts_dir, self.docs_dir)).as_posix()
        media_relative = Path(os.path.relpath(self.media_dir, self.docs_dir)).as_posix()

        context = {
            "site_name": self.site_root.name or "Egregora Archive",
            "blog_dir": blog_relative,
            "media_dir": media_relative,
            "stats": self.get_site_stats(),
            "posts": self.get_recent_posts(limit=6),
            "top_posts": self.get_top_posts_by_elo(limit=5),
            "recent_media": self.get_recent_media(limit=5),
            "profiles": self.get_profiles_data(),
            "generated_date": datetime.now(UTC).strftime("%Y-%m-%d"),
        }
        template = self._template_env.get_template("docs/index.md.jinja")
        (self.docs_dir / "index.md").write_text(template.render(context), encoding="utf-8")

    def regenerate_profiles_index(self) -> None:
        """Regenerates the profiles index.md from a template."""
        profiles = self.get_profiles_data()
        template = self._template_env.get_template("docs/profiles/index.md.jinja")
        content = template.render(profiles=profiles)
        (self.profiles_dir / "index.md").write_text(content, encoding="utf-8")

    def regenerate_media_index(self) -> None:
        """Regenerates the media index.md from a template."""
        media_items = self.get_recent_media(limit=50)
        template = self._template_env.get_template("docs/media/index.md.jinja")
        content = template.render(media_items=media_items)
        (self.media_dir / "index.md").write_text(content, encoding="utf-8")
