"""Handles generation of dynamic MkDocs pages like indexes and tag pages."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import frontmatter
import yaml
from jinja2 import Environment, FileSystemLoader, TemplateError

from egregora.data_primitives.document import DocumentType
from egregora.knowledge.profiles import generate_fallback_avatar_url
from egregora.output_adapters.exceptions import DocumentParsingError
from egregora.utils.paths import slugify

if TYPE_CHECKING:
    from egregora.output_adapters.mkdocs.adapter import MkDocsAdapter


logger = logging.getLogger(__name__)


class MkDocsPageGenerator:
    """Handles generation of dynamic MkDocs pages like indexes and tag pages."""

    def __init__(self, adapter: MkDocsAdapter) -> None:
        """Initializes the page generator."""
        self._adapter = adapter
        self._template_env = self._get_template_env()

    def _get_template_env(self) -> Environment:
        """Initializes the Jinja2 environment."""
        if hasattr(self._adapter, "_template_env") and self._adapter._template_env:
            return self._adapter._template_env

        templates_dir = Path(__file__).resolve().parents[2] / "rendering" / "templates" / "site"
        return Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)

    def regenerate_all(self) -> None:
        """Regenerates all dynamic pages."""
        logger.info("Regenerating all dynamic MkDocs pages.")
        self.regenerate_main_index()
        self.regenerate_profiles_index()
        self.regenerate_media_index()
        self.regenerate_tags_page()

    def get_site_stats(self) -> dict[str, int]:
        """Calculate site statistics for homepage."""
        stats = {"post_count": 0, "profile_count": 0, "media_count": 0, "journal_count": 0}
        adapter = self._adapter
        if not hasattr(adapter, "posts_dir") or not adapter.posts_dir:
            return stats
        if adapter.posts_dir.exists():
            stats["post_count"] = len(
                [p for p in adapter.posts_dir.glob("*.md") if p.name not in {"index.md", "tags.md"}]
            )
        if adapter.profiles_dir.exists():
            author_dirs = [p for p in adapter.profiles_dir.iterdir() if p.is_dir()]
            stats["profile_count"] = len(author_dirs)
        if adapter.media_dir.exists():
            all_media = list(adapter.media_dir.rglob("*.md"))
            stats["media_count"] = len([p for p in all_media if p.name != "index.md"])
        if adapter.posts_dir.exists():
            journal_count = 0
            for path in adapter.posts_dir.glob("*.md"):
                if path.name in {"index.md", "tags.md"}:
                    continue
                if adapter._detect_document_type(path) == DocumentType.JOURNAL:
                    journal_count += 1
            stats["journal_count"] = journal_count
        return stats

    def get_profiles_data(self) -> list[dict[str, Any]]:
        """Extract profile metadata for profiles index, including calculated stats."""
        profiles = []
        adapter = self._adapter
        all_posts = list(adapter.documents())
        if not hasattr(adapter, "profiles_dir") or not adapter.profiles_dir.exists():
            return profiles
        for author_dir in sorted([p for p in adapter.profiles_dir.iterdir() if p.is_dir()]):
            try:
                candidates = [p for p in author_dir.glob("*.md") if p.name != "index.md"]
                if not candidates:
                    continue
                profile_path = max(candidates, key=lambda p: p.stat().st_mtime_ns)
                post = frontmatter.load(str(profile_path))
                metadata = post.metadata
                author_uuid = author_dir.name
                author_posts = [
                    p for p in all_posts if p.metadata and author_uuid in p.metadata.get("authors", [])
                ]
                post_count = len(author_posts)
                word_count = sum(len(p.content.split()) for p in author_posts)
                topics = {}
                for p in author_posts:
                    for tag in p.metadata.get("tags", []):
                        topics[tag] = topics.get(tag, 0) + 1
                top_topics = sorted(topics.items(), key=lambda item: item[1], reverse=True)
                avatar = metadata.get("avatar", "")
                if not avatar:
                    avatar = generate_fallback_avatar_url(author_uuid)
                profiles.append(
                    {
                        "uuid": author_uuid,
                        "name": metadata.get("name", author_uuid[:8]),
                        "avatar": avatar,
                        "bio": metadata.get("bio", "Profile pending - first contributions detected"),
                        "post_count": post_count,
                        "word_count": word_count,
                        "topics": [topic for topic, count in top_topics],
                        "topic_counts": top_topics,
                        "member_since": metadata.get("member_since", "2024"),
                    }
                )
            except (OSError, yaml.YAMLError) as e:
                raise DocumentParsingError(str(profile_path), str(e)) from e
        return profiles

    def get_recent_media(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get recent media items for media index."""
        media_items = []
        adapter = self._adapter
        urls_dir = getattr(adapter, "urls_dir", adapter.media_dir / "urls")
        if not urls_dir.exists():
            return media_items
        url_files = sorted(
            [p for p in urls_dir.glob("*.md") if p.name != "index.md"],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:limit]
        for media_path in url_files:
            try:
                post = frontmatter.load(str(media_path))
                metadata, body = post.metadata, post.content
                summary = ""
                if "## Summary" in body:
                    summary_part = body.split("## Summary", 1)[1].split("##", 1)[0]
                    summary = summary_part.strip()[:200]
                media_items.append(
                    {
                        "title": metadata.get("title", media_path.stem),
                        "url": metadata.get("url", ""),
                        "slug": metadata.get("slug", media_path.stem),
                        "summary": summary or metadata.get("description", ""),
                    }
                )
            except (OSError, yaml.YAMLError) as e:
                raise DocumentParsingError(str(media_path), str(e)) from e
        return media_items

    def regenerate_tags_page(self) -> None:
        """Regenerate the tags.md page."""
        adapter = self._adapter
        if not hasattr(adapter, "posts_dir") or not adapter.posts_dir.exists():
            logger.debug("Posts directory not found, skipping tags page regeneration")
            return
        tag_counts: Counter = Counter()
        all_posts = list(adapter.documents())
        for post in all_posts:
            if post.type != DocumentType.POST:
                continue
            tags = post.metadata.get("tags", [])
            for tag in tags:
                if isinstance(tag, str) and tag.strip():
                    tag_counts[tag.strip()] += 1
        if not tag_counts:
            logger.info("No tags found in posts, skipping tags page regeneration")
            return
        max_count = max(tag_counts.values())
        min_count = min(tag_counts.values())
        count_range = max_count - min_count if max_count > min_count else 1
        tags_data = []
        for tag_name, count in tag_counts.items():
            if count_range > 0:
                frequency_level = int(((count - min_count) / count_range) * 9) + 1
            else:
                frequency_level = 5
            tags_data.append(
                {
                    "name": tag_name,
                    "slug": slugify(tag_name),
                    "count": count,
                    "frequency_level": min(10, max(1, frequency_level)),
                }
            )
        tags_data.sort(key=lambda x: x["count"], reverse=True)
        try:
            template = self._template_env.get_template("docs/posts/tags.md.jinja")
            content = template.render(tags=tags_data, generated_date=datetime.now(UTC).strftime("%Y-%m-%d"))
            tags_path = adapter.posts_dir / "tags.md"
            tags_path.write_text(content, encoding="utf-8")
            logger.info("Regenerated tags page with %d unique tags", len(tags_data))
        except (OSError, TemplateError):
            logger.exception("Failed to regenerate tags page")

    def regenerate_main_index(self) -> None:
        """Regenerates the main index.md from a template."""
        adapter = self._adapter
        if not adapter._initialized:
            logger.warning("Adapter not initialized, skipping main index regeneration.")
            return
        try:
            stats = self.get_site_stats()
            recent_media = self.get_recent_media(limit=5)
            profiles = self.get_profiles_data()
            template = self._template_env.get_template("docs/index.md.jinja")
            content = template.render(
                stats=stats,
                recent_media=recent_media,
                profiles=profiles,
                generated_date=datetime.now(UTC).strftime("%Y-%m-%d"),
            )
            index_path = adapter.docs_dir / "index.md"
            index_path.write_text(content, encoding="utf-8")
            logger.info("Regenerated main index page at %s", index_path)
        except (OSError, TemplateError):
            logger.exception("Failed to regenerate main index page")

    def regenerate_profiles_index(self) -> None:
        """Regenerates the profiles index.md from a template."""
        adapter = self._adapter
        if not adapter._initialized:
            logger.warning("Adapter not initialized, skipping profiles index regeneration.")
            return
        try:
            profiles = self.get_profiles_data()
            template = self._template_env.get_template("docs/profiles/index.md.jinja")
            content = template.render(
                profiles=profiles, generated_date=datetime.now(UTC).strftime("%Y-%m-%d")
            )
            index_path = adapter.profiles_dir / "index.md"
            index_path.write_text(content, encoding="utf-8")
            logger.info("Regenerated profiles index page with %d profiles at %s", len(profiles), index_path)
        except (OSError, TemplateError):
            logger.exception("Failed to regenerate profiles index page")

    def regenerate_media_index(self) -> None:
        """Regenerates the media index.md from a template."""
        adapter = self._adapter
        if not adapter._initialized:
            logger.warning("Adapter not initialized, skipping media index regeneration.")
            return
        try:
            recent_media = self.get_recent_media(limit=50)
            template = self._template_env.get_template("docs/media/index.md.jinja")
            content = template.render(
                media_items=recent_media, generated_date=datetime.now(UTC).strftime("%Y-%m-%d")
            )
            index_path = adapter.media_dir / "index.md"
            index_path.write_text(content, encoding="utf-8")
            logger.info("Regenerated media index page with %d items at %s", len(recent_media), index_path)
        except (OSError, TemplateError):
            logger.exception("Failed to regenerate media index page")
