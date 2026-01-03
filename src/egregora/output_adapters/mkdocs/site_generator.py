"""SiteGenerator for MkDocs output adapter.

This module contains the SiteGenerator class, which is responsible for
generating the static site pages for the MkDocs output adapter. It handles
all presentation-layer logic, such as rendering index pages, calculating
site statistics, and generating author profiles.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import frontmatter
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from egregora.data_primitives.document import Document, DocumentType
from egregora.knowledge.profiles import generate_fallback_avatar_url
from egregora.output_adapters.exceptions import DocumentParsingError
from egregora.utils.text_utils import slugify

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

        templates_dir = Path(__file__).resolve().parents[2] / "rendering" / "templates" / "site"
        self._template_env = Environment(
            loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape()
        )

    def _scan_directory(self, directory: Path, doc_type: DocumentType) -> Iterator[Document]:
        """Scans a directory for markdown files and yields Document objects."""
        if not directory.exists():
            return
        for path in directory.rglob("*.md"):
            if path.is_file() and "index" not in path.name:
                try:
                    post = frontmatter.load(str(path))
                    doc = Document(content=post.content, type=doc_type, metadata=post.metadata)
                    yield doc
                except (OSError, yaml.YAMLError) as e:
                    raise DocumentParsingError(str(path), str(e)) from e

    def get_site_stats(self) -> dict[str, int]:
        """Calculate site statistics for homepage."""
        post_count = len(list(self._scan_directory(self.posts_dir, DocumentType.POST)))
        profile_count = len(list(self.profiles_dir.glob("*/*.md")))  # Count files in author subdirs
        media_count = len(list(self._scan_directory(self.urls_dir, DocumentType.ENRICHMENT_URL)))
        journal_count = len(list(self._scan_directory(self.journal_dir, DocumentType.JOURNAL)))

        return {
            "post_count": post_count,
            "profile_count": profile_count,
            "media_count": media_count,
            "journal_count": journal_count,
        }

    def get_profiles_data(self) -> list[dict[str, Any]]:
        """Extract profile metadata for profiles index."""
        profiles = []
        all_posts = list(self._scan_directory(self.posts_dir, DocumentType.POST))

        if not self.profiles_dir.exists():
            return profiles

        for author_dir in sorted([p for p in self.profiles_dir.iterdir() if p.is_dir()]):
            try:
                candidates = [p for p in author_dir.glob("*.md") if p.name != "index.md"]
                if not candidates:
                    continue

                profile_path = max(candidates, key=lambda p: p.stat().st_mtime_ns)
                post = frontmatter.load(str(profile_path))
                metadata = post.metadata
                author_uuid = author_dir.name

                author_posts = [p for p in all_posts if author_uuid in p.metadata.get("authors", [])]
                topics = Counter(tag for p in author_posts for tag in p.metadata.get("tags", []))

                profiles.append(
                    {
                        "uuid": author_uuid,
                        "name": metadata.get("name", author_uuid[:8]),
                        "avatar": metadata.get("avatar", generate_fallback_avatar_url(author_uuid)),
                        "bio": metadata.get("bio", "Profile pending."),
                        "post_count": len(author_posts),
                        "word_count": sum(len(p.content.split()) for p in author_posts),
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

    def regenerate_tags_page(self) -> None:
        """Regenerate the tags.md page."""
        all_posts = self._scan_directory(self.posts_dir, DocumentType.POST)
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

    def regenerate_main_index(self) -> None:
        """Regenerates the main index.md from a template."""
        context = {
            "stats": self.get_site_stats(),
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
